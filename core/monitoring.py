"""
core/monitoring.py
==================
Production monitoring for the Consumer Complaint Dispute Risk model.

No ZenML or MLflow imports — this module is framework-agnostic and fully
testable without any orchestration layer.

## The Four-Layer Monitoring Ladder

Read top-down for impact, bottom-up for root cause:

  Layer 4 — Business Outcomes   : complaint re-escalation rate, resolution cost
  Layer 3 — Product Metrics     : senior queue routing rate, volume trends
  Layer 2 — Model Metrics       : PR-AUC, F2, Recall@Precision (label-delayed)
  Layer 1 — Data/Feature Health : null rates, distributions, prediction shape

When something breaks: start at Layer 4 (what is the user impact?) and drill
down to Layer 1 (what caused it?).
When investigating proactively: start at Layer 1 (what shifted?) and look up
to Layer 4 (is it affecting users?).

## What this module provides

- MonitoringSnapshot  : structured capture of a serving window's health
- AlertItem           : a single alert with severity, message, and routing
- AlertReport         : aggregate of all alert conditions for a window
- compute_monitoring_snapshot() : builds a snapshot from a serving log DataFrame
- check_alert_conditions()      : compares snapshot to baseline, returns AlertReport

## Serving log schema

The serving log is expected to be a DataFrame with these columns
(all produced by app/main.py logging or a structured log sink):

  request_id        — unique identifier per request
  timestamp         — ISO datetime of request
  dispute_probability — model output probability (float)
  dispute_predicted  — binary decision (bool)
  latency_ms        — end-to-end request latency in milliseconds
  model_version     — model version that served the request
  + all input feature columns (for null rate and distribution monitoring)

In practice, build this log from your API access logs or from a structured
logging sink (e.g. write to a daily Parquet file per model_version).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Alert severity levels (from incident-response.md)
# ---------------------------------------------------------------------------

AlertSeverity = Literal["critical", "high", "medium", "low"]

# Thresholds — aligned with architecture.md §6 and production-readiness.md
LATENCY_P95_SLA_MS: float = 1000.0        # architecture.md: p95 < 1s
NULL_RATE_SPIKE_THRESHOLD: float = 0.05   # absolute increase triggering alert
PREDICTION_VOLUME_MIN: int = 1             # alert if zero predictions in window
PREDICTION_MEAN_DRIFT_THRESHOLD: float = 0.10  # abs mean shift triggering alert
PREDICTION_STD_CHANGE_FACTOR: float = 2.0      # std ratio triggering alert


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class NullRateStats:
    """Null rate statistics for a single feature in a serving window."""

    feature: str
    current_null_rate: float
    baseline_null_rate: float
    delta: float         # current - baseline (positive = more nulls than expected)

    @property
    def is_anomalous(self) -> bool:
        return abs(self.delta) > NULL_RATE_SPIKE_THRESHOLD


@dataclass
class PredictionStats:
    """
    Statistics for the model's prediction score distribution in a serving window.

    Prediction distribution monitoring is the fastest indirect signal for:
    - Training-serving skew (sudden collapse to a constant)
    - Concept drift (gradual mean shift)
    - Input pipeline failure (spike in nulls → scores collapse to baseline prior)
    """

    count: int
    mean: float
    std: float
    p10: float
    p50: float
    p90: float
    positive_rate: float    # fraction predicted as dispute (threshold-applied)
    baseline_mean: float | None = None
    baseline_std: float | None = None

    @property
    def mean_shift(self) -> float | None:
        if self.baseline_mean is None:
            return None
        return self.mean - self.baseline_mean

    @property
    def is_collapsed(self) -> bool:
        """True if the model is returning near-constant scores (std ≈ 0)."""
        return self.std < 0.01

    @property
    def mean_drifted(self) -> bool:
        """True if mean has shifted significantly from baseline."""
        if self.baseline_mean is None:
            return False
        return abs(self.mean - self.baseline_mean) > PREDICTION_MEAN_DRIFT_THRESHOLD


@dataclass
class LatencyStats:
    """Latency statistics for a serving window."""

    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float

    @property
    def sla_breached(self) -> bool:
        """True if p95 latency exceeds the architecture's 1s SLA."""
        return self.p95_ms > LATENCY_P95_SLA_MS


