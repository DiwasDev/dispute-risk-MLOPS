"""
pipelines/training_pipeline.py
===============================
ZenML training pipeline orchestration.

Wires the four steps into a single executable pipeline:
  1. ingest_data   — load CSV, validate schema, drop leakage columns
  2. split_data    — time-based train/validation split
  3. train         — fit preprocessing + model pipeline, log to MLflow
  4. evaluate      — compute metrics, bootstrap CIs, slice evaluation, log to MLflow

## Why this structure matters

Each step is a discrete unit with its own inputs and outputs. If step 3 fails,
you can fix it and rerun from step 3 — ZenML caches steps 1 and 2 automatically.
No reprocessing data, no wasted time.

The pipeline is the reproducibility artifact:
  - Git commit captures the code
  - training_config.yaml captures the configuration
  - MLflow run captures the metrics and model artifact
  - ZenML pipeline run captures which step ran which version

## Running the pipeline

    from pipelines.training_pipeline import run_training_pipeline
    run_training_pipeline(csv_path="data/complaints.csv")

Or from CLI:

    python -m pipelines.training_pipeline

## The baseline experiment

Always run logistic regression first. Set config.model.active = "logistic_regression"
in configs/training_config.yaml (it already defaults to this). This first run
IS the baseline. Never delete this run from MLflow — it is the permanent floor.
"""

from __future__ import annotations

import logging

from zenml import pipeline

from steps.ingest import ingest_data
from steps.preprocess import split_data
from steps.train import train
from steps.evaluate import evaluate

logger = logging.getLogger(__name__)


@pipeline(name="complaint-dispute-training", enable_cache=False)
def training_pipeline(
    csv_path: str = "data/complaints.csv",
    config_path: str = "configs/training_config.yaml",
    split_date: str = "2016-01-01",
) -> None:
    """
    End-to-end training pipeline from raw CSV to evaluated model in MLflow.

    Parameters
    ----------
    csv_path : str
        Path to the raw complaints CSV. Passed to the ingest step.
    config_path : str
        Path to training_config.yaml. Passed to train and evaluate steps.
    split_date : str
        Time-based split cutoff date. Passed to the split step.
        Override here OR in config — split_data step uses this parameter directly.
        Keep in sync with config.data.split_date for reproducibility.
    """
    # Step 1: Load + validate
    df, validation_summary = ingest_data(csv_path=csv_path)

    # Step 2: Time-based split
    X_train, y_train, X_val, y_val = split_data(df=df, split_date=split_date)

    # Step 3: Train
    # Returns fitted pipeline AND the MLflow run_id so the evaluate step
    # logs its metrics to the same run as the model artifact.
    pipeline_artifact, mlflow_run_id = train.with_options(
        experiment_tracker="mlflow_tracker"
    )(
        X_train=X_train,
        y_train=y_train,
        config_path=config_path,
    )

    # Step 4: Evaluate
    # Logs PR-AUC, F2, Recall@Precision, bootstrapped CIs, and slice metrics
    # to the MLflow run opened in the train step.
    evaluate.with_options(experiment_tracker="mlflow_tracker")(
        pipeline=pipeline_artifact,
        X_val=X_val,
        y_val=y_val,
        mlflow_run_id=mlflow_run_id,
        config_path=config_path,
    )


if __name__ == "__main__":
    """
    Direct execution for local development:
        python -m pipelines.training_pipeline

    This runs the baseline (logistic_regression) by default.
    To run a different model, edit configs/training_config.yaml:
        model:
          active: "xgboost"
    """
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    logger.info("Starting training pipeline (baseline: logistic_regression)")
    training_pipeline()
