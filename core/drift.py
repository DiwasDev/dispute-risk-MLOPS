"""
core/drift.py
=============
Statistical drift detection for the Consumer Complaint Dispute Risk model.

No ZenML or MLflow imports — this module is framework-agnostic and fully
testable without any orchestration layer installed.

## Two types of drift we detect

Data drift (covariate shift): P(X) changes, P(Y|X) stays the same.
  The input feature distributions shift — a new customer segment, a seasonal
  campaign, a regulatory change in who files complaints. The model may still
  be correct in principle but is operating outside its training distribution.

Concept drift: P(Y|X) changes. The same input features now map to different
  dispute outcomes — an economic downturn, a policy change, a product redesign.
  Concept drift requires ground-truth labels to confirm; we detect it indirectly
  via prediction distribution shift.

## Detection methods

PSI (Population Stability Index) — industry standard for financial ML.
  Works for both numeric (via binning) and categorical features.
  PSI < 0.10: stable. PSI 0.10–0.25: moderate shift, investigate.
  PSI > 0.25: significant shift, trigger retraining review.

KS (Kolmogorov-Smirnov) test — for continuous/numeric features.
  Measures maximum distance between CDFs. p-value < 0.01 → significant.
  Complementary to PSI: catches localized distribution shifts that PSI
  may average away.

Chi-squared test — for categorical features.
  Compares observed vs expected category frequencies.
  p-value < 0.01 → significant category distribution shift.

## Feature priority

Monitoring focuses on features with highest model importance and highest
real-world drift risk, as identified in the architecture and feature plan:
  - Product, Submitted via, Tags: low-cardinality categorical
  - Company: high-cardinality, monitored via frequency bucket
  - Prediction score distribution: always monitored (indirect concept drift)

## Reference

architecture.md §6: "Population Stability Index (PSI) for key features"
architecture.md §6: "Quarterly Review — update baselines every 3 months"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PSI thresholds (architecture.md §6)
# ---------------------------------------------------------------------------

PSI_STABLE: float = 0.10  # < 0.10 → no action
PSI_MODERATE: float = 0.25  # 0.10–0.25 → investigate
# > 0.25 → significant, trigger retraining review

# KS / Chi-squared significance level
PVALUE_THRESHOLD: float = 0.01

# Default number of bins for PSI on numeric features (industry standard: 10)
PSI_BINS: int = 10

# Features to monitor by type — from architecture.md feature engineering plan
CATEGORICAL_FEATURES: list[str] = [
    "Product",
    "Submitted via",
    "Tags",
    "Consumer consent provided?",
]

# High-cardinality: monitored via frequency bucket (top-N + "other")
HIGH_CARDINALITY_FEATURES: list[str] = ["Company", "State"]

NUMERIC_FEATURES: list[str] = [
    # After preprocessing these become numeric; monitor the raw/pre-encoded form
    # Time-derived features are monitored via prediction score distribution
    # instead, since raw dates don't drift meaningfully in isolation.
]

# All features we run drift detection on
MONITORED_FEATURES: list[str] = CATEGORICAL_FEATURES + HIGH_CARDINALITY_FEATURES

DriftVerdict = Literal["stable", "moderate", "significant"]


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------


@dataclass
class FeatureDriftResult:
    """Drift detection result for a single feature."""

    feature: str
    method: Literal["psi", "ks", "chi2"]
    statistic: float  # PSI value, KS statistic, or chi2 statistic
    pvalue: float | None  # None for PSI (threshold-based, not p-value-based)
    verdict: DriftVerdict
    message: str

    @property
    def is_drifted(self) -> bool:
        """True when drift is moderate or significant."""
        return self.verdict in ("moderate", "significant")

    @property
    def needs_retraining(self) -> bool:
        """True when drift is significant (PSI > 0.25 or p < 0.01)."""
        return self.verdict == "significant"


@dataclass
class PredictionDriftResult:
    """Drift detection result for the model's prediction score distribution."""

    method: Literal["ks", "psi"]
    statistic: float
    pvalue: float | None
    verdict: DriftVerdict
    ref_mean: float
    current_mean: float
    ref_std: float
    current_std: float
    message: str

    @property
    def is_drifted(self) -> bool:
        return self.verdict in ("moderate", "significant")

    @property
    def needs_retraining(self) -> bool:
        return self.verdict == "significant"


