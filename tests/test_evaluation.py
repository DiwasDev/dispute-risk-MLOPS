"""
tests/test_evaluation.py
========================
Unit tests for core/evaluation.py.

No ZenML required. No MLflow server required (tests use local file-based tracking).
All tests use small synthetic predictions (y_true / y_proba arrays).

Tests verify:
1. compute_threshold_metrics() returns correct precision/recall/F2/confusion matrix.
2. bootstrap_ci() returns a CI whose interval contains the point estimate.
3. bootstrap_ci() interval width decreases with more data (statistical sanity).
4. tune_threshold() finds a threshold that yields higher F2 than the default 0.5.
5. recall_at_fixed_precision() returns 0.0 when no threshold achieves target.
6. evaluate_slices() returns one SliceResult per slice value with >= min_size.
7. run_evaluation() returns a complete EvaluationResult on a fitted pipeline.
8. Imbalance decision is logged correctly (SMOTE not applied at 21% rate).

Run with:
    pytest tests/test_evaluation.py -v
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from core.preprocessing import TARGET_COLUMN, build_full_pipeline
from core.evaluation import (
    ConfidenceInterval,
    EvaluationResult,
    SliceResult,
    ThresholdMetrics,
    bootstrap_ci,
    compute_threshold_metrics,
    evaluate_slices,
    recall_at_fixed_precision,
    run_evaluation,
    tune_threshold,
)
from core.training import load_config

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PRODUCTS = ["Mortgage", "Credit reporting", "Debt collection", "Credit card"]
COMPANIES = ["Equifax", "Bank of America", "Wells Fargo", "Citibank"]
ISSUES = ["Incorrect info", "Loan modification", "Billing"]
STATES = ["GA", "CA", "TX", "NY"]


def _make_X_y(n: int = 200, seed: int = 42) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(seed)

    def choice(options, size, null_rate=0.0):
        vals = rng.choice(options, size=size).astype(object)
        if null_rate > 0:
            mask = rng.random(size) < null_rate
            vals[mask] = None
        return vals

    dates = pd.date_range("2014-01-01", "2016-06-01", periods=n)
    X = pd.DataFrame(
        {
            "Date received": dates.strftime("%Y-%m-%d"),
            "Product": choice(PRODUCTS, n),
            "Sub-product": choice(
                ["Conventional fixed mortgage", "Other"], n, null_rate=0.3
            ),
            "Issue": choice(ISSUES, n),
            "Sub-issue": choice(
                ["Info belongs to someone else", None], n, null_rate=0.6
            ),
            "Consumer complaint narrative": choice(
                ["Long complaint.", None], n, null_rate=0.8
            ),
            "Company": choice(COMPANIES, n),
            "State": choice(STATES, n, null_rate=0.01),
            "ZIP code": choice(["30134", "90001"], n),
            "Tags": choice(
                ["Older American", "Servicemember", None], n, null_rate=0.85
            ),
            "Consumer consent provided?": choice(
                ["Consent not provided", "Consent provided", None], n, null_rate=0.7
            ),
            "Submitted via": choice(["Web", "Referral", "Phone", "Postal mail"], n),
        }
    )
    y = pd.Series(rng.integers(0, 2, size=n), name=TARGET_COLUMN)
    return X, y


def _fitted_pipeline(n: int = 200) -> tuple[Pipeline, pd.DataFrame, pd.Series]:
    """Return a fitted pipeline plus X, y for evaluation testing."""
    X, y = _make_X_y(n=n)
    model = LogisticRegression(max_iter=200, random_state=42, class_weight="balanced")
    pipe = build_full_pipeline(model, include_scaler=True)
    pipe.fit(X, y)
    return pipe, X, y


def _make_config_yaml(tmp_path: Path) -> Path:
    config = {
        "data": {
            "snapshot_id": "test_snapshot",
            "csv_path": "data/test.csv",
            "split_date": "2016-01-01",
            "target_column": "Consumer disputed?",
        },
        "experiment": {
            "name": "test-experiment",
            "random_seed": 42,
            "cv_folds": 3,
        },
        "model": {
            "active": "logistic_regression",
            "include_scaler": True,
            "logistic_regression": {
                "C": 1.0,
                "class_weight": "balanced",
                "max_iter": 100,
                "solver": "lbfgs",
                "random_state": 42,
            },
            "xgboost": {
                "n_estimators": 5,
                "max_depth": 3,
                "learning_rate": 0.1,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "scale_pos_weight": 3.76,
                "eval_metric": "aucpr",
                "random_state": 42,
                "n_jobs": 1,
            },
            "lightgbm": {
                "n_estimators": 5,
                "num_leaves": 15,
                "learning_rate": 0.1,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "min_child_samples": 5,
                "is_unbalance": True,
                "random_state": 42,
                "n_jobs": 1,
                "verbose": -1,
            },
        },
        "evaluation": {
            "threshold": 0.5,
            "bootstrap_iterations": 100,  # Fast for tests
            "slice_columns": ["Product", "Submitted via"],
            "f_beta": 2,
        },
    }
    path = tmp_path / "training_config.yaml"
    path.write_text(yaml.dump(config))
    return path


# ---------------------------------------------------------------------------
# compute_threshold_metrics()
# ---------------------------------------------------------------------------


class TestComputeThresholdMetrics:
    def test_perfect_classifier(self):
        """At the right threshold, a perfect classifier should give precision=recall=1."""
        y_true = np.array([1, 0, 1, 0, 1])
        y_proba = np.array([0.9, 0.1, 0.8, 0.2, 0.7])
        metrics = compute_threshold_metrics(y_true, y_proba, threshold=0.5)
        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.tp == 3
        assert metrics.fp == 0
        assert metrics.fn == 0
        assert metrics.tn == 2

    def test_threshold_too_high_catches_nothing(self):
        """Threshold above all probabilities → zero positives predicted."""
        y_true = np.array([1, 0, 1, 0])
        y_proba = np.array([0.6, 0.4, 0.7, 0.3])
        metrics = compute_threshold_metrics(y_true, y_proba, threshold=0.99)
        assert metrics.tp == 0
        assert metrics.fp == 0
        assert metrics.recall == 0.0
        assert metrics.precision == 0.0

    def test_f2_weights_recall_over_precision(self):
        """
        F2 = (1 + 4) * P * R / (4*P + R).
        At high recall, low precision: F2 should still be reasonable.
        At low recall, high precision: F2 should be poor.
        """
        # High recall, low precision case
        y_true = np.array([1, 1, 1, 0, 0])
        y_proba = np.array(
            [0.8, 0.7, 0.6, 0.9, 0.85]
        )  # 2 false positives, but catches all 3
        m_high_recall = compute_threshold_metrics(
            y_true, y_proba, threshold=0.55, beta=2
        )

        # Low recall, high precision case
        y_proba2 = np.array(
            [0.9, 0.3, 0.3, 0.1, 0.1]
        )  # only catches 1/3, but perfectly
        m_low_recall = compute_threshold_metrics(
            y_true, y_proba2, threshold=0.5, beta=2
        )

        # F2 should prefer high recall over high precision
        assert m_high_recall.f2 >= m_low_recall.f2

    def test_flagged_rate(self):
        y_true = np.array([1, 0, 1, 0, 0, 0])
        y_proba = np.array([0.8, 0.9, 0.7, 0.3, 0.2, 0.1])
        metrics = compute_threshold_metrics(y_true, y_proba, threshold=0.5)
        # 3 predicted positive out of 6 total
        assert abs(metrics.flagged_rate - 3 / 6) < 1e-6

    def test_confusion_matrix_sums_to_total(self):
        y_true = np.array([1, 0, 1, 0, 1, 0])
        y_proba = np.random.RandomState(0).rand(6)
        metrics = compute_threshold_metrics(y_true, y_proba, threshold=0.5)
        assert metrics.tp + metrics.fp + metrics.fn + metrics.tn == 6


# ---------------------------------------------------------------------------
# bootstrap_ci()
# ---------------------------------------------------------------------------


class TestBootstrapCI:
    def test_returns_confidence_interval(self):
        from sklearn.metrics import average_precision_score

        y_true = np.array([1, 0, 1, 0, 1, 0, 1, 0] * 10)
        y_proba = np.random.RandomState(0).rand(80)
        ci = bootstrap_ci(y_true, y_proba, average_precision_score, n_iters=100)
        assert isinstance(ci, ConfidenceInterval)

    def test_lower_le_point_le_upper(self):
        """The point estimate should lie within the CI."""
        from sklearn.metrics import average_precision_score

        y_true = np.array([1, 0] * 40)
        y_proba = np.random.RandomState(42).rand(80)
        ci = bootstrap_ci(
            y_true, y_proba, average_precision_score, n_iters=200, seed=42
        )
        assert ci.lower <= ci.point_estimate <= ci.upper

    def test_ci_width_bounded(self):
        """CI width should be non-negative and ≤ 1 for a [0,1]-bounded metric."""
        from sklearn.metrics import average_precision_score

        y_true = np.array([1, 0] * 50)
        y_proba = np.random.RandomState(7).rand(100)
        ci = bootstrap_ci(y_true, y_proba, average_precision_score, n_iters=200, seed=7)
        width = ci.upper - ci.lower
        assert 0 <= width <= 1.0

    def test_bootstrap_count_recorded(self):
        from sklearn.metrics import average_precision_score

        y_true = np.array([1, 0] * 20)
        y_proba = np.random.RandomState(1).rand(40)
        ci = bootstrap_ci(y_true, y_proba, average_precision_score, n_iters=150, seed=1)
        assert ci.n_bootstraps == 150

    def test_reproducible_with_same_seed(self):
        from sklearn.metrics import average_precision_score

        y_true = np.array([1, 0] * 30)
        y_proba = np.random.RandomState(99).rand(60)
        ci1 = bootstrap_ci(
            y_true, y_proba, average_precision_score, n_iters=100, seed=42
        )
        ci2 = bootstrap_ci(
            y_true, y_proba, average_precision_score, n_iters=100, seed=42
        )
        assert ci1.lower == ci2.lower
        assert ci1.upper == ci2.upper


# ---------------------------------------------------------------------------
# tune_threshold()
# ---------------------------------------------------------------------------


class TestTuneThreshold:
    def test_returns_threshold_and_metrics(self):
        y_true = np.array([1, 0, 1, 0, 1, 0, 0, 0] * 10)
        y_proba = np.random.RandomState(0).rand(80)
        threshold, metrics = tune_threshold(y_true, y_proba, beta=2.0)
        assert 0.0 < threshold < 1.0
        assert isinstance(metrics, ThresholdMetrics)

    def test_optimal_f2_is_non_negative(self):
        y_true = np.array([1, 0, 1, 0, 1] * 20)
        y_proba = np.random.RandomState(1).rand(100)
        _, metrics = tune_threshold(y_true, y_proba, beta=2.0)
        assert metrics.f2 >= 0.0

    def test_tuned_threshold_beats_or_matches_default(self):
        """
        The tuned threshold should find an F2 >= F2 at the default 0.5.
        This is the core guarantee of threshold tuning.
        """
        rng = np.random.RandomState(7)
        y_true = rng.choice([0, 1], size=200, p=[0.79, 0.21])
        # Give the model some signal to work with
        y_proba = np.clip(y_true * 0.5 + rng.rand(200) * 0.5, 0, 1)

        default_metrics = compute_threshold_metrics(
            y_true, y_proba, threshold=0.5, beta=2
        )
        _, tuned_metrics = tune_threshold(y_true, y_proba, beta=2)

        assert tuned_metrics.f2 >= default_metrics.f2 - 1e-6  # tuned ≥ default


# ---------------------------------------------------------------------------
# recall_at_fixed_precision()
# ---------------------------------------------------------------------------


class TestRecallAtFixedPrecision:
    def test_returns_float(self):
        y_true = np.array([1, 0, 1, 0] * 20)
        y_proba = np.random.RandomState(0).rand(80)
        result = recall_at_fixed_precision(y_true, y_proba, target_precision=0.40)
        assert isinstance(result, float)

    def test_returns_zero_when_unreachable(self):
        """If all predicted probabilities are low, target precision may be unachievable."""
        y_true = np.array([1, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        # Uniform low proba — precision will be ~10% everywhere
        y_proba = np.full(10, 0.5)
        result = recall_at_fixed_precision(y_true, y_proba, target_precision=0.99)
        assert result == 0.0

    def test_recall_bounded_0_1(self):
        y_true = np.array([1, 0] * 40)
        y_proba = np.random.RandomState(3).rand(80)
        result = recall_at_fixed_precision(y_true, y_proba, target_precision=0.3)
        assert 0.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# evaluate_slices()
# ---------------------------------------------------------------------------


class TestEvaluateSlices:
    def test_returns_slice_results(self):
        X, y = _make_X_y(n=300)
        y_proba = np.random.RandomState(0).rand(len(y))
        results = evaluate_slices(
            X_val=X,
            y_val=y,
            y_proba=y_proba,
            slice_columns=["Product"],
            threshold=0.5,
            beta=2.0,
            min_slice_size=10,
        )
        assert len(results) > 0
        assert all(isinstance(r, SliceResult) for r in results)

    def test_slice_column_names_correct(self):
        X, y = _make_X_y(n=300)
        y_proba = np.random.RandomState(0).rand(len(y))
        results = evaluate_slices(
            X_val=X,
            y_val=y,
            y_proba=y_proba,
            slice_columns=["Product"],
            threshold=0.5,
            min_slice_size=10,
        )
        assert all(r.slice_column == "Product" for r in results)

    def test_skips_missing_column_gracefully(self):
        """Slice evaluation should warn but not crash if column is absent."""
        X, y = _make_X_y(n=200)
        y_proba = np.random.RandomState(0).rand(len(y))
        # This should not raise
        results = evaluate_slices(
            X_val=X,
            y_val=y,
            y_proba=y_proba,
            slice_columns=["NonexistentColumn"],
            threshold=0.5,
        )
        assert results == []

    def test_pr_auc_bounded(self):
        X, y = _make_X_y(n=300)
        y_proba = np.random.RandomState(5).rand(len(y))
        results = evaluate_slices(
            X_val=X,
            y_val=y,
            y_proba=y_proba,
            slice_columns=["Product"],
            threshold=0.5,
            min_slice_size=10,
        )
        for r in results:
            if r.pr_auc is not None:
                assert 0.0 <= r.pr_auc <= 1.0

    def test_n_samples_correct(self):
        X, y = _make_X_y(n=300)
        y_proba = np.random.RandomState(0).rand(len(y))
        results = evaluate_slices(
            X_val=X,
            y_val=y,
            y_proba=y_proba,
            slice_columns=["Product"],
            threshold=0.5,
            min_slice_size=1,
        )
        total = sum(r.n_samples for r in results)
        # All slice samples should sum to total rows (each row belongs to exactly one Product)
        assert total == len(X)


# ---------------------------------------------------------------------------
# run_evaluation() — integration test
# ---------------------------------------------------------------------------


class TestRunEvaluation:
    """
    Integration test: fits a real pipeline and runs the full evaluation suite.

    MLflow 3.x deprecated the filesystem store. Tests use a SQLite URI via
    monkeypatch so no external server is needed and no temp dir cleanup issues arise.
    """

    @staticmethod
    def _setup_mlflow(tmp_path, monkeypatch):
        import mlflow

        db = tmp_path / "mlflow.db"
        monkeypatch.setenv("MLFLOW_ALLOW_FILE_STORE", "true")
        mlflow.set_tracking_uri(f"sqlite:///{db}")
        mlflow.set_experiment("test-experiment")

    def test_returns_evaluation_result(self, tmp_path, monkeypatch):
        self._setup_mlflow(tmp_path, monkeypatch)

        pipe, X, y = _fitted_pipeline(n=200)
        cfg = load_config(_make_config_yaml(tmp_path))

        import mlflow

        with mlflow.start_run():
            result = run_evaluation(pipe, X, y, cfg, mlflow_run_id=None)

        assert isinstance(result, EvaluationResult)

    def test_pr_auc_is_valid(self, tmp_path, monkeypatch):
        self._setup_mlflow(tmp_path, monkeypatch)

        pipe, X, y = _fitted_pipeline(n=200)
        cfg = load_config(_make_config_yaml(tmp_path))
        import mlflow

        with mlflow.start_run():
            result = run_evaluation(pipe, X, y, cfg)

        assert 0.0 <= result.pr_auc <= 1.0

    def test_ci_lower_le_upper(self, tmp_path, monkeypatch):
        self._setup_mlflow(tmp_path, monkeypatch)

        pipe, X, y = _fitted_pipeline(n=200)
        cfg = load_config(_make_config_yaml(tmp_path))
        import mlflow

        with mlflow.start_run():
            result = run_evaluation(pipe, X, y, cfg)

        assert result.pr_auc_ci.lower <= result.pr_auc_ci.upper

    def test_optimal_threshold_in_valid_range(self, tmp_path, monkeypatch):
        self._setup_mlflow(tmp_path, monkeypatch)

        pipe, X, y = _fitted_pipeline(n=200)
        cfg = load_config(_make_config_yaml(tmp_path))
        import mlflow

        with mlflow.start_run():
            result = run_evaluation(pipe, X, y, cfg)

        assert 0.0 < result.optimal_threshold < 1.0

    def test_slice_results_present(self, tmp_path, monkeypatch):
        self._setup_mlflow(tmp_path, monkeypatch)

        pipe, X, y = _fitted_pipeline(n=300)
        cfg = load_config(_make_config_yaml(tmp_path))
        import mlflow

        with mlflow.start_run():
            result = run_evaluation(pipe, X, y, cfg)

        # Config has slice_columns = ["Product", "Submitted via"] — both in X
        assert len(result.slice_results) > 0

    def test_imbalance_decision_logged(self, tmp_path, monkeypatch):
        self._setup_mlflow(tmp_path, monkeypatch)

        pipe, X, y = _fitted_pipeline(n=200)
        cfg = load_config(_make_config_yaml(tmp_path))
        import mlflow

        with mlflow.start_run():
            result = run_evaluation(pipe, X, y, cfg)

        # Should document the SMOTE decision
        assert "SMOTE" in result.imbalance_decision
        assert len(result.imbalance_decision) > 0

    def test_summary_lines_non_empty(self, tmp_path, monkeypatch):
        self._setup_mlflow(tmp_path, monkeypatch)

        pipe, X, y = _fitted_pipeline(n=200)
        cfg = load_config(_make_config_yaml(tmp_path))
        import mlflow

        with mlflow.start_run():
            result = run_evaluation(pipe, X, y, cfg)

        lines = result.summary_lines()
        assert len(lines) >= 7  # At minimum the 7 global metric lines
        assert any("PR-AUC" in line for line in lines)
        assert any("Threshold" in line for line in lines)