@dataclass
class MonitoringSnapshot:
    """
    Complete monitoring snapshot for a serving window.

    A snapshot covers a time window (e.g., 1 day, 1 week) of serving traffic.
    Compare snapshots over time to detect gradual drift and sudden spikes.

    Attributes
    ----------
    window_start, window_end : str
        ISO datetime strings bounding the serving window.
    model_version : str
        Model version that served this window's traffic.
    request_count : int
        Total requests in the window.
    prediction_stats : PredictionStats
        Score distribution summary.
    latency_stats : LatencyStats | None
        Latency distribution (None if latency not logged).
    null_rate_stats : list[NullRateStats]
        Per-feature null rate comparison to training baseline.
    anomalous_null_features : list[str]
        Feature names where null rate spiked above threshold.
    """

    window_start: str
    window_end: str
    model_version: str
    request_count: int
    prediction_stats: PredictionStats
    latency_stats: LatencyStats | None = None
    null_rate_stats: list[NullRateStats] = field(default_factory=list)

    @property
    def anomalous_null_features(self) -> list[str]:
        return [s.feature for s in self.null_rate_stats if s.is_anomalous]

    def summary(self) -> str:
        lines = [
            f"Window: {self.window_start} → {self.window_end}",
            f"Model version: {self.model_version}",
            f"Requests: {self.request_count:,}",
            f"Prediction mean={self.prediction_stats.mean:.3f} "
            f"std={self.prediction_stats.std:.3f} "
            f"positive_rate={self.prediction_stats.positive_rate:.1%}",
        ]
        if self.latency_stats:
            lines.append(
                f"Latency p50={self.latency_stats.p50_ms:.0f}ms "
                f"p95={self.latency_stats.p95_ms:.0f}ms "
                f"p99={self.latency_stats.p99_ms:.0f}ms"
            )
        if self.anomalous_null_features:
            lines.append(f"NULL SPIKES: {self.anomalous_null_features}")
        return " | ".join(lines)


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------


@dataclass
class AlertItem:
    """
    A single monitoring alert.

    Design rules from incident-response.md:
    - Tie to clear symptoms: specific metric, specific threshold, specific value.
    - Include routing owner and runbook link.
    - Severity determines response time.
    """

    severity: AlertSeverity
    layer: int                   # 1=data/feature, 2=model, 3=product, 4=business
    metric: str                  # e.g. "null_rate:Product", "latency_p95_ms"
    current_value: float | str
    threshold: float | str
    message: str
    owner: str = "ml-platform"   # Override per alert type with actual team name
    runbook: str = "See RUNBOOK.md"

    def __str__(self) -> str:
        return (
            f"[{self.severity.upper()}] Layer {self.layer} | {self.metric} "
            f"= {self.current_value} (threshold: {self.threshold}) | {self.message}"
        )


@dataclass
class AlertReport:
    """
    Aggregate alert report for a monitoring snapshot.

    Usage:
        report = check_alert_conditions(snapshot)
        for alert in report.critical_alerts:
            send_page(alert)
        for alert in report.high_alerts:
            create_ticket(alert)
    """

    snapshot_summary: str
    alerts: list[AlertItem] = field(default_factory=list)

    @property
    def critical_alerts(self) -> list[AlertItem]:
        return [a for a in self.alerts if a.severity == "critical"]

    @property
    def high_alerts(self) -> list[AlertItem]:
        return [a for a in self.alerts if a.severity == "high"]

    @property
    def medium_alerts(self) -> list[AlertItem]:
        return [a for a in self.alerts if a.severity == "medium"]

    @property
    def low_alerts(self) -> list[AlertItem]:
        return [a for a in self.alerts if a.severity == "low"]

    @property
    def is_healthy(self) -> bool:
        """True if no critical or high alerts."""
        return len(self.critical_alerts) == 0 and len(self.high_alerts) == 0

    @property
    def needs_immediate_action(self) -> bool:
        return len(self.critical_alerts) > 0

    def summary(self) -> str:
        status = (
            "CRITICAL" if self.critical_alerts
            else "HIGH" if self.high_alerts
            else "HEALTHY"
        )
        return (
            f"[{status}] {len(self.alerts)} alerts "
            f"(critical={len(self.critical_alerts)}, "
            f"high={len(self.high_alerts)}, "
            f"medium={len(self.medium_alerts)}, "
            f"low={len(self.low_alerts)})"
        )