@dataclass
class DriftReport:
    """
    Aggregate drift detection report for a production serving window.

    Usage pattern:
        report = run_drift_detection(reference_df, current_df, pred_ref, pred_cur)
        if report.needs_retraining:
            trigger_retraining_pipeline()
        elif report.has_drift:
            alert_and_investigate()
    """

    feature_results: list[FeatureDriftResult] = field(default_factory=list)
    prediction_result: PredictionDriftResult | None = None
    reference_rows: int = 0
    current_rows: int = 0

    @property
    def has_drift(self) -> bool:
        """Any feature or prediction drift detected (moderate or significant)."""
        feature_drift = any(r.is_drifted for r in self.feature_results)
        pred_drift = (
            self.prediction_result is not None and self.prediction_result.is_drifted
        )
        return feature_drift or pred_drift

    @property
    def needs_retraining(self) -> bool:
        """Significant drift on any feature or prediction distribution."""
        feature_retrain = any(r.needs_retraining for r in self.feature_results)
        pred_retrain = (
            self.prediction_result is not None
            and self.prediction_result.needs_retraining
        )
        return feature_retrain or pred_retrain

    @property
    def drifted_features(self) -> list[str]:
        """Names of features with moderate or significant drift."""
        return [r.feature for r in self.feature_results if r.is_drifted]

    @property
    def retraining_features(self) -> list[str]:
        """Names of features with significant drift (PSI > 0.25)."""
        return [r.feature for r in self.feature_results if r.needs_retraining]

    def summary(self) -> str:
        """Human-readable one-paragraph summary."""
        status = (
            "RETRAIN"
            if self.needs_retraining
            else ("DRIFT" if self.has_drift else "STABLE")
        )
        lines = [
            f"[{status}] ref={self.reference_rows:,} rows | current={self.current_rows:,} rows",
            f"Features monitored: {len(self.feature_results)}",
            f"Drifted features: {self.drifted_features or 'none'}",
            f"Retraining-triggered features: {self.retraining_features or 'none'}",
        ]
        if self.prediction_result:
            lines.append(
                f"Prediction drift: {self.prediction_result.verdict} "
                f"(ref_mean={self.prediction_result.ref_mean:.3f}, "
                f"cur_mean={self.prediction_result.current_mean:.3f})"
            )
        return " | ".join(lines)


# ---------------------------------------------------------------------------
# PSI computation
# ---------------------------------------------------------------------------


def _psi_verdict(psi: float) -> DriftVerdict:
    if psi < PSI_STABLE:
        return "stable"
    elif psi < PSI_MODERATE:
        return "moderate"
    return "significant"


def compute_psi_numeric(
    reference: pd.Series,
    current: pd.Series,
    n_bins: int = PSI_BINS,
) -> FeatureDriftResult:
    """
    Compute PSI for a numeric feature using equal-width bins derived from
    the reference distribution.

    Why reference-derived bins: the reference (training) distribution defines
    what "normal" looks like. Current data is bucketed into the same bins so
    we measure drift relative to the baseline, not relative to itself.

    Parameters
    ----------
    reference : pd.Series
        Feature values from the training/reference window.
    current : pd.Series
        Feature values from the current serving window.
    n_bins : int
        Number of bins. Industry standard is 10.

    Returns
    -------
    FeatureDriftResult with method="psi".
    """
    feature = reference.name or "unknown"
    ref_clean = reference.dropna().astype(float)
    cur_clean = current.dropna().astype(float)

    if len(ref_clean) == 0 or len(cur_clean) == 0:
        logger.warning("PSI: empty series for feature '%s'. Returning PSI=0.", feature)
        return FeatureDriftResult(
            feature=feature,
            method="psi",
            statistic=0.0,
            pvalue=None,
            verdict="stable",
            message=f"'{feature}': insufficient data for PSI (ref={len(ref_clean)}, cur={len(cur_clean)}).",
        )

    # Build bins from reference distribution
    _, bin_edges = np.histogram(ref_clean, bins=n_bins)
    # Extend edges slightly to capture extreme values in current data
    bin_edges[0] -= 1e-6
    bin_edges[-1] += 1e-6

    ref_counts, _ = np.histogram(ref_clean, bins=bin_edges)
    cur_counts, _ = np.histogram(cur_clean, bins=bin_edges)

    # Convert to proportions; clip to avoid log(0)
    ref_pct = np.clip(ref_counts / len(ref_clean), 1e-6, None)
    cur_pct = np.clip(cur_counts / len(cur_clean), 1e-6, None)

    psi = float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))
    verdict = _psi_verdict(psi)

    msg = (
        f"'{feature}' PSI={psi:.4f} → {verdict.upper()}. "
        f"Thresholds: <{PSI_STABLE} stable, {PSI_STABLE}–{PSI_MODERATE} moderate, "
        f">{PSI_MODERATE} significant."
    )
    logger.info(msg)
    return FeatureDriftResult(
        feature=feature,
        method="psi",
        statistic=psi,
        pvalue=None,
        verdict=verdict,
        message=msg,
    )


