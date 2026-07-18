"""
steps/monitor.py
================
ZenML step for periodic monitoring of the production model.

Thin wrapper — all logic lives in core/drift.py and core/monitoring.py so
that tests can run without ZenML installed and the logic is reusable.

## What this step does

1. Loads a serving window DataFrame (from a provided path or artifact).
2. Computes a MonitoringSnapshot (null rates, prediction distribution, latency).
3. Runs drift detection against the training reference distribution.
4. Checks alert conditions and logs any triggered alerts.
5. Logs the snapshot metrics and drift report to the active MLflow run.
6. Returns structured results for downstream pipeline steps.

## When to run this step

- Daily: scheduled monitoring run on the previous day's serving logs.
- On-demand: after a deploy, to confirm the new model is behaving.
- After incidents: to characterize what changed before and after the event.

## Running standalone

    from steps.monitor import monitor_model
    snapshot, drift_report = monitor_model(
        serving_log_path="logs/serving_2016-03-15.parquet",
        reference_data_path="data/complaints.csv",
        model_version="3",
    )
"""

from __future__ import annotations

import logging

import mlflow
import pandas as pd
from zenml import step

from core.drift import DriftReport, run_drift_detection
from core.monitoring import (
    AlertReport,
    MonitoringSnapshot,
    check_alert_conditions,
    compute_monitoring_snapshot,
)
from core.validation import NULL_RATE_THRESHOLDS

logger = logging.getLogger(__name__)


@step
def monitor_model(
    serving_log_path: str,
    reference_data_path: str = "data/complaints.csv",
    model_version: str = "unknown",
    mlflow_run_id: str | None = None,
    window_start: str = "",
    window_end: str = "",
) -> tuple[MonitoringSnapshot, DriftReport, AlertReport]:
    """
    Monitor production model health for a serving window.

    Parameters
    ----------
    serving_log_path : str
        Path to the serving log file (CSV or Parquet).
        Must contain 'dispute_probability' and optionally 'latency_ms'
        and any input feature columns.
    reference_data_path : str
        Path to the training reference data for drift detection.
    model_version : str
        The model version that produced the serving log.
    mlflow_run_id : str, optional
        If provided, logs monitoring metrics to this MLflow run.
        If None, logs to the currently active MLflow run (if any).
    window_start, window_end : str
        ISO datetime strings bounding the serving window.

    Returns
    -------
    (MonitoringSnapshot, DriftReport, AlertReport)
        Structured monitoring results for downstream pipeline steps
        or reporting dashboards.
    """
    # --- Load serving log ---
    logger.info("Loading serving log from: %s", serving_log_path)
    try:
        if serving_log_path.endswith(".parquet"):
            serving_log = pd.read_parquet(serving_log_path)
        else:
            serving_log = pd.read_csv(serving_log_path, low_memory=False)
        logger.info("Serving log loaded: %d rows, %d columns.", len(serving_log), len(serving_log.columns))
    except Exception as exc:
        logger.error("Failed to load serving log from '%s': %s", serving_log_path, exc)
        raise

    # --- Load reference data ---
    logger.info("Loading reference data from: %s", reference_data_path)
    try:
        reference_df = pd.read_csv(reference_data_path, low_memory=False, nrows=5000)
        logger.info("Reference data loaded: %d rows.", len(reference_df))
    except Exception as exc:
        logger.warning("Failed to load reference data: %s. Drift detection skipped.", exc)
        reference_df = pd.DataFrame()

    # --- Compute monitoring snapshot ---
    snapshot = compute_monitoring_snapshot(
        serving_log=serving_log,
        model_version=model_version,
        baseline_null_rates=NULL_RATE_THRESHOLDS,
        window_start=window_start,
        window_end=window_end,
    )

    # --- Run drift detection ---
    if not reference_df.empty:
        # Only pass features present in both DataFrames
        common_cols = [
            col for col in reference_df.columns
            if col in serving_log.columns
        ]

        # Separate scores if available
        ref_scores = None
        cur_scores = None
        if "dispute_probability" in serving_log.columns:
            cur_scores = serving_log["dispute_probability"].dropna().values
            # Use a sample of reference to compute reference scores (proxy)
            # In production, store validation set scores as an artifact.
            # Here we use reference raw data scores if a model is available.

        drift_report = run_drift_detection(
            reference_df=reference_df[common_cols],
            current_df=serving_log[common_cols],
            reference_scores=ref_scores,
            current_scores=cur_scores,
        )
    else:
        # No reference data — create empty drift report
        from core.drift import DriftReport as _DR
        drift_report = _DR(reference_rows=0, current_rows=len(serving_log))
        logger.warning("Drift detection skipped: no reference data available.")

    # --- Check alert conditions ---
    alert_report = check_alert_conditions(snapshot)

    # --- Log to MLflow ---
    _log_to_mlflow(snapshot, drift_report, alert_report, mlflow_run_id)

    # --- Log summary ---
    logger.info("Monitor step complete. Snapshot: %s", snapshot.summary())
    logger.info("Drift: %s", drift_report.summary())
    logger.info("Alerts: %s", alert_report.summary())

    if alert_report.needs_immediate_action:
        logger.critical(
            "CRITICAL ALERTS DETECTED. Immediate action required. "
            "Critical alerts: %s",
            [str(a) for a in alert_report.critical_alerts],
        )

    return snapshot, drift_report, alert_report


def _log_to_mlflow(
    snapshot: MonitoringSnapshot,
    drift_report: DriftReport,
    alert_report: AlertReport,
    run_id: str | None,
) -> None:
    """Log monitoring metrics to MLflow for trend tracking."""
    try:
        ctx = mlflow.start_run(run_id=run_id) if run_id else mlflow.start_run()
        with ctx:
            # Layer 1: prediction health
            mlflow.log_metrics({
                "monitor.request_count": snapshot.request_count,
                "monitor.prediction_mean": snapshot.prediction_stats.mean,
                "monitor.prediction_std": snapshot.prediction_stats.std,
                "monitor.prediction_p50": snapshot.prediction_stats.p50,
                "monitor.prediction_p90": snapshot.prediction_stats.p90,
                "monitor.positive_rate": snapshot.prediction_stats.positive_rate,
            })

            # Latency
            if snapshot.latency_stats:
                mlflow.log_metrics({
                    "monitor.latency_p50_ms": snapshot.latency_stats.p50_ms,
                    "monitor.latency_p95_ms": snapshot.latency_stats.p95_ms,
                    "monitor.latency_p99_ms": snapshot.latency_stats.p99_ms,
                })

            # Drift
            mlflow.log_metrics({
                "monitor.drift.has_drift": int(drift_report.has_drift),
                "monitor.drift.needs_retraining": int(drift_report.needs_retraining),
                "monitor.drift.drifted_feature_count": len(drift_report.drifted_features),
            })

            # Alerts
            mlflow.log_metrics({
                "monitor.alerts.critical": len(alert_report.critical_alerts),
                "monitor.alerts.high": len(alert_report.high_alerts),
                "monitor.alerts.medium": len(alert_report.medium_alerts),
                "monitor.alerts.total": len(alert_report.alerts),
            })

            mlflow.log_param("monitor.model_version", snapshot.model_version)
            mlflow.log_param("monitor.window_start", snapshot.window_start)
            mlflow.log_param("monitor.window_end", snapshot.window_end)
            mlflow.log_param("monitor.drifted_features", ",".join(drift_report.drifted_features) or "none")

    except Exception as exc:
        # MLflow logging failures should not break the monitoring pipeline
        logger.warning("MLflow logging failed (non-fatal): %s", exc)