# ---------------------------------------------------------------------------
# Snapshot computation
# ---------------------------------------------------------------------------


def compute_monitoring_snapshot(
    serving_log: pd.DataFrame,
    *,
    model_version: str = "unknown",
    baseline_null_rates: dict[str, float] | None = None,
    baseline_prediction_mean: float | None = None,
    baseline_prediction_std: float | None = None,
    window_start: str = "",
    window_end: str = "",
) -> MonitoringSnapshot:
    """
    Compute a monitoring snapshot from a serving log DataFrame.

    Parameters
    ----------
    serving_log : pd.DataFrame
        DataFrame of serving records. Expected columns:
          - dispute_probability (float): model output
          - dispute_predicted (bool): threshold-applied decision
          - latency_ms (float, optional): request latency
          - timestamp (str, optional): request timestamp
          - Any input feature columns for null rate monitoring.
    model_version : str
        Model version that produced this serving log.
    baseline_null_rates : dict[str, float], optional
        Training-time null rates per feature for comparison.
        From core/validation.py compute_null_baseline().
    baseline_prediction_mean : float, optional
        Mean prediction probability from training validation set.
    baseline_prediction_std : float, optional
        Std of prediction probability from training validation set.
    window_start, window_end : str
        ISO datetime strings for the window boundaries.

    Returns
    -------
    MonitoringSnapshot
    """
    if len(serving_log) == 0:
        logger.warning("Empty serving log provided. Returning minimal snapshot.")
        return MonitoringSnapshot(
            window_start=window_start,
            window_end=window_end,
            model_version=model_version,
            request_count=0,
            prediction_stats=PredictionStats(
                count=0, mean=0.0, std=0.0, p10=0.0, p50=0.0, p90=0.0,
                positive_rate=0.0,
            ),
        )

    # --- Prediction score statistics ---
    proba_col = "dispute_probability"
    pred_col = "dispute_predicted"

    scores = np.array([])
    positive_rate = 0.0

    if proba_col in serving_log.columns:
        scores = serving_log[proba_col].dropna().astype(float).values
    if pred_col in serving_log.columns:
        positive_rate = float(serving_log[pred_col].astype(bool).mean())

    prediction_stats = PredictionStats(
        count=len(scores),
        mean=float(scores.mean()) if len(scores) > 0 else 0.0,
        std=float(scores.std()) if len(scores) > 0 else 0.0,
        p10=float(np.percentile(scores, 10)) if len(scores) > 0 else 0.0,
        p50=float(np.percentile(scores, 50)) if len(scores) > 0 else 0.0,
        p90=float(np.percentile(scores, 90)) if len(scores) > 0 else 0.0,
        positive_rate=positive_rate,
        baseline_mean=baseline_prediction_mean,
        baseline_std=baseline_prediction_std,
    )

    # --- Latency statistics ---
    latency_stats = None
    latency_col = "latency_ms"
    if latency_col in serving_log.columns:
        lat = serving_log[latency_col].dropna().astype(float).values
        if len(lat) > 0:
            latency_stats = LatencyStats(
                p50_ms=float(np.percentile(lat, 50)),
                p95_ms=float(np.percentile(lat, 95)),
                p99_ms=float(np.percentile(lat, 99)),
                max_ms=float(lat.max()),
            )

    # --- Null rate statistics ---
    null_stats: list[NullRateStats] = []
    if baseline_null_rates:
        for feature, baseline_rate in baseline_null_rates.items():
            if feature not in serving_log.columns:
                continue
            current_rate = float(serving_log[feature].isna().mean())
            null_stats.append(NullRateStats(
                feature=feature,
                current_null_rate=current_rate,
                baseline_null_rate=baseline_rate,
                delta=current_rate - baseline_rate,
            ))

    snapshot = MonitoringSnapshot(
        window_start=window_start or str(serving_log.get("timestamp", pd.Series()).min()),
        window_end=window_end or str(serving_log.get("timestamp", pd.Series()).max()),
        model_version=model_version,
        request_count=len(serving_log),
        prediction_stats=prediction_stats,
        latency_stats=latency_stats,
        null_rate_stats=null_stats,
    )

    logger.info("Monitoring snapshot computed. %s", snapshot.summary())
    return snapshot