def compute_psi_categorical(
    reference: pd.Series,
    current: pd.Series,
    top_n: int = 20,
) -> FeatureDriftResult:
    """
    Compute PSI for a categorical feature.

    Categories with less than 1% frequency in the reference are collapsed
    into an "_other_" bucket. This prevents spurious PSI spikes from rare
    categories appearing/disappearing due to sampling noise.

    Parameters
    ----------
    reference : pd.Series
        Categorical feature values from training/reference window.
    current : pd.Series
        Categorical feature values from the current serving window.
    top_n : int
        Number of top categories to track individually.

    Returns
    -------
    FeatureDriftResult with method="psi".
    """
    feature = reference.name or "unknown"
    ref_clean = reference.dropna().astype(str)
    cur_clean = current.dropna().astype(str)

    if len(ref_clean) == 0 or len(cur_clean) == 0:
        logger.warning("PSI categorical: empty series for feature '%s'.", feature)
        return FeatureDriftResult(
            feature=feature,
            method="psi",
            statistic=0.0,
            pvalue=None,
            verdict="stable",
            message=f"'{feature}': insufficient data for categorical PSI.",
        )

    # Build reference frequency table
    ref_freq = ref_clean.value_counts(normalize=True)
    # Keep top_n categories; collapse rest to "_other_"
    top_cats = set(ref_freq.nlargest(top_n).index)

    def bucket(series: pd.Series, cats: set) -> pd.Series:
        return series.apply(lambda x: x if x in cats else "_other_")

    ref_bucketed = bucket(ref_clean, top_cats)
    cur_bucketed = bucket(cur_clean, top_cats)

    # All categories present in reference after bucketing
    all_cats = set(ref_bucketed.unique()) | {"_other_"}

    ref_pct = ref_bucketed.value_counts(normalize=True).reindex(
        all_cats, fill_value=0.0
    )
    cur_pct = cur_bucketed.value_counts(normalize=True).reindex(
        all_cats, fill_value=0.0
    )

    # Clip to avoid log(0)
    ref_pct_arr = np.clip(ref_pct.values, 1e-6, None)
    cur_pct_arr = np.clip(cur_pct.values, 1e-6, None)

    psi = float(np.sum((cur_pct_arr - ref_pct_arr) * np.log(cur_pct_arr / ref_pct_arr)))
    verdict = _psi_verdict(psi)

    msg = (
        f"'{feature}' categorical PSI={psi:.4f} → {verdict.upper()}. "
        f"Tracked {len(all_cats)} categories (top {top_n} + _other_)."
    )
    logger.info(msg)
    return FeatureDriftResult(
        feature=feature,
        method="psi",
        statistic=psi,
        pvalue=None,
        verdict=verdict,
        message=msg,
    )


# ---------------------------------------------------------------------------
# KS test (numeric features)
# ---------------------------------------------------------------------------


def compute_ks(
    reference: pd.Series,
    current: pd.Series,
) -> FeatureDriftResult:
    """
    Kolmogorov-Smirnov test for a numeric feature.

    KS is complementary to PSI: it catches localized distribution shifts
    (a bump appearing in the tail) that PSI may average away across bins.
    Use both and treat any positive result as a signal.

    Parameters
    ----------
    reference, current : pd.Series
        Numeric feature values from reference and current windows.

    Returns
    -------
    FeatureDriftResult with method="ks".
    """
    feature = reference.name or "unknown"
    ref_clean = reference.dropna().astype(float).values
    cur_clean = current.dropna().astype(float).values

    if len(ref_clean) < 10 or len(cur_clean) < 10:
        logger.warning("KS: too few samples for feature '%s'. Skipping.", feature)
        return FeatureDriftResult(
            feature=feature,
            method="ks",
            statistic=0.0,
            pvalue=1.0,
            verdict="stable",
            message=f"'{feature}': insufficient samples for KS test.",
        )

    ks_stat, pvalue = stats.ks_2samp(ref_clean, cur_clean)

    if pvalue < PVALUE_THRESHOLD:
        verdict: DriftVerdict = "significant"
    elif pvalue < 0.05:
        verdict = "moderate"
    else:
        verdict = "stable"

    msg = (
        f"'{feature}' KS statistic={ks_stat:.4f}, p-value={pvalue:.4f} → {verdict.upper()}. "
        f"Threshold: p < {PVALUE_THRESHOLD} = significant."
    )
    logger.info(msg)
    return FeatureDriftResult(
        feature=feature,
        method="ks",
        statistic=ks_stat,
        pvalue=pvalue,
        verdict=verdict,
        message=msg,
    )


