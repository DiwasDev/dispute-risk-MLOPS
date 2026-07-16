"""
steps/evaluate.py
=================
ZenML step for model evaluation.

Thin wrapper — all logic lives in core/evaluation.py so that:
1. Tests can run without ZenML installed.
2. The core module is framework-agnostic and reusable.
3. Swapping orchestration frameworks requires updating only this file.

Step contract:
    Inputs : pipeline (Pipeline)   — fitted sklearn pipeline from train step
             X_val   (pd.DataFrame) — raw validation features
             y_val   (pd.Series)    — binary integer labels (0/1)
             mlflow_run_id (str)    — MLflow run ID from train step
             config_path (str)      — path to training_config.yaml
    Outputs: pr_auc (float)         — PR-AUC on validation set
             optimal_threshold (float) — F2-maximized threshold
             evaluation_json (str)  — JSON-serialized EvaluationResult for
                                      downstream steps (e.g., model registry gate)

The evaluate step logs metrics to the SAME MLflow run opened in the train step.
This means model artifact + all metrics appear together in one run in the UI —
not fragmented across two runs.
"""

from __future__ import annotations

import json
import logging

import pandas as pd
from sklearn.pipeline import Pipeline
from zenml import step

from core.evaluation import EvaluationResult, run_evaluation
from core.training import load_config

logger = logging.getLogger(__name__)


@step
def evaluate(
    pipeline: Pipeline,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    mlflow_run_id: str,
    config_path: str = "configs/training_config.yaml",
) -> tuple[float, float, str]:
    """
    Evaluate the fitted pipeline on the held-out validation set.

    Computes and logs to MLflow:
      - PR-AUC with 95% bootstrapped confidence interval
      - ROC-AUC
      - F2, Precision, Recall at the F2-optimized threshold
      - Recall@Precision>=0.40 (guardrail metric)
      - Per-slice PR-AUC for Product, Submitted via, Tags
      - Confusion matrix components (TP, FP, FN, TN)

    Returns the three values most useful to downstream pipeline steps:
      - pr_auc: the primary metric for model comparison
      - optimal_threshold: stored for use by the serving endpoint
      - evaluation_json: full structured result for a model-registry gate step

    Parameters
    ----------
    pipeline : sklearn.pipeline.Pipeline
        Fitted pipeline from the train step.
    X_val : pd.DataFrame
        Raw validation features. Must have the same schema as X_train.
    y_val : pd.Series
        Binary integer labels (0/1).
    mlflow_run_id : str
        MLflow run ID from the train step. Metrics are logged to this run
        so model + metrics are co-located in the MLflow UI.
    config_path : str
        Path to training_config.yaml.

    Returns
    -------
    pr_auc : float
        PR-AUC on validation set. Primary comparison metric.
    optimal_threshold : float
        Decision threshold that maximizes F2 on validation set.
        Use this value in the serving endpoint.
    evaluation_json : str
        JSON string of the key evaluation metrics. Passed to a registry gate
        step to decide whether to promote the model to staging.
    """
    config = load_config(config_path)

    logger.info(
        "Evaluate step: model=%s | val_rows=%d | mlflow_run=%s",
        config.model.active,
        len(X_val),
        mlflow_run_id,
    )

    result: EvaluationResult = run_evaluation(
        pipeline=pipeline,
        X_val=X_val,
        y_val=y_val,
        config=config,
        mlflow_run_id=mlflow_run_id,
    )

    # Serialize key results for downstream use (model registry gate).
    # JSON is the lightest cross-step contract — no custom ZenML materializer needed.
    evaluation_dict = {
        "model_type": config.model.active,
        "snapshot_id": config.data.snapshot_id,
        "mlflow_run_id": mlflow_run_id,
        "pr_auc": result.pr_auc,
        "pr_auc_ci_lower": result.pr_auc_ci.lower,
        "pr_auc_ci_upper": result.pr_auc_ci.upper,
        "roc_auc": result.roc_auc,
        "optimal_threshold": result.optimal_threshold,
        "precision_at_threshold": result.threshold_metrics.precision,
        "recall_at_threshold": result.threshold_metrics.recall,
        "f2_at_threshold": result.threshold_metrics.f2,
        "recall_at_p40": result.recall_at_target_precision,
        "flagged_rate": result.threshold_metrics.flagged_rate,
        "imbalance_decision": result.imbalance_decision,
    }
    evaluation_json = json.dumps(evaluation_dict, indent=2)

    logger.info(
        "Evaluate step complete. PR-AUC=%s | Threshold=%.3f | F2=%.4f",
        str(result.pr_auc_ci),
        result.optimal_threshold,
        result.threshold_metrics.f2,
    )

    return result.pr_auc, result.optimal_threshold, evaluation_json