# ---------------------------------------------------------------------------
# Alert checking
# ---------------------------------------------------------------------------


def check_alert_conditions(snapshot: MonitoringSnapshot) -> AlertReport:
    """
    Check a monitoring snapshot against alert thresholds.

    Alert design rules (from incident-response.md):
    - Critical: page immediately (zero predictions, golden test failure, SLA breach)
    - High: respond within hours (prediction distribution collapse, latency sustained)
    - Medium: respond within one business day (null spikes, slow drifts)
    - Low: review in weekly triage (small persistent shifts)

    Parameters
    ----------
    snapshot : MonitoringSnapshot

    Returns
    -------
    AlertReport with all triggered alerts.
    """
    alerts: list[AlertItem] = []

    # -----------------------------------------------------------------------
    # Layer 1 — Data/Feature Health (fastest signal, no labels needed)
    # -----------------------------------------------------------------------

    # Zero request volume (data pipeline stopped)
    if snapshot.request_count == 0:
        alerts.append(AlertItem(
            severity="critical",
            layer=1,
            metric="request_volume",
            current_value=0,
            threshold=PREDICTION_VOLUME_MIN,
            message=(
                "Zero predictions in the monitoring window. "
                "Data pipeline may have stopped. Check API logs and upstream data."
            ),
            owner="data-engineering",
            runbook="RUNBOOK.md#zero-volume",
        ))

    # Null rate spikes (upstream pipeline failure)
    for null_stat in snapshot.null_rate_stats:
        if null_stat.is_anomalous:
            severity: AlertSeverity = (
                "high" if abs(null_stat.delta) > 0.20 else "medium"
            )
            alerts.append(AlertItem(
                severity=severity,
                layer=1,
                metric=f"null_rate:{null_stat.feature}",
                current_value=f"{null_stat.current_null_rate:.1%}",
                threshold=f"baseline {null_stat.baseline_null_rate:.1%} ± {NULL_RATE_SPIKE_THRESHOLD:.0%}",
                message=(
                    f"'{null_stat.feature}' null rate spiked from "
                    f"{null_stat.baseline_null_rate:.1%} (baseline) to "
                    f"{null_stat.current_null_rate:.1%} (Δ{null_stat.delta:+.1%}). "
                    "This usually signals an upstream pipeline break, not real drift."
                ),
                owner="data-engineering",
                runbook="RUNBOOK.md#null-rate-spike",
            ))

    # Prediction distribution collapse (model returning constant score)
    if snapshot.prediction_stats.is_collapsed and snapshot.request_count > 10:
        alerts.append(AlertItem(
            severity="critical",
            layer=1,
            metric="prediction_std",
            current_value=f"{snapshot.prediction_stats.std:.4f}",
            threshold="0.01",
            message=(
                f"Prediction score distribution has collapsed (std={snapshot.prediction_stats.std:.4f}). "
                "Model is returning near-constant scores. Likely cause: "
                "feature preprocessing failure, input pipeline bug, or wrong model loaded."
            ),
            owner="ml-platform",
            runbook="RUNBOOK.md#prediction-collapse",
        ))

    # Prediction mean drift
    if snapshot.prediction_stats.mean_drifted:
        mean_shift = snapshot.prediction_stats.mean_shift or 0.0
        alerts.append(AlertItem(
            severity="high",
            layer=1,
            metric="prediction_mean",
            current_value=f"{snapshot.prediction_stats.mean:.3f}",
            threshold=(
                f"baseline {snapshot.prediction_stats.baseline_mean:.3f} "
                f"± {PREDICTION_MEAN_DRIFT_THRESHOLD}"
            ),
            message=(
                f"Prediction mean shifted by {mean_shift:+.3f} from baseline "
                f"{snapshot.prediction_stats.baseline_mean:.3f}. "
                "This may indicate concept drift, a feature distribution shift, "
                "or training-serving skew. Run drift detection on recent traffic."
            ),
            owner="ml-platform",
            runbook="RUNBOOK.md#prediction-drift",
        ))

    # -----------------------------------------------------------------------
    # Layer 2 — Model Metrics (requires labels, handled separately via eval pipeline)
    # -----------------------------------------------------------------------
    # No alerts here — label delay means we cannot alert in real time.
    # Periodic evaluation pipeline (steps/evaluate.py) handles this.
    # When labels arrive, compare PR-AUC against the baseline floor.

    # -----------------------------------------------------------------------
    # Layer 3 — Product Metrics (proxy: positive rate, volume trends)
    # -----------------------------------------------------------------------

    # Senior queue saturation proxy: if positive rate > 60%, queue may be overwhelmed
    if snapshot.prediction_stats.positive_rate > 0.60 and snapshot.request_count > 50:
        alerts.append(AlertItem(
            severity="medium",
            layer=3,
            metric="positive_rate",
            current_value=f"{snapshot.prediction_stats.positive_rate:.1%}",
            threshold="60%",
            message=(
                f"Dispute routing rate is {snapshot.prediction_stats.positive_rate:.1%} "
                "(expected ~21% from training). Senior review queue may be saturated. "
                "Check if threshold needs adjustment or if the model is misbehaving."
            ),
            owner="product",
            runbook="RUNBOOK.md#queue-saturation",
        ))

    # -----------------------------------------------------------------------
    # Layer 3 — Serving Infrastructure (latency SLA)
    # -----------------------------------------------------------------------

    if snapshot.latency_stats and snapshot.latency_stats.sla_breached:
        alerts.append(AlertItem(
            severity="high",
            layer=3,
            metric="latency_p95_ms",
            current_value=f"{snapshot.latency_stats.p95_ms:.0f}ms",
            threshold=f"{LATENCY_P95_SLA_MS:.0f}ms",
            message=(
                f"p95 latency ({snapshot.latency_stats.p95_ms:.0f}ms) exceeds "
                f"SLA of {LATENCY_P95_SLA_MS:.0f}ms. "
                "Check for model complexity issues, infrastructure load, or feature "
                "computation bottlenecks."
            ),
            owner="ml-platform",
            runbook="RUNBOOK.md#latency-sla",
        ))

    report = AlertReport(
        snapshot_summary=snapshot.summary(),
        alerts=alerts,
    )

    if alerts:
        logger.warning(
            "Alert report: %s | Alerts: %s",
            report.summary(),
            [str(a) for a in alerts],
        )
    else:
        logger.info("Alert report: no alerts. System is healthy.")

    return report


# ---------------------------------------------------------------------------
# Convenience: build serving log from FastAPI request records
# ---------------------------------------------------------------------------


def build_serving_log_from_records(records: list[dict]) -> pd.DataFrame:
    """
    Build a serving log DataFrame from a list of request/response dicts.

    Each dict should contain the fields logged by app/main.py per request.
    This is a convenience function for testing and offline analysis.

    Parameters
    ----------
    records : list[dict]
        Each record should have keys matching the serving log schema.

    Returns
    -------
    pd.DataFrame suitable for compute_monitoring_snapshot().
    """
    return pd.DataFrame(records)