# ---------------------------------------------------------------------------
# Chi-squared test (categorical features)
# ---------------------------------------------------------------------------


def compute_chi2(
    reference: pd.Series,
    current: pd.Series,
) -> FeatureDriftResult:
    """
    Chi-squared test for categorical feature distribution shift.

    Compares observed category frequencies in the current window against
    expected frequencies from the reference. Sensitive to both appearance
    of new categories and disappearance of existing ones.

    Parameters
    ----------
    reference, current : pd.Series
        Categorical feature values from reference and current windows.

    Returns
    -------
    FeatureDriftResult with method="chi2".
    """
    feature = reference.name or "unknown"
    ref_clean = reference.dropna().astype(str)
    cur_clean = current.dropna().astype(str)

    if len(ref_clean) < 5 or len(cur_clean) < 5:
        logger.warning("Chi2: too few samples for feature '%s'. Skipping.", feature)
        return FeatureDriftResult(
            feature=feature,
            method="chi2",
            statistic=0.0,
            pvalue=1.0,
            verdict="stable",
            message=f"'{feature}': insufficient samples for chi-squared test.",
        )

    # Build aligned frequency table across all categories
    all_cats = sorted(set(ref_clean.unique()) | set(cur_clean.unique()))
    ref_counts = ref_clean.value_counts().reindex(all_cats, fill_value=0).values
    cur_counts = cur_clean.value_counts().reindex(all_cats, fill_value=0).values

    # Chi-squared expects expected frequencies; scale reference to current size
    expected = ref_counts * (len(cur_clean) / max(len(ref_clean), 1))
    # Avoid zero expected cells (can cause chi2 to blow up)
    expected = np.clip(expected, 0.5, None)
    # Normalize expected so its sum exactly equals observed sum (scipy requirement)
    expected = expected * (cur_counts.sum() / expected.sum())

    chi2_stat, pvalue = stats.chisquare(f_obs=cur_counts, f_exp=expected)

    if pvalue < PVALUE_THRESHOLD:
        verdict: DriftVerdict = "significant"
    elif pvalue < 0.05:
        verdict = "moderate"
    else:
        verdict = "stable"

    msg = (
        f"'{feature}' chi2={chi2_stat:.2f}, p-value={pvalue:.4f} → {verdict.upper()}. "
        f"Compared {len(all_cats)} categories."
    )
    logger.info(msg)
    return FeatureDriftResult(
        feature=feature,
        method="chi2",
        statistic=chi2_stat,
        pvalue=pvalue,
        verdict=verdict,
        message=msg,
    )


# ---------------------------------------------------------------------------
# Prediction score drift
# ---------------------------------------------------------------------------


def compute_prediction_drift(
    reference_scores: np.ndarray | list[float],
    current_scores: np.ndarray | list[float],
) -> PredictionDriftResult:
    """
    Monitor the model's prediction score distribution for drift.

    This is the fastest indirect signal for concept drift. If the input
    features haven't changed but prediction scores have shifted, the model
    may be responding to a genuine change in dispute patterns — or a
    training-serving skew bug. Either way, investigate immediately.

    Uses KS test + PSI on the score distribution.

    Parameters
    ----------
    reference_scores : array-like of float in [0, 1]
        Prediction probabilities from a reference window (e.g., first week
        of deployment or the validation set).
    current_scores : array-like of float in [0, 1]
        Prediction probabilities from the current serving window.

    Returns
    -------
    PredictionDriftResult
    """
    ref = np.asarray(reference_scores, dtype=float)
    cur = np.asarray(current_scores, dtype=float)

    if len(ref) < 10 or len(cur) < 10:
        logger.warning("Prediction drift: insufficient samples. Returning stable.")
        return PredictionDriftResult(
            method="ks",
            statistic=0.0,
            pvalue=1.0,
            verdict="stable",
            ref_mean=float(ref.mean()) if len(ref) > 0 else 0.0,
            current_mean=float(cur.mean()) if len(cur) > 0 else 0.0,
            ref_std=float(ref.std()) if len(ref) > 0 else 0.0,
            current_std=float(cur.std()) if len(cur) > 0 else 0.0,
            message="Insufficient samples for prediction drift detection.",
        )

    ks_stat, pvalue = stats.ks_2samp(ref, cur)

    if pvalue < PVALUE_THRESHOLD:
        verdict: DriftVerdict = "significant"
    elif pvalue < 0.05:
        verdict = "moderate"
    else:
        verdict = "stable"

    ref_mean, cur_mean = float(ref.mean()), float(cur.mean())
    ref_std, cur_std = float(ref.std()), float(cur.std())

    msg = (
        f"Prediction score drift KS={ks_stat:.4f}, p={pvalue:.4f} → {verdict.upper()}. "
        f"ref_mean={ref_mean:.3f}±{ref_std:.3f}, "
        f"cur_mean={cur_mean:.3f}±{cur_std:.3f}. "
        f"Mean shift={cur_mean - ref_mean:+.3f}."
    )
    logger.info(msg)

    return PredictionDriftResult(
        method="ks",
        statistic=ks_stat,
        pvalue=pvalue,
        verdict=verdict,
        ref_mean=ref_mean,
        current_mean=cur_mean,
        ref_std=ref_std,
        current_std=cur_std,
        message=msg,
    )


