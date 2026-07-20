"""
core/training.py
================
Pure Python training logic. No ZenML imports.

Responsibilities:
  1. Load and validate training_config.yaml into a typed TrainingConfig object.
  2. Build the correct sklearn estimator from config (dispatch by model name).
  3. Wrap the estimator in the full preprocessing pipeline (core/preprocessing.py).
  4. Fit the pipeline on training data.
  5. Log the run to MLflow: params, git commit, snapshot ID, and the model artifact.

## The baseline is non-negotiable

The first model trained must be the simplest plausible model — logistic regression.
It sets the performance floor. Every subsequent experiment is compared against it.
A model that does not beat the baseline in PR-AUC should not advance.

This module is framework-agnostic. The ZenML step (steps/train.py) is a thin
wrapper that calls train_model() and passes artifacts to the next step. Swapping
ZenML for Airflow or Prefect requires only updating steps/train.py.

## MLflow run structure

Each call to train_model() opens a new MLflow run and records:
  - params:   all hyperparameters from config (flat key-value pairs)
  - tags:     snapshot_id, git_commit, model_type, active_model
  - artifacts: full fitted pipeline (model + preprocessing) via mlflow.sklearn.log_model
  - metrics:   empty here — evaluation metrics are logged by core/evaluation.py
                in a separate evaluate step (clear separation of concerns)

The run_id is returned so the evaluate step can log its metrics to the same run.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mlflow
import mlflow.sklearn
import pandas as pd
import yaml
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from core.preprocessing import build_full_pipeline

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Typed config objects (parsed from training_config.yaml)
# ---------------------------------------------------------------------------


@dataclass
class DataConfig:
    snapshot_id: str
    csv_path: str
    split_date: str
    target_column: str


@dataclass
class ExperimentConfig:
    name: str
    random_seed: int
    cv_folds: int


@dataclass
class ModelConfig:
    active: str
    include_scaler: bool
    logistic_regression: dict[str, Any]
    xgboost: dict[str, Any]
    lightgbm: dict[str, Any]


@dataclass
class EvaluationConfig:
    threshold: float
    bootstrap_iterations: int
    slice_columns: list[str]
    f_beta: float


@dataclass
class TrainingConfig:
    data: DataConfig
    experiment: ExperimentConfig
    model: ModelConfig
    evaluation: EvaluationConfig


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def load_config(
    config_path: str | Path = "configs/training_config.yaml",
) -> TrainingConfig:
    """
    Load training_config.yaml into a typed TrainingConfig object.

    Validates required sections exist and provides clear error messages
    if the config is malformed. This catches mistakes before wasting
    compute on a broken training run.

    Parameters
    ----------
    config_path : str | Path
        Path to the YAML config file. Defaults to configs/training_config.yaml.

    Returns
    -------
    TrainingConfig dataclass populated from the YAML.

    Raises
    ------
    FileNotFoundError : If the config file does not exist.
    KeyError : If a required section is missing from the config.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Training config not found at '{path}'. "
            "Expected configs/training_config.yaml. "
            "Create it or pass the correct path."
        )

    with open(path) as f:
        raw = yaml.safe_load(f)

    required_sections = ["data", "experiment", "model", "evaluation"]
    for section in required_sections:
        if section not in raw:
            raise KeyError(
                f"Missing required section '{section}' in config '{path}'. "
                f"Config must contain: {required_sections}"
            )

    cfg = TrainingConfig(
        data=DataConfig(**raw["data"]),
        experiment=ExperimentConfig(**raw["experiment"]),
        model=ModelConfig(
            active=raw["model"]["active"],
            include_scaler=raw["model"]["include_scaler"],
            logistic_regression=raw["model"]["logistic_regression"],
            xgboost=raw["model"]["xgboost"],
            lightgbm=raw["model"]["lightgbm"],
        ),
        evaluation=EvaluationConfig(**raw["evaluation"]),
    )

    logger.info(
        "Config loaded: model=%s | snapshot=%s | split_date=%s",
        cfg.model.active,
        cfg.data.snapshot_id,
        cfg.data.split_date,
    )
    return cfg


# ---------------------------------------------------------------------------
# Git commit hash (Reproducibility Element #3)
# ---------------------------------------------------------------------------


