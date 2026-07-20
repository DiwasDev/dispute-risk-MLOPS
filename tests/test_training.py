"""
tests/test_training.py
======================
Unit tests for core/training.py.

No ZenML required. No MLflow server required (tests use local file-based tracking).
All tests use small synthetic DataFrames.

Tests verify:
1. load_config() parses a valid config correctly.
2. load_config() raises informative errors for missing files / missing sections.
3. build_model() dispatches to the correct estimator class.
4. build_model() raises ValueError for unsupported model types.
5. train_model() fits a pipeline on synthetic data (MLflow runs locally).
6. train_model() returns a fitted pipeline that produces valid probabilities.
7. The returned pipeline is the sklearn.Pipeline wrapping core/preprocessing.py.

Run with:
    pytest tests/test_training.py -v
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from core.preprocessing import TARGET_COLUMN
from core.training import (
    TrainingConfig,
    build_model,
    load_config,
    train_model,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PRODUCTS = ["Mortgage", "Credit reporting", "Debt collection", "Credit card"]
COMPANIES = ["Equifax", "Bank of America", "Wells Fargo", "Citibank"]
ISSUES = ["Incorrect info", "Loan modification", "Billing"]
STATES = ["GA", "CA", "TX", "NY"]


def _make_X_y(n: int = 120, seed: int = 42) -> tuple[pd.DataFrame, pd.Series]:
    """Small synthetic DataFrame matching the schema expected by the pipeline."""
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


def _make_config_yaml(
    tmp_path: Path, model_active: str = "logistic_regression"
) -> Path:
    """Write a minimal valid training_config.yaml to a temp directory."""
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
            "active": model_active,
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
            "bootstrap_iterations": 50,  # Fast for tests
            "slice_columns": ["Product", "Submitted via"],
            "f_beta": 2,
        },
    }
    path = tmp_path / "training_config.yaml"
    path.write_text(yaml.dump(config))
    return path


# ---------------------------------------------------------------------------
# load_config()
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_loads_valid_config(self, tmp_path):
        path = _make_config_yaml(tmp_path)
        cfg = load_config(path)
        assert isinstance(cfg, TrainingConfig)
        assert cfg.model.active == "logistic_regression"
        assert cfg.data.snapshot_id == "test_snapshot"
        assert cfg.experiment.random_seed == 42
        assert cfg.evaluation.f_beta == 2

    def test_missing_file_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Training config not found"):
            load_config(tmp_path / "nonexistent.yaml")

    def test_missing_section_raises_key_error(self, tmp_path):
        # Write config with 'model' section removed
        partial_config = {
            "data": {
                "snapshot_id": "x",
                "csv_path": "x",
                "split_date": "2016-01-01",
                "target_column": "Consumer disputed?",
            },
            "experiment": {"name": "x", "random_seed": 42, "cv_folds": 3},
            # 'model' and 'evaluation' missing
        }
        path = tmp_path / "bad_config.yaml"
        path.write_text(yaml.dump(partial_config))
        with pytest.raises(KeyError, match="model"):
            load_config(path)

    def test_all_model_params_accessible(self, tmp_path):
        path = _make_config_yaml(tmp_path)
        cfg = load_config(path)
        assert "C" in cfg.model.logistic_regression
        assert "n_estimators" in cfg.model.xgboost
        assert "num_leaves" in cfg.model.lightgbm

    def test_slice_columns_parsed_as_list(self, tmp_path):
        path = _make_config_yaml(tmp_path)
        cfg = load_config(path)
        assert isinstance(cfg.evaluation.slice_columns, list)
        assert "Product" in cfg.evaluation.slice_columns


# ---------------------------------------------------------------------------
# build_model()
# ---------------------------------------------------------------------------


class TestBuildModel:
    def test_logistic_regression_returns_lr_instance(self, tmp_path):
        cfg = load_config(_make_config_yaml(tmp_path, "logistic_regression"))
        model = build_model(cfg)
        assert isinstance(model, LogisticRegression)

    def test_logistic_regression_has_correct_params(self, tmp_path):
        cfg = load_config(_make_config_yaml(tmp_path, "logistic_regression"))
        model = build_model(cfg)
        assert model.C == 1.0
        assert model.class_weight == "balanced"
        assert model.solver == "lbfgs"

    def test_xgboost_returns_xgb_classifier(self, tmp_path):
        pytest.importorskip("xgboost")
        cfg = load_config(_make_config_yaml(tmp_path, "xgboost"))
        from xgboost import XGBClassifier

        model = build_model(cfg)
        assert isinstance(model, XGBClassifier)

    def test_lightgbm_returns_lgbm_classifier(self, tmp_path):
        pytest.importorskip("lightgbm")
        cfg = load_config(_make_config_yaml(tmp_path, "lightgbm"))
        from lightgbm import LGBMClassifier

        model = build_model(cfg)
        assert isinstance(model, LGBMClassifier)

    def test_unsupported_model_raises_value_error(self, tmp_path):
        cfg = load_config(_make_config_yaml(tmp_path, "logistic_regression"))
        # Manually patch active to an unsupported value
        cfg.model.active = "random_forest_v99"
        with pytest.raises(ValueError, match="Unsupported model type"):
            build_model(cfg)


# ---------------------------------------------------------------------------
# train_model()
# ---------------------------------------------------------------------------


class TestTrainModel:
    """
    Tests train_model() with a local MLflow SQLite tracking URI so no server is needed.

    MLflow 3.x deprecated the filesystem store; SQLite is the correct local backend.
    MLFLOW_ALLOW_FILE_STORE is also set as a safety net for any transitive calls.
    """

    @staticmethod
    def _setup_mlflow(tmp_path, monkeypatch):
        import mlflow

        db = tmp_path / "mlflow.db"
        monkeypatch.setenv("MLFLOW_ALLOW_FILE_STORE", "true")
        mlflow.set_tracking_uri(f"sqlite:///{db}")

    def test_returns_fitted_pipeline_and_run_id(self, tmp_path, monkeypatch):

        self._setup_mlflow(tmp_path, monkeypatch)

        cfg = load_config(_make_config_yaml(tmp_path))
        X, y = _make_X_y()

        pipeline, run_id = train_model(X, y, cfg)

        assert isinstance(pipeline, Pipeline)
        assert isinstance(run_id, str)
        assert len(run_id) > 0

    def test_fitted_pipeline_predicts_proba(self, tmp_path, monkeypatch):

        self._setup_mlflow(tmp_path, monkeypatch)

        cfg = load_config(_make_config_yaml(tmp_path))
        X, y = _make_X_y()

        pipeline, _ = train_model(X, y, cfg)
        proba = pipeline.predict_proba(X)

        assert proba.shape == (len(X), 2)
        assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-5)
        assert (proba >= 0).all() and (proba <= 1).all()

    def test_pipeline_has_expected_steps(self, tmp_path, monkeypatch):

        self._setup_mlflow(tmp_path, monkeypatch)

        cfg = load_config(_make_config_yaml(tmp_path))
        X, y = _make_X_y()

        pipeline, _ = train_model(X, y, cfg)
        step_names = [name for name, _ in pipeline.steps]

        assert "preprocessor" in step_names
        assert "model" in step_names

    def test_pipeline_no_nan_in_predictions(self, tmp_path, monkeypatch):

        self._setup_mlflow(tmp_path, monkeypatch)

        cfg = load_config(_make_config_yaml(tmp_path))
        X, y = _make_X_y()

        pipeline, _ = train_model(X, y, cfg)
        proba = pipeline.predict_proba(X)

        assert not np.isnan(proba).any(), "Predictions contain NaN values"

    def test_xgboost_trains_successfully(self, tmp_path, monkeypatch):

        pytest.importorskip("xgboost")
        self._setup_mlflow(tmp_path, monkeypatch)

        cfg = load_config(_make_config_yaml(tmp_path, "xgboost"))
        X, y = _make_X_y()

        pipeline, run_id = train_model(X, y, cfg)
        proba = pipeline.predict_proba(X)

        assert proba.shape[0] == len(X)
        assert run_id is not None

    def test_lightgbm_trains_successfully(self, tmp_path, monkeypatch):

        pytest.importorskip("lightgbm")
        self._setup_mlflow(tmp_path, monkeypatch)

        cfg = load_config(_make_config_yaml(tmp_path, "lightgbm"))
        X, y = _make_X_y()

        pipeline, run_id = train_model(X, y, cfg)
        proba = pipeline.predict_proba(X)

        assert proba.shape[0] == len(X)
        assert run_id is not None
