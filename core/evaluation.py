"""
core/evaluation.py
==================
Pure Python evaluation logic. No ZenML imports.

Responsibilities:
  1. Compute the full metric suite: PR-AUC, F-beta, Recall@Precision,
     confusion matrix, threshold-specific precision/recall/F2.
  2. Bootstrap 95% confidence intervals for any scalar metric.
  3. Tune the operating threshold to maximize F-beta on the validation set.
  4. Evaluate model performance per business-relevant slice.
  5. Return a structured EvaluationResult for MLflow logging.

## Why each metric exists

PR-AUC (primary):
  Threshold-independent. For a 21% positive rate, PR-AUC is more informative
  than ROC-AUC because it directly measures performance on the minority class
  across all thresholds. The area under the PR curve equals the average precision
  across recall levels — when recall drops to zero (model flags nothing),
  precision is undefined and the curve area shrinks fast. This punishes bad
  minority-class behavior more than ROC.

F2-score (guardrail):
  Weights recall 4x more than precision (via beta^2 = 4). This matches the
  problem framing: a missed dispute (false negative) costs more than an
  unnecessary senior review (false positive). F2 captures this asymmetry
  in a single operable threshold metric.

Recall@Precision (guardrail):
  Answers the product question: "At the capacity of our senior queue (fixed
  precision), what fraction of actual disputes do we catch?" This is the metric
  the business actually cares about day-to-day. We target Recall given
  precision >= 0.40 (assumes ~2x queue capacity tolerance).

Bootstrapped CIs:
  A single metric point is not evidence for model comparison or go/no-go
  decisions. CIs built from 1000 bootstrap resamples give the decision-maker
  a range: "we are 95% confident the true PR-AUC is in [lo, hi]." If two
  models' CIs overlap substantially, the difference is not significant.

Threshold tuning:
  The default 0.5 threshold is arbitrary. The optimal threshold for F2 is
  found by scanning [0.1, 0.9] on the validation set in 0.01 steps. This is
  done AFTER training, on the held-out validation split — no data leakage.
  Threshold tuning is the first-line response to class imbalance; it costs
  nothing and risks nothing.

Slice evaluation:
  Global metrics hide segment failures. We evaluate separately on Product,
  Submitted via, and Tags — all available at intake time, all meaningful
  business segments. A model with good aggregate PR-AUC that fails on
  "Servicemember" tagged complaints is not production-ready.

## Class imbalance decision (four-factor framework)

1. Minority class ratio: 21% (1:4.8). NOT below 5%.
2. Metric: PR-AUC is threshold-independent; F2 is recall-weighted.
3. Model: Logistic regression (class_weight="balanced" already set in config).
          XGBoost/LightGBM handle moderate imbalance natively.
4. Threshold tuning: done here, first.

Decision: class_weight="balanced" (set in config) + threshold tuning.
SMOTE is not warranted: the dataset has 76K minority examples (well above
the 1,000-example threshold), and the dataset has high-cardinality categorical
features where interpolation is nonsensical. Log this decision explicitly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

import mlflow
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    fbeta_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline

from core.training import TrainingConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------


@dataclass
class ThresholdMetrics:
    """Metrics computed at a specific classification threshold."""

    threshold: float
    precision: float
    recall: float
    f2: float
    f1: float
    tp: int
    fp: int
    fn: int
    tn: int

    @property
    def flagged_rate(self) -> float:
        """Fraction of validation set flagged as high-risk."""
        total = self.tp + self.fp + self.fn + self.tn
        return (self.tp + self.fp) / total if total > 0 else 0.0


@dataclass
class ConfidenceInterval:
    """95% bootstrap confidence interval for a scalar metric."""

    point_estimate: float
    lower: float  # 2.5th percentile
    upper: float  # 97.5th percentile
    n_bootstraps: int

    def __str__(self) -> str:
        return f"{self.point_estimate:.4f} (95% CI: {self.lower:.4f}–{self.upper:.4f})"


@dataclass
class SliceResult:
    """Evaluation metrics for one slice (e.g., Product='Mortgage')."""

    slice_column: str
    slice_value: str
    n_samples: int
    n_positive: int
    pr_auc: float | None  # None if slice has no positive examples
    f2_at_threshold: float | None
    recall_at_threshold: float | None
    precision_at_threshold: float | None


@dataclass
class EvaluationResult:
    """
    Complete evaluation output for one model run.

    Structured to map directly to MLflow metric logging:
      - Scalar metrics → mlflow.log_metrics()
      - Slice results → mlflow.log_table() or individual metrics with prefix
      - Artifacts → mlflow.log_artifact() (PR curve plot, confusion matrix)
    """

    # Global threshold-independent metrics
    pr_auc: float
    roc_auc: float

    # Bootstrapped CIs for primary metric
    pr_auc_ci: ConfidenceInterval

    # Operating threshold chosen by F2 maximization
    optimal_threshold: float
    threshold_metrics: ThresholdMetrics

    # Recall at a fixed precision target (guardrail)
    recall_at_target_precision: float
    target_precision: float  # what precision level was held fixed

    # Slice-level results
    slice_results: list[SliceResult] = field(default_factory=list)

    # Class imbalance decision log
    imbalance_decision: str = ""

    def summary_lines(self) -> list[str]:
        """Human-readable summary for logging."""
        lines = [
            f"PR-AUC:        {self.pr_auc_ci}",
            f"ROC-AUC:       {self.roc_auc:.4f}",
            f"Threshold:     {self.optimal_threshold:.2f} (F2-maximized)",
            f"  Precision:   {self.threshold_metrics.precision:.4f}",
            f"  Recall:      {self.threshold_metrics.recall:.4f}",
            f"  F2:          {self.threshold_metrics.f2:.4f}",
            f"  Flagged:     {self.threshold_metrics.flagged_rate:.1%} of validation set",
            f"Recall@P>={self.target_precision:.2f}: {self.recall_at_target_precision:.4f}",
        ]
        if self.slice_results:
            lines.append("\nSlice PR-AUC:")
            for sr in self.slice_results:
                if sr.pr_auc is not None:
                    lines.append(
                        f"  [{sr.slice_column}={sr.slice_value}] "
                        f"n={sr.n_samples} (+={sr.n_positive}) "
                        f"PR-AUC={sr.pr_auc:.4f}"
                    )
        return lines


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------


def compute_threshold_metrics(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    threshold: float,
    beta: float = 2.0,
) -> ThresholdMetrics:
    """
    Compute precision, recall, F-beta at a given threshold.

    Parameters
    ----------
    y_true : np.ndarray of int (0/1)
    y_proba : np.ndarray of float — predicted probabilities for the positive class
    threshold : float — decision threshold
    beta : float — beta for F-beta score (2 = F2, weights recall 4x precision)

    Returns
    -------
    ThresholdMetrics
    """
    y_pred = (y_proba >= threshold).astype(int)

    # Handle edge cases: if all predictions are one class, sklearn metrics
    # will warn but not crash. We want clean logging.
    if y_pred.sum() == 0:
        logger.warning(
            "Threshold %.2f produces zero positive predictions. "
            "Precision/Recall/F2 are all 0. Consider lowering the threshold.",
            threshold,
        )

    precision = precision_score(y_true, y_pred, zero_division=0.0)
    recall = recall_score(y_true, y_pred, zero_division=0.0)
    f2 = fbeta_score(y_true, y_pred, beta=beta, zero_division=0.0)
    f1 = f1_score(y_true, y_pred, zero_division=0.0)

    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()

    return ThresholdMetrics(
        threshold=threshold,
        precision=float(precision),
        recall=float(recall),
        f2=float(f2),
        f1=float(f1),
        tp=int(tp),
        fp=int(fp),
        fn=int(fn),
        tn=int(tn),
    )


# ---------------------------------------------------------------------------
# Bootstrap confidence intervals
# ---------------------------------------------------------------------------


def bootstrap_ci(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    metric_fn: Callable[[np.ndarray, np.ndarray], float],
    n_iters: int = 1000,
    seed: int = 42,
    confidence: float = 0.95,
) -> ConfidenceInterval:
    """
    Compute a bootstrap confidence interval for any scalar metric.

    Procedure (1000 iterations is the minimum for reliable 95% CIs):
      1. Sample test set indices with replacement (same size as original).
      2. Compute metric on the bootstrap sample.
      3. Repeat n_iters times.
      4. Report the point estimate on the full set + percentile CI from distribution.

    Why percentile bootstrap (not normal-approximation)?
      The percentile method is non-parametric — it makes no assumption about
      the metric's sampling distribution. For PR-AUC, which is bounded [0,1]
      and skewed, the normal approximation can produce CIs outside [0,1].

    Parameters
    ----------
    y_true : np.ndarray of int (0/1)
    y_proba : np.ndarray of float
    metric_fn : callable(y_true, y_proba) → float
    n_iters : int — number of bootstrap resamples
    seed : int — random seed for reproducibility
    confidence : float — CI level (0.95 → 2.5th/97.5th percentiles)

    Returns
    -------
    ConfidenceInterval with point estimate and percentile bounds.
    """
    rng = np.random.RandomState(seed)
    n = len(y_true)
    scores = np.empty(n_iters)

    for i in range(n_iters):
        idx = rng.choice(n, size=n, replace=True)
        y_t = y_true[idx]
        y_p = y_proba[idx]

        # Skip degenerate samples (all one class — metric is undefined).
        # This can happen with very small test sets. Replace with the
        # point estimate so the distribution is not biased downward.
        if len(np.unique(y_t)) < 2:
            scores[i] = metric_fn(y_true, y_proba)
        else:
            try:
                scores[i] = metric_fn(y_t, y_p)
            except Exception:
                scores[i] = metric_fn(y_true, y_proba)

    alpha = (1.0 - confidence) / 2.0
    lower = float(np.percentile(scores, alpha * 100))
    upper = float(np.percentile(scores, (1 - alpha) * 100))
    point = float(metric_fn(y_true, y_proba))

    return ConfidenceInterval(
        point_estimate=point,
        lower=lower,
        upper=upper,
        n_bootstraps=n_iters,
    )


# ---------------------------------------------------------------------------
# Threshold tuning
# ---------------------------------------------------------------------------


def tune_threshold(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    beta: float = 2.0,
    thresholds: np.ndarray | None = None,
) -> tuple[float, ThresholdMetrics]:
    """
    Find the threshold that maximizes F-beta score on the validation set.

    This is the FIRST response to class imbalance — not SMOTE, not oversampling.
    Threshold tuning:
      - Works within the model's existing calibration
      - Requires no modification to training data
      - Has zero risk of synthetic data artifacts or leakage
      - Is fully reproducible (scan is deterministic)

    Parameters
    ----------
    y_true : np.ndarray of int (0/1)
    y_proba : np.ndarray of float — positive class probabilities
    beta : float — beta for F-beta score (2.0 → F2, recall-weighted)
    thresholds : np.ndarray | None
        Candidate thresholds to scan. If None, uses precision-recall curve
        thresholds (more efficient than a fixed grid) plus 0.1-0.9 grid.

    Returns
    -------
    (optimal_threshold, ThresholdMetrics at optimal_threshold)
    """
    # Use precision-recall curve thresholds — these are the natural breakpoints
    # where predictions change class, so they cover the important range without
    # a brute-force grid. Augment with a coarse grid for safety.
    if thresholds is None:
        _, _, pr_thresholds = precision_recall_curve(y_true, y_proba)
        coarse_grid = np.arange(0.05, 0.95, 0.01)
        thresholds = np.unique(np.concatenate([pr_thresholds, coarse_grid]))
        thresholds = np.clip(thresholds, 0.01, 0.99)

    best_threshold = 0.5
    best_f2 = 0.0

    for t in thresholds:
        y_pred = (y_proba >= t).astype(int)
        f2 = fbeta_score(y_true, y_pred, beta=beta, zero_division=0.0)
        if f2 > best_f2:
            best_f2 = f2
            best_threshold = float(t)

    metrics = compute_threshold_metrics(y_true, y_proba, best_threshold, beta=beta)
    logger.info(
        "Threshold tuning: optimal=%.3f | F2=%.4f | Precision=%.4f | Recall=%.4f",
        best_threshold,
        metrics.f2,
        metrics.precision,
        metrics.recall,
    )
    return best_threshold, metrics


# ---------------------------------------------------------------------------
# Recall at fixed precision
# ---------------------------------------------------------------------------


def recall_at_fixed_precision(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    target_precision: float = 0.40,
) -> float:
    """
    Find the maximum recall achievable at or above target_precision.

    Business interpretation: "At a senior-queue precision of at least 40%
    (i.e., at least 2 out of 5 flagged complaints actually escalate),
    what fraction of all disputes do we catch?"

    This is the guardrail metric from problem_statement.md.
    Target precision of 0.40 is a placeholder — adjust to the actual
    senior-queue capacity once known.

    Parameters
    ----------
    y_true : np.ndarray of int (0/1)
    y_proba : np.ndarray of float
    target_precision : float — minimum acceptable precision

    Returns
    -------
    float — maximum recall achieved when precision >= target_precision.
             Returns 0.0 if no threshold achieves target_precision.
    """
    precisions, recalls, _ = precision_recall_curve(y_true, y_proba)

    # precision_recall_curve returns in decreasing-recall order.
    # Find all points where precision >= target, take the max recall among them.
    eligible = recalls[precisions >= target_precision]

    if len(eligible) == 0:
        logger.warning(
            "No threshold achieves precision >= %.2f. "
            "Model may not be precise enough for the target queue capacity.",
            target_precision,
        )
        return 0.0

    return float(eligible.max())


# ---------------------------------------------------------------------------
# Slice evaluation
# ---------------------------------------------------------------------------


def evaluate_slices(
    X_val: pd.DataFrame,
    y_val: pd.Series,
    y_proba: np.ndarray,
    slice_columns: list[str],
    threshold: float,
    beta: float = 2.0,
    min_slice_size: int = 30,
) -> list[SliceResult]:
    """
    Compute per-slice metrics for each value in each slice column.

    Why slices matter:
      Aggregate PR-AUC of 0.42 might hide a Product="Mortgage" slice with
      PR-AUC 0.28 (barely better than random for a 21% positive rate).
      Mortgage complaints may have regulatory implications — this failure
      would not be caught without slice evaluation.

    Only evaluates slices with >= min_slice_size samples to avoid reporting
    unreliable metrics on tiny groups. Slices below this threshold are logged
    as warnings.

    Parameters
    ----------
    X_val : pd.DataFrame — validation features (pre-split, raw)
    y_val : pd.Series — true labels (0/1)
    y_proba : np.ndarray — predicted positive-class probabilities
    slice_columns : list[str] — columns to slice on
    threshold : float — operating threshold for precision/recall/F2 computation
    beta : float — F-beta beta
    min_slice_size : int — slices smaller than this are skipped

    Returns
    -------
    list[SliceResult], one per (column, value) pair.
    """
    results: list[SliceResult] = []
    y_true_arr = y_val.values

    for col in slice_columns:
        if col not in X_val.columns:
            logger.warning("Slice column '%s' not in validation set. Skipping.", col)
            continue

        values = X_val[col].fillna("MISSING").unique()

        for val in sorted(str(v) for v in values):
            mask = X_val[col].fillna("MISSING").astype(str) == val
            n = mask.sum()

            if n < min_slice_size:
                logger.debug(
                    "Slice %s=%s has only %d samples (< %d). Skipping.",
                    col,
                    val,
                    n,
                    min_slice_size,
                )
                continue

            y_t = y_true_arr[mask]
            y_p = y_proba[mask]
            n_pos = int(y_t.sum())

            if n_pos == 0:
                logger.warning(
                    "Slice %s=%s has no positive examples. PR-AUC undefined.",
                    col,
                    val,
                )
                results.append(
                    SliceResult(
                        slice_column=col,
                        slice_value=val,
                        n_samples=n,
                        n_positive=0,
                        pr_auc=None,
                        f2_at_threshold=None,
                        recall_at_threshold=None,
                        precision_at_threshold=None,
                    )
                )
                continue

            slice_pr_auc = float(average_precision_score(y_t, y_p))
            slice_threshold_metrics = compute_threshold_metrics(
                y_t, y_p, threshold, beta=beta
            )

            results.append(
                SliceResult(
                    slice_column=col,
                    slice_value=val,
                    n_samples=int(n),
                    n_positive=n_pos,
                    pr_auc=slice_pr_auc,
                    f2_at_threshold=slice_threshold_metrics.f2,
                    recall_at_threshold=slice_threshold_metrics.recall,
                    precision_at_threshold=slice_threshold_metrics.precision,
                )
            )

    return results


# ---------------------------------------------------------------------------
# Main evaluation entry point
# ---------------------------------------------------------------------------


def run_evaluation(
    pipeline: Pipeline,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    config: TrainingConfig,
    mlflow_run_id: str | None = None,
) -> EvaluationResult:
    """
    Run the full evaluation suite on the validation set.

    Steps:
      1. Predict probabilities on the validation set.
      2. Compute PR-AUC (global, threshold-independent).
      3. Bootstrap 95% CI for PR-AUC.
      4. Tune threshold by maximizing F2 on the validation set.
      5. Compute Recall@target_precision.
      6. Evaluate per-slice metrics.
      7. Log all metrics and a slice summary table to the MLflow run.
      8. Log the imbalance handling decision.

    Parameters
    ----------
    pipeline : sklearn.pipeline.Pipeline
        Fitted pipeline from the train step. predict_proba() gives class probabilities.
    X_val : pd.DataFrame
        Raw validation features (same schema as X_train).
    y_val : pd.Series
        Binary integer labels (0/1) for the validation set.
    config : TrainingConfig
        Loaded training config with evaluation parameters.
    mlflow_run_id : str | None
        If provided, log metrics to this existing MLflow run (same run as the model).
        If None, opens a new run. Should always be provided in pipeline context.

    Returns
    -------
    EvaluationResult — complete structured output for inspection/reporting.
    """
    eval_cfg = config.evaluation

    logger.info(
        "Running evaluation on %d validation rows (%.1f%% positive).",
        len(X_val),
        y_val.mean() * 100,
    )

    # --- Predict ---
    y_proba: np.ndarray = pipeline.predict_proba(X_val)[:, 1]
    y_true: np.ndarray = y_val.values

    # --- Global metrics ---
    pr_auc = float(average_precision_score(y_true, y_proba))
    roc_auc = float(roc_auc_score(y_true, y_proba))

    # --- Bootstrap CI for PR-AUC ---
    pr_auc_ci = bootstrap_ci(
        y_true=y_true,
        y_proba=y_proba,
        metric_fn=average_precision_score,
        n_iters=eval_cfg.bootstrap_iterations,
        seed=config.experiment.random_seed,
    )

    # --- Threshold tuning ---
    optimal_threshold, threshold_metrics = tune_threshold(
        y_true=y_true,
        y_proba=y_proba,
        beta=eval_cfg.f_beta,
    )

    # --- Recall at fixed precision ---
    recall_at_prec = recall_at_fixed_precision(
        y_true=y_true,
        y_proba=y_proba,
        target_precision=0.40,  # Guardrail: precision >= 40%
    )

    # --- Slice evaluation ---
    slice_results = evaluate_slices(
        X_val=X_val,
        y_val=y_val,
        y_proba=y_proba,
        slice_columns=eval_cfg.slice_columns,
        threshold=optimal_threshold,
        beta=eval_cfg.f_beta,
    )

    # --- Imbalance decision log ---
    minority_ratio = float(y_true.mean())
    n_minority = int(y_true.sum())
    imbalance_decision = (
        f"Minority ratio: {minority_ratio:.1%} ({n_minority} examples). "
        f"Decision: class_weight='balanced' (set in config) + threshold tuning. "
        f"SMOTE not applied: {n_minority} > 1000 minority examples; "
        f"high-cardinality categoricals make interpolation nonsensical."
    )
    logger.info("Imbalance decision: %s", imbalance_decision)

    result = EvaluationResult(
        pr_auc=pr_auc,
        roc_auc=roc_auc,
        pr_auc_ci=pr_auc_ci,
        optimal_threshold=optimal_threshold,
        threshold_metrics=threshold_metrics,
        recall_at_target_precision=recall_at_prec,
        target_precision=0.40,
        slice_results=slice_results,
        imbalance_decision=imbalance_decision,
    )

    # --- Log to MLflow ---
    _log_to_mlflow(result, mlflow_run_id, config)

    # --- Print summary ---
    logger.info("=== Evaluation Summary ===")
    for line in result.summary_lines():
        logger.info(line)

    return result


def _log_to_mlflow(
    result: EvaluationResult,
    mlflow_run_id: str | None,
    config: TrainingConfig,
) -> None:
    """
    Log EvaluationResult to MLflow.

    Logs to the existing training run (same run_id) so model artifact
    and metrics appear together in the MLflow UI — no fragmented runs.

    Metrics logged (flat key-value, all visible in MLflow UI):
      - pr_auc, pr_auc_ci_lower, pr_auc_ci_upper
      - roc_auc
      - optimal_threshold
      - precision_at_threshold, recall_at_threshold, f2_at_threshold, f1_at_threshold
      - recall_at_p40 (Recall@Precision>=0.40)
      - slice_{column}_{value}_pr_auc (one metric per slice)

    Tags logged:
      - imbalance_decision (full text)
      - n_val_rows, val_positive_rate
    """
    mlflow.set_experiment(config.experiment.name)

    run_ctx = (
        mlflow.start_run(run_id=mlflow_run_id) if mlflow_run_id else mlflow.start_run()
    )

    with run_ctx:
        # Core metrics
        mlflow.log_metrics(
            {
                "pr_auc": result.pr_auc,
                "pr_auc_ci_lower": result.pr_auc_ci.lower,
                "pr_auc_ci_upper": result.pr_auc_ci.upper,
                "roc_auc": result.roc_auc,
                "optimal_threshold": result.optimal_threshold,
                "precision_at_threshold": result.threshold_metrics.precision,
                "recall_at_threshold": result.threshold_metrics.recall,
                "f2_at_threshold": result.threshold_metrics.f2,
                "f1_at_threshold": result.threshold_metrics.f1,
                "recall_at_p40": result.recall_at_target_precision,
                "flagged_rate": result.threshold_metrics.flagged_rate,
            }
        )

        # Confusion matrix components
        mlflow.log_metrics(
            {
                "tp": result.threshold_metrics.tp,
                "fp": result.threshold_metrics.fp,
                "fn": result.threshold_metrics.fn,
                "tn": result.threshold_metrics.tn,
            }
        )

        # Slice metrics — logged with prefix for easy filtering in MLflow UI
        import re

        for sr in result.slice_results:
            if sr.pr_auc is not None:
                safe_col = sr.slice_column.replace(" ", "_").replace("?", "")
                safe_val = str(sr.slice_value).replace(" ", "_")[:20]
                prefix = f"slice_{safe_col}_{safe_val}"
                prefix = re.sub(r"[^a-zA-Z0-9_\-\.\:\/ ]", "_", prefix)
                mlflow.log_metrics(
                    {
                        f"{prefix}_pr_auc": sr.pr_auc,
                        f"{prefix}_f2": sr.f2_at_threshold or 0.0,
                        f"{prefix}_recall": sr.recall_at_threshold or 0.0,
                        f"{prefix}_precision": sr.precision_at_threshold or 0.0,
                        f"{prefix}_n": sr.n_samples,
                    }
                )

        # Tags
        mlflow.set_tags(
            {
                "imbalance_decision": result.imbalance_decision[
                    :250
                ],  # MLflow tag limit
                "eval_bootstrap_iters": config.evaluation.bootstrap_iterations,
            }
        )

    logger.info(
        "Evaluation metrics logged to MLflow run: %s", mlflow_run_id or "new run"
    )
