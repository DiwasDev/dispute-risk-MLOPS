"""
tests/test_serving.py
=====================
Unit tests for app/schemas.py and core/monitoring.py.

No ZenML, no MLflow, no model loading required.
Tests verify the request/response schema contracts and the monitoring
snapshot + alert logic in isolation.

Tests verify:
1. ComplaintInput accepts required-only fields with None for optionals.
2. ComplaintInput.to_dataframe() produces correct column names.
3. ComplaintInput respects field aliases (e.g. "Date received" vs Date_received).
4. MonitoringSnapshot.summary() returns a non-empty string.
5. compute_monitoring_snapshot() handles an empty serving log gracefully.
6. check_alert_conditions() fires CRITICAL on zero requests.
7. check_alert_conditions() fires HIGH on prediction distribution collapse.
8. check_alert_conditions() fires HIGH on prediction mean drift.
9. check_alert_conditions() fires HIGH on latency SLA breach.
10. check_alert_conditions() fires MEDIUM on null rate spike.
11. AlertReport.is_healthy is True when no critical or high alerts.
12. AlertReport.needs_immediate_action is True when any critical alert exists.

Run with:
    pytest tests/test_serving.py -v
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.schemas import ComplaintInput, PredictionResponse
from core.monitoring import (
    LatencyStats,
    MonitoringSnapshot,
    NullRateStats,
    PredictionStats,
    check_alert_conditions,
    compute_monitoring_snapshot,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MINIMAL_COMPLAINT = {
    "Date received": "2016-03-15",
    "Product": "Mortgage",
    "Issue": "Loan modification,collection,foreclosure",
    "Company": "Bank of America",
    "State": "CA",
    "ZIP code": "90001",
    "Submitted via": "Web",
}

EXPECTED_COLUMNS = [
    "Date received",
    "Product",
    "Sub-product",
    "Issue",
    "Sub-issue",
    "Consumer complaint narrative",
    "Company",
    "State",
    "ZIP code",
    "Tags",
    "Consumer consent provided?",
    "Submitted via",
]


def _make_snapshot(
    request_count: int = 100,
    prediction_mean: float = 0.40,
    prediction_std: float = 0.18,
    positive_rate: float = 0.21,
    baseline_mean: float | None = None,
    latency_p95: float | None = None,
    null_stats: list[NullRateStats] | None = None,
) -> MonitoringSnapshot:
    pred_stats = PredictionStats(
        count=request_count,
        mean=prediction_mean,
        std=prediction_std,
        p10=max(0.0, prediction_mean - prediction_std),
        p50=prediction_mean,
        p90=min(1.0, prediction_mean + prediction_std),
        positive_rate=positive_rate,
        baseline_mean=baseline_mean,
    )
    lat_stats = None
    if latency_p95 is not None:
        lat_stats = LatencyStats(
            p50_ms=latency_p95 * 0.5,
            p95_ms=latency_p95,
            p99_ms=latency_p95 * 1.2,
            max_ms=latency_p95 * 1.5,
        )
    return MonitoringSnapshot(
        window_start="2016-03-15T00:00:00",
        window_end="2016-03-15T23:59:59",
        model_version="3",
        request_count=request_count,
        prediction_stats=pred_stats,
        latency_stats=lat_stats,
        null_rate_stats=null_stats or [],
    )


# ---------------------------------------------------------------------------
# Schema: ComplaintInput
# ---------------------------------------------------------------------------


def test_complaint_input_minimal():
    """Required fields only — all optionals should be None."""
    c = ComplaintInput(**MINIMAL_COMPLAINT)
    assert c.Product == "Mortgage"
    assert c.Sub_product is None
    assert c.Tags is None
    assert c.Consumer_complaint_narrative is None


def test_complaint_input_to_dataframe_columns():
    """to_dataframe() must produce exactly the columns the pipeline was trained on."""
    c = ComplaintInput(**MINIMAL_COMPLAINT)
    df = c.to_dataframe()
    assert list(df.columns) == EXPECTED_COLUMNS
    assert len(df) == 1


def test_complaint_input_to_dataframe_values():
    """Values must round-trip through to_dataframe() correctly."""
    complaint = {
        **MINIMAL_COMPLAINT,
        "Tags": "Servicemember",
        "Sub-product": "Conventional fixed mortgage",
    }
    c = ComplaintInput(**complaint)
    df = c.to_dataframe()
    assert df["Tags"].iloc[0] == "Servicemember"
    assert df["Sub-product"].iloc[0] == "Conventional fixed mortgage"
    assert df["Company"].iloc[0] == "Bank of America"


def test_complaint_input_alias_date_received():
    """'Date received' alias must work (field name has a space)."""
    c = ComplaintInput(**MINIMAL_COMPLAINT)
    df = c.to_dataframe()
    assert "Date received" in df.columns
    assert df["Date received"].iloc[0] == "2016-03-15"


def test_complaint_input_null_fields_in_dataframe():
    """Optional None fields must appear as None/NaN in the DataFrame."""
    c = ComplaintInput(**MINIMAL_COMPLAINT)
    df = c.to_dataframe()
    assert df["Sub-product"].iloc[0] is None
    assert df["Tags"].iloc[0] is None


def test_prediction_response_schema():
    """PredictionResponse validates probability bounds."""
    r = PredictionResponse(
        dispute_probability=0.75,
        dispute_predicted=True,
        model_version="3",
        model_alias="champion",
        threshold=0.5,
    )
    assert r.dispute_probability == 0.75
    assert r.dispute_predicted is True


# ---------------------------------------------------------------------------
# MonitoringSnapshot
# ---------------------------------------------------------------------------


def test_snapshot_summary_non_empty():
    snap = _make_snapshot()
    summary = snap.summary()
    assert isinstance(summary, str)
    assert len(summary) > 0
    assert "3" in summary  # model_version


def test_snapshot_anomalous_null_features_empty_when_none():
    snap = _make_snapshot()
    assert snap.anomalous_null_features == []


def test_snapshot_anomalous_null_detected():
    null_stats = [
        NullRateStats(
            feature="Product",
            current_null_rate=0.30,
            baseline_null_rate=0.01,
            delta=0.29,
        )
    ]
    snap = _make_snapshot(null_stats=null_stats)
    assert "Product" in snap.anomalous_null_features


# ---------------------------------------------------------------------------
# compute_monitoring_snapshot
# ---------------------------------------------------------------------------


def test_compute_snapshot_empty_log():
    """Empty serving log should not raise — returns minimal snapshot."""
    empty_log = pd.DataFrame(columns=["dispute_probability", "dispute_predicted"])
    snap = compute_monitoring_snapshot(empty_log, model_version="1")
    assert snap.request_count == 0
    assert snap.prediction_stats.count == 0


def test_compute_snapshot_no_latency_col():
    """Serving log without latency_ms should produce None latency_stats."""
    log = pd.DataFrame(
        {
            "dispute_probability": [0.3, 0.4, 0.6],
            "dispute_predicted": [False, False, True],
        }
    )
    snap = compute_monitoring_snapshot(log, model_version="1")
    assert snap.latency_stats is None
    assert snap.prediction_stats.count == 3


def test_compute_snapshot_null_rate_baseline():
    """Null rate spikes should appear in anomalous_null_features."""
    rng = np.random.default_rng(0)
    log = pd.DataFrame(
        {
            "dispute_probability": rng.uniform(0, 1, 100),
            "dispute_predicted": [False] * 100,
            "Product": [None] * 50 + ["Mortgage"] * 50,  # 50% null — spike
        }
    )
    snap = compute_monitoring_snapshot(
        log,
        model_version="1",
        baseline_null_rates={"Product": 0.01},  # baseline: 1% null
    )
    assert "Product" in snap.anomalous_null_features


# ---------------------------------------------------------------------------
# check_alert_conditions
# ---------------------------------------------------------------------------


def test_alert_zero_requests():
    snap = _make_snapshot(request_count=0)
    report = check_alert_conditions(snap)
    assert any(a.severity == "critical" for a in report.alerts)
    assert any("volume" in a.metric for a in report.alerts)


def test_alert_prediction_collapse():
    """std ≈ 0 should fire a CRITICAL alert."""
    snap = _make_snapshot(prediction_std=0.001, request_count=50)
    report = check_alert_conditions(snap)
    assert any(
        a.severity == "critical" and "prediction_std" in a.metric for a in report.alerts
    )


def test_alert_prediction_mean_drift():
    """Prediction mean shifted > threshold from baseline should fire HIGH."""
    snap = _make_snapshot(
        prediction_mean=0.75,
        baseline_mean=0.35,  # shift = 0.40 > threshold 0.10
    )
    report = check_alert_conditions(snap)
    assert any(
        a.severity == "high" and "prediction_mean" in a.metric for a in report.alerts
    )


def test_no_alert_when_prediction_near_baseline():
    """Prediction mean within threshold of baseline should not fire."""
    snap = _make_snapshot(
        prediction_mean=0.38,
        baseline_mean=0.35,  # shift = 0.03 < threshold 0.10
    )
    report = check_alert_conditions(snap)
    mean_alerts = [a for a in report.alerts if "prediction_mean" in a.metric]
    assert len(mean_alerts) == 0


def test_alert_latency_sla_breach():
    """p95 latency > 1000ms should fire HIGH."""
    snap = _make_snapshot(latency_p95=1500.0)  # 1.5s — over SLA
    report = check_alert_conditions(snap)
    assert any(
        a.severity == "high" and "latency_p95" in a.metric for a in report.alerts
    )


def test_no_alert_latency_within_sla():
    snap = _make_snapshot(latency_p95=400.0)  # well within 1s SLA
    report = check_alert_conditions(snap)
    latency_alerts = [a for a in report.alerts if "latency" in a.metric]
    assert len(latency_alerts) == 0


def test_alert_null_spike():
    null_stats = [
        NullRateStats(
            feature="Submitted via",
            current_null_rate=0.35,
            baseline_null_rate=0.01,
            delta=0.34,  # well above 0.05 threshold
        )
    ]
    snap = _make_snapshot(null_stats=null_stats)
    report = check_alert_conditions(snap)
    assert any("null_rate:Submitted via" in a.metric for a in report.alerts)


def test_alert_report_is_healthy_true():
    snap = _make_snapshot(
        request_count=100,
        prediction_std=0.18,
        baseline_mean=0.38,  # near enough to mean=0.40
    )
    report = check_alert_conditions(snap)
    assert report.is_healthy


def test_alert_report_needs_immediate_action():
    snap = _make_snapshot(request_count=0)  # triggers critical
    report = check_alert_conditions(snap)
    assert report.needs_immediate_action


def test_alert_report_summary_format():
    snap = _make_snapshot(request_count=0)
    report = check_alert_conditions(snap)
    summary = report.summary()
    assert "CRITICAL" in summary or "HIGH" in summary or "HEALTHY" in summary
