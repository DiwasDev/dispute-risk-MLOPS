"""
steps/train.py
==============
ZenML step for model training.

Thin wrapper — all logic lives in core/training.py so that:
1. Tests can run without ZenML installed.
2. The core module is framework-agnostic and reusable.
3. Swapping orchestration frameworks (ZenML → Airflow, etc.) only
   requires updating this file, not the core logic.

Step contract:
    Inputs : X_train (pd.DataFrame) — raw training features
             y_train (pd.Series)    — binary integer labels (0/1)
             config_path (str)      — path to training_config.yaml
    Outputs: pipeline (Pipeline)    — fitted sklearn pipeline (preprocessing + model)
             mlflow_run_id (str)    — MLflow run ID for the evaluate step to log against

The fitted pipeline is the single serialized artifact that goes to serving.
It contains the fitted preprocessor (imputers, encoders, scaler) AND the model —
no separate preprocessing step at serving time, no risk of training-serving skew.
"""

from __future__ import annotations

import logging

import pandas as pd
from sklearn.pipeline import Pipeline
from zenml import step

from core.training import TrainingConfig, load_config, train_model

logger = logging.getLogger(__name__)


@step
def train(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    config_path: str = "configs/training_config.yaml",
) -> tuple[Pipeline, str]:
    """
    Load config, fit the full preprocessing + model pipeline, log to MLflow.

    Parameters
    ----------
    X_train : pd.DataFrame
        Raw training features from the split_data step.
        Preprocessing (imputation, encoding, scaling) happens inside the pipeline.
    y_train : pd.Series
        Binary integer labels. Must already be 0/1 (done by time_based_split).
    config_path : str
        Path to training_config.yaml. Override for testing or CI runs.

    Returns
    -------
    pipeline : sklearn.pipeline.Pipeline
        Fitted pipeline containing preprocessor + model. This is the artifact
        loaded at serving time via mlflow.sklearn.load_model().
    mlflow_run_id : str
        The MLflow run ID. Passed to the evaluate step so evaluation metrics
        are logged to the same run as the model artifact.
    """
    config: TrainingConfig = load_config(config_path)

    logger.info(
        "Train step: model=%s | snapshot=%s | train_rows=%d | positive_rate=%.1f%%",
        config.model.active,
        config.data.snapshot_id,
        len(X_train),
        y_train.mean() * 100,
    )

    pipeline, mlflow_run_id = train_model(X_train, y_train, config)

    logger.info(
        "Train step complete. MLflow run_id=%s | pipeline steps: %s",
        mlflow_run_id,
        [name for name, _ in pipeline.steps],
    )

    return pipeline, mlflow_run_id