# ---------------------------------------------------------------------------
# Public API: run full drift detection
# ---------------------------------------------------------------------------


def run_drift_detection(
    reference_df: pd.DataFrame,
    current_df: pd.DataFrame,
    reference_scores: np.ndarray | list[float] | None = None,
    current_scores: np.ndarray | list[float] | None = None,
    categorical_features: list[str] | None = None,
    numeric_features: list[str] | None = None,
) -> DriftReport:
    """
    Run the full drift detection suite for a serving window.

    For each monitored feature:
      - Categorical (low/high-cardinality): PSI + Chi-squared
      - Numeric: PSI + KS
    Plus: prediction score distribution drift if scores are provided.

    The report's `needs_retraining` flag is True if ANY feature exceeds
    PSI > 0.25. Use this to trigger a retraining pipeline automatically.

    Parameters
    ----------
    reference_df : pd.DataFrame
        The training (or stable reference window) DataFrame.
    current_df : pd.DataFrame
        DataFrame from the current serving window (e.g., last 7 days).
    reference_scores : array-like, optional
        Model prediction probabilities for the reference window.
    current_scores : array-like, optional
        Model prediction probabilities for the current window.
    categorical_features : list[str], optional
        Override the default monitored categorical features.
    numeric_features : list[str], optional
        Override the default monitored numeric features.

    Returns
    -------
    DriftReport
        Structured report. Check `report.needs_retraining` and
        `report.drifted_features` for alert routing.

    Examples
    --------
    >>> report = run_drift_detection(train_df, serving_df, train_scores, live_scores)
    >>> if report.needs_retraining:
    ...     print("Retraining triggered:", report.retraining_features)
    """
    cat_features = (
        categorical_features or CATEGORICAL_FEATURES + HIGH_CARDINALITY_FEATURES
    )
    num_features = numeric_features or NUMERIC_FEATURES

    logger.info(
        "Starting drift detection. ref=%d rows, current=%d rows. "
        "Monitoring %d categorical + %d numeric features.",
        len(reference_df),
        len(current_df),
        len(cat_features),
        len(num_features),
    )

    report = DriftReport(
        reference_rows=len(reference_df),
        current_rows=len(current_df),
    )

    # --- Categorical features: PSI + Chi-squared ---
    for feature in cat_features:
        if feature not in reference_df.columns or feature not in current_df.columns:
            logger.warning("Feature '%s' not found in DataFrame. Skipping.", feature)
            continue

        ref_series = reference_df[feature].rename(feature)
        cur_series = current_df[feature].rename(feature)

        psi_result = compute_psi_categorical(ref_series, cur_series)
        chi2_result = compute_chi2(ref_series, cur_series)

        # Always use PSI as the primary metric (architecture requirement)
        report.feature_results.append(psi_result)
        if chi2_result.is_drifted and not psi_result.is_drifted:
            # Chi2 caught something PSI missed — add as a secondary result
            report.feature_results.append(chi2_result)

    # --- Numeric features: PSI + KS ---
    for feature in num_features:
        if feature not in reference_df.columns or feature not in current_df.columns:
            logger.warning("Feature '%s' not found in DataFrame. Skipping.", feature)
            continue

        ref_series = reference_df[feature].rename(feature)
        cur_series = current_df[feature].rename(feature)

        psi_result = compute_psi_numeric(ref_series, cur_series)
        ks_result = compute_ks(ref_series, cur_series)

        report.feature_results.append(psi_result)
        if ks_result.is_drifted and not psi_result.is_drifted:
            report.feature_results.append(ks_result)

    # --- Prediction score drift ---
    if reference_scores is not None and current_scores is not None:
        report.prediction_result = compute_prediction_drift(
            reference_scores, current_scores
        )

    logger.info("Drift detection complete. %s", report.summary())
    return report
