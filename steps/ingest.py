"""
steps/ingest.py
===============
ZenML step for data ingestion and validation.

This is a THIN WRAPPER. All logic lives in core/validation.py so that:
1. Tests can run without ZenML installed.
2. The core module is framework-agnostic and reusable.
3. Swapping orchestration frameworks (ZenML → Airflow, etc.) only
   requires updating this file, not the core logic.

Step contract:
    Input  : csv_path (str) — path to raw data CSV
    Outputs: df (pd.DataFrame) — leakage-free, validated DataFrame
             report_summary (str) — one-line validation summary for logging
"""

from __future__ import annotations

import logging

import pandas as pd
from zenml import step

from core.validation import (
    load_and_validate,
)

logger = logging.getLogger(__name__)


@step
def ingest_data(csv_path: str) -> tuple[pd.DataFrame, str]:
    """
    Load raw complaint CSV and validate it against the schema.

    This step enforces:
    - All intake-time features are present.
    - Leakage columns are stripped before any downstream processing.
    - Null rates are within expected thresholds.
    - Target column contains only binary {Yes, No} values.

    Parameters
    ----------
    csv_path : str
        Absolute or relative path to the raw CSV file.

    Returns
    -------
    df : pd.DataFrame
        Validated, leakage-free DataFrame ready for preprocessing.
    report_summary : str
        One-line validation summary string for audit logging.

    Raises
    ------
    core.validation.ValidationError
        If any hard schema constraint is violated. Pipeline halts.
    """
    df, report = load_and_validate(csv_path, drop_leakage=True, strict=True)

    summary = report.summary()
    logger.info("Ingestion step complete. %s", summary)

    # Log per-column null rates at INFO level for visibility in ZenML UI
    for col_report in report.column_reports:
        logger.info(
            "  %s | null_rate=%.1f%% | cardinality=%d | dtype=%s",
            col_report.column,
            col_report.null_rate * 100,
            col_report.unique_count,
            col_report.dtype,
        )

    if report.leakage_warnings:
        logger.warning(
            "Leakage columns were found and dropped: %s",
            [w for w in report.leakage_warnings],
        )

    return df, summary
