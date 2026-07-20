"""
tests/test_drift.py
===================
Unit tests for core/drift.py.

No ZenML, no MLflow, no training data required.
All tests use small synthetic DataFrames and arrays.

Tests verify:
1. compute_psi_categorical() returns stable verdict when distributions match.
2. compute_psi_categorical() returns significant verdict when distributions diverge.
3. compute_psi_numeric() returns stable verdict for identical distributions.
4. compute_psi_numeric() returns significant verdict for fully shifted distributions.
5. compute_ks() returns stable for identical arrays.
6. compute_ks() returns significant for clearly separated distributions.
7. compute_chi2() returns stable for same-distribution categorical data.
8. compute_chi2() returns significant when one category disappears entirely.
9. compute_prediction_drift() returns stable for identical score arrays.
10. compute_prediction_drift() returns significant for clearly shifted scores.
11. run_drift_detection() returns DriftReport with correct drifted_features.
12. DriftReport.needs_retraining is False when all PSI < 0.25.
13. DriftReport.needs_retraining is True when any PSI > 0.25.

Run with:
    pytest tests/test_drift.py -v
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.drift import (
    DriftReport,
    FeatureDriftResult,
    compute_chi2,
    compute_ks,
    compute_prediction_drift,
    compute_psi_categorical,
    compute_psi_numeric,
    run_drift_detection,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _cat_series(values: list[str], name: str = "Product") -> pd.Series:
    return pd.Series(values, name=name)


def _num_series(values: list[float], name: str = "score") -> pd.Series:
    return pd.Series(values, dtype=float, name=name)


@pytest.fixture
def stable_cat():
    """Two identical categorical distributions — should return stable."""
    vals = ["Mortgage"] * 100 + ["Credit card"] * 80 + ["Debt collection"] * 20
    ref = _cat_series(vals)
    cur = _cat_series(vals)
    return ref, cur


@pytest.fixture
def drifted_cat():
    """Current drops one category entirely — should trigger significant drift."""
    ref = _cat_series(["A"] * 100 + ["B"] * 100 + ["C"] * 100)
    cur = _cat_series(["A"] * 200 + ["B"] * 100)  # C vanishes, A doubles
    return ref, cur


@pytest.fixture
def stable_num():
    rng = np.random.default_rng(0)
    vals = rng.normal(0, 1, 500).tolist()
    ref = _num_series(vals)
    cur = _num_series(vals)
    return ref, cur


@pytest.fixture
def drifted_num():
    rng = np.random.default_rng(1)
    ref = _num_series(rng.normal(0, 1, 500).tolist())
    cur = _num_series(rng.normal(10, 1, 500).tolist())  # completely shifted
    return ref, cur


# ---------------------------------------------------------------------------
# PSI categorical
# ---------------------------------------------------------------------------


def test_psi_categorical_stable(stable_cat):
    ref, cur = stable_cat
    result = compute_psi_categorical(ref, cur)
    assert isinstance(result, FeatureDriftResult)
    assert result.method == "psi"
    assert result.verdict == "stable"
    assert result.statistic < 0.10


def test_psi_categorical_significant(drifted_cat):
    ref, cur = drifted_cat
    result = compute_psi_categorical(ref, cur)
    assert result.verdict in ("moderate", "significant")
    assert result.statistic > 0.10


def test_psi_categorical_empty_series():
    """Empty series should not raise — returns stable with PSI=0."""
    ref = _cat_series([])
    cur = _cat_series(["A", "B"])
    result = compute_psi_categorical(ref, cur)
    assert result.statistic == 0.0
    assert result.verdict == "stable"


# ---------------------------------------------------------------------------
# PSI numeric
# ---------------------------------------------------------------------------


def test_psi_numeric_stable(stable_num):
    ref, cur = stable_num
    result = compute_psi_numeric(ref, cur)
    assert result.method == "psi"
    assert result.verdict == "stable"
    assert result.statistic < 0.10


def test_psi_numeric_significant(drifted_num):
    ref, cur = drifted_num
    result = compute_psi_numeric(ref, cur)
    assert result.verdict == "significant"
    assert result.statistic > 0.25


def test_psi_numeric_empty_series():
    ref = _num_series([])
    cur = _num_series([1.0, 2.0, 3.0])
    result = compute_psi_numeric(ref, cur)
    assert result.statistic == 0.0


# ---------------------------------------------------------------------------
# KS test
# ---------------------------------------------------------------------------


def test_ks_stable(stable_num):
    ref, cur = stable_num
    result = compute_ks(ref, cur)
    assert result.method == "ks"
    assert result.verdict == "stable"
    assert result.pvalue is not None
    assert result.pvalue > 0.01


def test_ks_significant(drifted_num):
    ref, cur = drifted_num
    result = compute_ks(ref, cur)
    assert result.verdict == "significant"
    assert result.pvalue < 0.01


def test_ks_insufficient_samples():
    """Fewer than 10 samples should return stable without raising."""
    ref = _num_series([1.0, 2.0, 3.0])
    cur = _num_series([1.0, 2.0, 3.0])
    result = compute_ks(ref, cur)
    assert result.verdict == "stable"
    assert result.pvalue == 1.0


# ---------------------------------------------------------------------------
# Chi-squared test
# ---------------------------------------------------------------------------


def test_chi2_stable(stable_cat):
    ref, cur = stable_cat
    result = compute_chi2(ref, cur)
    assert result.method == "chi2"
    assert result.verdict == "stable"
    assert result.pvalue is not None
    assert result.pvalue > 0.01


def test_chi2_significant(drifted_cat):
    ref, cur = drifted_cat
    result = compute_chi2(ref, cur)
    assert result.verdict in ("moderate", "significant")
    assert result.pvalue < 0.05


def test_chi2_insufficient_samples():
    ref = _cat_series(["A", "B"])
    cur = _cat_series(["A", "B"])
    result = compute_chi2(ref, cur)
    assert result.verdict == "stable"


# ---------------------------------------------------------------------------
# Prediction drift
# ---------------------------------------------------------------------------


def test_prediction_drift_stable():
    rng = np.random.default_rng(42)
    scores = rng.uniform(0.3, 0.7, 300)
    result = compute_prediction_drift(scores, scores)
    assert result.verdict == "stable"
    assert result.pvalue > 0.01


def test_prediction_drift_significant():
    rng = np.random.default_rng(42)
    ref = rng.uniform(0.1, 0.3, 300)
    cur = rng.uniform(0.7, 0.9, 300)
    result = compute_prediction_drift(ref, cur)
    assert result.verdict == "significant"
    assert result.pvalue < 0.01
    assert result.current_mean > result.ref_mean


def test_prediction_drift_insufficient():
    result = compute_prediction_drift([0.5], [0.5])
    assert result.verdict == "stable"


# ---------------------------------------------------------------------------
# run_drift_detection (integration)
# ---------------------------------------------------------------------------


def _make_ref_cur(n: int = 300, shift: bool = False):
    rng = np.random.default_rng(99)
    ref = pd.DataFrame(
        {
            "Product": rng.choice(["Mortgage", "Credit card", "Debt collection"], n),
            "Submitted via": rng.choice(["Web", "Phone", "Referral"], n),
            "Tags": rng.choice(["Older American", "Servicemember", None], n),
        }
    )
    if shift:
        # Dramatic shift: Submitted via only Web now
        cur = pd.DataFrame(
            {
                "Product": rng.choice(
                    ["Mortgage", "Credit card", "Debt collection"], n
                ),
                "Submitted via": ["Web"] * n,
                "Tags": rng.choice(["Older American", "Servicemember", None], n),
            }
        )
    else:
        cur = ref.copy()
    return ref, cur


def test_run_drift_detection_no_drift():
    ref, cur = _make_ref_cur(shift=False)
    report = run_drift_detection(
        ref,
        cur,
        categorical_features=["Product", "Submitted via"],
        numeric_features=[],
    )
    assert isinstance(report, DriftReport)
    assert not report.needs_retraining


def test_run_drift_detection_with_drift():
    ref, cur = _make_ref_cur(shift=True)
    report = run_drift_detection(
        ref,
        cur,
        categorical_features=["Product", "Submitted via"],
        numeric_features=[],
    )
    assert report.has_drift
    assert "Submitted via" in report.drifted_features


def test_drift_report_needs_retraining_false():
    """DriftReport with all stable results should not need retraining."""
    report = DriftReport(
        feature_results=[
            FeatureDriftResult(
                feature="Product",
                method="psi",
                statistic=0.05,
                pvalue=None,
                verdict="stable",
                message="ok",
            )
        ]
    )
    assert not report.needs_retraining
    assert not report.has_drift


def test_drift_report_needs_retraining_true():
    """DriftReport with one significant result should need retraining."""
    report = DriftReport(
        feature_results=[
            FeatureDriftResult(
                feature="Submitted via",
                method="psi",
                statistic=0.35,
                pvalue=None,
                verdict="significant",
                message="drift",
            )
        ]
    )
    assert report.needs_retraining
    assert report.has_drift
    assert "Submitted via" in report.retraining_features


def test_drift_report_summary_contains_key_info():
    ref, cur = _make_ref_cur(shift=True)
    report = run_drift_detection(
        ref,
        cur,
        categorical_features=["Submitted via"],
        numeric_features=[],
    )
    summary = report.summary()
    assert "ref=" in summary
    assert "current=" in summary


def test_run_drift_detection_missing_feature_skipped():
    """Features absent from one DataFrame should be skipped gracefully."""
    ref = pd.DataFrame({"Product": ["A", "B", "C"] * 100})
    cur = pd.DataFrame({"Other": ["X", "Y", "Z"] * 100})  # no 'Product'
    report = run_drift_detection(
        ref,
        cur,
        categorical_features=["Product"],
        numeric_features=[],
    )
    # No results — feature was skipped, not an error
    assert isinstance(report, DriftReport)
