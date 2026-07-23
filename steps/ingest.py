"""
steps/ingest.py
===============
ZenML step for data ingestion and validation.

This is a THIN WRAPPER. All logic lives in core/validation.py so that:
1. Tests can run without ZenML installed.
2. The core module is framework-agnostic and reusable.
3. Swapping orchestration frameworks (ZenML → Airflow, etc.) only
   requires updating this file, not the core logic.

The step accepts a source_type parameter ("csv" or "azure") and constructs
the appropriate DataLoaderStrategy, keeping the ZenML interface simple
(string params only — ZenML serialises step inputs/outputs as artifacts).

Step contract:
    Inputs : source_type (str)  — "csv" or "azure"
             csv_path    (str)  — used when source_type == "csv"
             az_container (str) — used when source_type == "azure"
             az_blob      (str) — used when source_type == "azure"
    Outputs: df (pd.DataFrame)  — leakage-free, validated DataFrame
             report_summary (str) — one-line validation summary for logging
"""

from __future__ import annotations

import logging

import pandas as pd
from zenml import step

from core.validation import (
    AzureBlobDataLoader,
    CSVDataLoader,
    load_and_validate,
)

logger = logging.getLogger(__name__)


@step
def ingest_data(
    source_type: str = "csv",
    csv_path: str = "",
    az_container: str = "",
    az_blob: str = "",
) -> tuple[pd.DataFrame, str]:
    """
    Load raw complaint data and validate it against the schema.

    This step enforces:
    - All intake-time features are present.
    - Leakage columns are stripped before any downstream processing.
    - Null rates are within expected thresholds.
    - Target column contains only binary {Yes, No} values.

    Parameters
    ----------
    source_type : str
        "csv"   — load from a local file at csv_path (default).
        "azure" — load from Azure Blob Storage using az_container / az_blob.
                  Requires AZURE_STORAGE_CONNECTION_STRING in the environment.
    csv_path : str
        Absolute or relative path to the raw CSV file.
        Required when source_type == "csv".
    az_container : str
        Azure Blob container name. Required when source_type == "azure".
    az_blob : str
        Blob path inside the container. Required when source_type == "azure".

    Returns
    -------
    df : pd.DataFrame
        Validated, leakage-free DataFrame ready for preprocessing.
    report_summary : str
        One-line validation summary string for audit logging.

    Raises
    ------
    ValueError
        If source_type is not recognised or required params are missing.
    core.validation.ValidationError
        If any hard schema constraint is violated. Pipeline halts.
    """
    source_type = source_type.strip().lower()

    if source_type == "csv":
        if not csv_path:
            raise ValueError("csv_path must be provided when source_type='csv'.")
        loader = CSVDataLoader(path=csv_path)

    elif source_type == "azure":
        if not az_container or not az_blob:
            raise ValueError(
                "az_container and az_blob must be provided when source_type='azure'."
            )
        # Import here so azure-storage-blob is only required when actually used.
        from scripts.azure_connection import AzureConnection  # noqa: PLC0415

        az_conn = AzureConnection()
        client = az_conn.get_blob_service_client()
        loader = AzureBlobDataLoader(
            client=client,
            container_name=az_container,
            blob_name=az_blob,
        )

    else:
        raise ValueError(
            f"Unknown source_type '{source_type}'. Expected 'csv' or 'azure'."
        )

    df, report = load_and_validate(loader, drop_leakage=True, strict=True)

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