def _get_git_commit() -> str:
    """Return the current HEAD commit hash, or 'unknown' if git is unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Model builder (dispatches by config.model.active)
# ---------------------------------------------------------------------------


def build_model(config: TrainingConfig) -> Any:
    """
    Instantiate the sklearn estimator specified in config.model.active.

    This is the ONLY place where model construction happens. Adding a new
    model type requires only adding a branch here and a params section in
    the config — training step and pipeline require no changes.

    Parameters
    ----------
    config : TrainingConfig

    Returns
    -------
    Unfitted sklearn-compatible estimator.

    Raises
    ------
    ValueError : If config.model.active is not a supported model type.
    """
    active = config.model.active

    if active == "logistic_regression":
        params = config.model.logistic_regression
        logger.info("Building LogisticRegression with params: %s", params)
        return LogisticRegression(**params)

    elif active == "xgboost":
        # Import here — xgboost is an optional heavy dependency.
        # If not installed, fail with a clear message.
        try:
            from xgboost import XGBClassifier
        except ImportError as exc:
            raise ImportError(
                "XGBoost is not installed. Run: pip install xgboost"
            ) from exc

        params = dict(config.model.xgboost)
        # XGBClassifier uses 'random_state' instead of sklearn's convention —
        # it actually accepts both; this is a no-op safety alias.
        logger.info("Building XGBClassifier with params: %s", params)
        return XGBClassifier(**params)

    elif active == "lightgbm":
        try:
            from lightgbm import LGBMClassifier
        except ImportError as exc:
            raise ImportError(
                "LightGBM is not installed. Run: pip install lightgbm"
            ) from exc

        params = dict(config.model.lightgbm)
        logger.info("Building LGBMClassifier with params: %s", params)
        return LGBMClassifier(**params)

    else:
        raise ValueError(
            f"Unsupported model type: '{active}'. "
            "Supported: 'logistic_regression', 'xgboost', 'lightgbm'. "
            "Add a new branch to build_model() and a params section to the config."
        )


# ---------------------------------------------------------------------------
# Training entry point
# ---------------------------------------------------------------------------


def train_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    config: TrainingConfig,
    *,
    mlflow_run_id: str | None = None,
) -> tuple[Pipeline, str]:
    """
    Fit the full pipeline (preprocessing + model) on training data.

    Opens an MLflow run (or resumes an existing one) and logs:
      - All hyperparameters from the active model config (flat key=value)
      - Data snapshot ID and split date as tags
      - Git commit hash as a tag
      - The fitted pipeline artifact (sklearn model + preprocessing frozen together)

    Evaluation metrics are NOT logged here — that is the evaluate step's job.
    This separation means training and evaluation can be re-run independently.

    Parameters
    ----------
    X_train : pd.DataFrame
        Raw training features (leakage-free, not yet preprocessed).
        The pipeline's preprocessing step handles all transformations.
    y_train : pd.Series
        Binary integer labels (0/1).
    config : TrainingConfig
        Fully loaded training config.
    mlflow_run_id : str | None
        If provided, resume an existing MLflow run. Used when training and
        evaluation are in the same orchestrated ZenML pipeline run.

    Returns
    -------
    (fitted_pipeline, run_id) : tuple
        fitted_pipeline : sklearn Pipeline ready for predict_proba()
        run_id : str — MLflow run ID for the evaluate step to log metrics against
    """
    git_commit = _get_git_commit()

    # Build model and wrap in full preprocessing pipeline
    estimator = build_model(config)
    pipeline = build_full_pipeline(
        estimator,
        include_scaler=config.model.include_scaler,
    )

    # Set the MLflow experiment (creates it if it doesn't exist)
    mlflow.set_experiment(config.experiment.name)

    # Flatten hyperparameters for MLflow logging (MLflow expects flat key=value)
    active = config.model.active
    active_params = getattr(config.model, active.replace("-", "_"), {})
    flat_params: dict[str, Any] = {
        f"{active}__{k}": v for k, v in active_params.items()
    }
    flat_params["model_type"] = active
    flat_params["split_date"] = config.data.split_date
    flat_params["include_scaler"] = config.model.include_scaler
    flat_params["random_seed"] = config.experiment.random_seed

    # Open or resume MLflow run
    run_context = (
        mlflow.start_run(run_id=mlflow_run_id) if mlflow_run_id else mlflow.start_run()
    )

    with run_context as run:
        # Log tags (searchable metadata, not metrics)
        mlflow.set_tags(
            {
                "snapshot_id": config.data.snapshot_id,
                "git_commit": git_commit,
                "model_type": active,
                "train_rows": len(X_train),
                "train_positive_rate": f"{y_train.mean():.4f}",
            }
        )

        # Log all hyperparameters
        mlflow.log_params(flat_params)

        logger.info(
            "Training %s on %d rows (%.1f%% positive). "
            "MLflow run: %s | commit: %s | snapshot: %s",
            active,
            len(X_train),
            y_train.mean() * 100,
            run.info.run_id,
            git_commit,
            config.data.snapshot_id,
        )

        # Fit the pipeline — all preprocessing transformers are fitted here.
        # After this call, the pipeline object contains:
        #   - Fitted ColumnTransformer (imputation fill values, OHE vocabularies,
        #     TargetEncoder statistics, scaler mean/std)
        #   - Fitted estimator
        # This is the single artifact that goes to serving.
        pipeline.fit(X_train, y_train)

        logger.info("Pipeline fit complete.")

        # Log the fitted pipeline as an MLflow artifact.
        # mlflow.sklearn.log_model() serializes the pipeline with skops (MLflow 3.x).
        # skops requires explicit trust declarations for custom transformer classes —
        # a security measure so arbitrary code cannot be loaded from untrusted artifacts.
        # We explicitly trust our three custom transformers from core/preprocessing.py.
        # At serving time: mlflow.sklearn.load_model(run_id) → predict_proba().
        _TRUSTED_TYPES = [
            "core.preprocessing.DateFeatureExtractor",
            "core.preprocessing.NarrativeLengthExtractor",
            "core.preprocessing.SentinelImputer",
            "sklearn.linear_model._logistic.LogisticRegression",
            "sklearn.pipeline.Pipeline",
            "sklearn.compose._column_transformer.ColumnTransformer",
            "sklearn.preprocessing._encoders.OneHotEncoder",
            "sklearn.preprocessing._target.TargetEncoder",
            "sklearn.preprocessing._data.StandardScaler",
            "sklearn.impute._base.SimpleImputer",
            "xgboost.core.Booster",
            "xgboost.sklearn.XGBClassifier",
            "lightgbm.basic.Booster",
            "lightgbm.sklearn.LGBMClassifier",
            "collections.OrderedDict",
        ]
        mlflow.sklearn.log_model(
            sk_model=pipeline,
            artifact_path="model",
            registered_model_name=None,  # Promote to registry explicitly in eval step
            input_example=X_train.head(3),
            skops_trusted_types=_TRUSTED_TYPES,
        )

        run_id = run.info.run_id
        logger.info("Model artifact logged. MLflow run_id: %s", run_id)

    return pipeline, run_id
