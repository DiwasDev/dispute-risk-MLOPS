"""
core/validation.py
==================
Pure Python schema validation and data quality checks.

No ZenML or MLflow imports here — this module must be fully testable
without any ML framework installed. Steps are thin wrappers; logic lives here.

Design principles:
- Fail fast and loudly: a ValidationError stops the pipeline immediately.
- Log every anomaly: silent degradation is the #1 production failure mode.
- Baseline null rates from training data to catch upstream pipeline breaks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema definition
# ---------------------------------------------------------------------------

# Features available at intake time (before any resolution work begins).
# Source: problem_statement.md — "Features (intake-time only)"
INTAKE_FEATURES: list[str] = [
    "Product",
    "Sub-product",
    "Issue",
    "Sub-issue",
    "Consumer complaint narrative",
    "Company",
    "State",
    "ZIP code",
    "Tags",
    "Consumer consent provided?",
    "Submitted via",
    "Date received",
]

TARGET_COLUMN: str = "Consumer disputed?"
COMPLAINT_ID_COLUMN: str = "Complaint ID"

# These columns are known at resolution time only — never at intake.
# Including them would be data leakage: the model would learn resolution
# patterns rather than intake-time risk signals.
LEAKAGE_COLUMNS: list[str] = [
    "Company public response",
    "Company response to consumer",
    "Timely response?",
    "Date sent to company",
]

# Expected dtypes after loading (before type coercion).
# "object" covers strings and mixed types — pandas default for text.
EXPECTED_DTYPES: dict[str, str] = {
    "Product": "object",
    "Sub-product": "object",
    "Issue": "object",
    "Sub-issue": "object",
    "Consumer complaint narrative": "object",
    "Company": "object",
    "State": "object",
    "ZIP code": "object",  # ZIP codes can have leading zeros — keep as string
    "Tags": "object",
    "Consumer consent provided?": "object",
    "Submitted via": "object",
    "Date received": "object",  # Will be parsed to datetime downstream
    TARGET_COLUMN: "object",
}

# Null rate thresholds (max fraction of nulls allowed before alerting).
# Derived from problem_statement.md data summary.
#   - Consumer complaint narrative: ~84% null — this is expected; baseline it.
#   - Target: must be present for supervised learning.
#   - Core categorical features: allow up to 20% missing before alerting.
NULL_RATE_THRESHOLDS: dict[str, float] = {
    "Product": 0.01,
    "Issue": 0.01,
    "Company": 0.01,
    "Submitted via": 0.01,
    "Date received": 0.0,
    TARGET_COLUMN: 0.0,
    "Sub-product": 0.60,
    "Sub-issue": 0.80,
    "Consumer complaint narrative": 0.90,  # 84% null is normal; cap at 90%
    "Tags": 0.80,
    "Consumer consent provided?": 0.80,
    "State": 0.05,
    "ZIP code": 0.10,
}

# Allowed values for the target column (binary classification).
TARGET_ALLOWED_VALUES: set[str] = {"Yes", "No"}

# Expected cardinality bounds (min, max unique values).
# Prevents join errors that create unexpected categories.
# Note: TARGET_COLUMN is excluded here — binary value validation is handled
# separately by _check_target_values(), which is more precise. Cardinality
# on the target can be 1 in filtered batches (e.g., all "No") and that is
# structurally valid as long as the value is in the allowed set.
CARDINALITY_BOUNDS: dict[str, tuple[int, int]] = {
    "Product": (1, 50),
    "Submitted via": (1, 20),
    "Consumer consent provided?": (1, 10),
    "Tags": (1, 20),
}

# Minimum record count for a valid dataset batch.
# Training set has ~358K rows; flag if batch is suspiciously small.
MIN_ROW_COUNT: int = 100


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------


@dataclass
class ColumnQualityReport:
    """Quality metrics for a single column."""

    column: str
    null_rate: float
    unique_count: int
    dtype: str
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0


@dataclass
class ValidationReport:
    """Aggregate result of a full schema validation run."""

    row_count: int
    column_reports: list[ColumnQualityReport] = field(default_factory=list)
    schema_errors: list[str] = field(default_factory=list)
    leakage_warnings: list[str] = field(default_factory=list)
    global_warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True only if there are zero schema errors and zero column errors."""
        column_errors = any(not r.passed for r in self.column_reports)
        return len(self.schema_errors) == 0 and not column_errors

    def summary(self) -> str:
        """Human-readable one-paragraph summary."""
        status = "PASS" if self.passed else "FAIL"
        col_failures = [r.column for r in self.column_reports if not r.passed]
        lines = [
            f"[{status}] Rows: {self.row_count:,}",
            f"Schema errors: {len(self.schema_errors)}",
            f"Column failures: {col_failures or 'none'}",
            f"Leakage warnings: {len(self.leakage_warnings)}",
            f"Global warnings: {len(self.global_warnings)}",
        ]
        return " | ".join(lines)


class ValidationError(Exception):
    """Raised when validation fails hard enough to halt the pipeline."""

    def __init__(self, report: ValidationReport) -> None:
        self.report = report
        super().__init__(
            f"Data validation failed.\n{report.summary()}\n"
            f"Schema errors: {report.schema_errors}\n"
            f"Column errors: {[e for r in report.column_reports for e in r.errors]}"
        )


# ---------------------------------------------------------------------------
# Core validation logic
# ---------------------------------------------------------------------------


def _check_leakage_columns(df: pd.DataFrame) -> list[str]:
    """
    Check for resolution-time columns that must never appear in the training
    or serving pipeline. Returns warnings (not errors) so the pipeline can
    drop them rather than halt — but log loudly.

    Why: including Company response or Timely response at training time means
    the model learns from information that doesn't exist at complaint intake.
    It would achieve great offline metrics and fail silently in production.
    """
    found = [col for col in LEAKAGE_COLUMNS if col in df.columns]
    warnings = []
    for col in found:
        msg = (
            f"LEAKAGE GUARD: Column '{col}' is a resolution-time feature and "
            f"must not enter the feature matrix. Drop it immediately."
        )
        logger.warning(msg)
        warnings.append(msg)
    return warnings


def _check_required_columns(df: pd.DataFrame) -> list[str]:
    """
    Verify all intake features and the target column are present.

    Why: a renamed or dropped column doesn't cause a crash — pandas just
    returns NaN for the missing column. Schema checks catch this at the
    boundary before bad data propagates through training.
    """
    required = INTAKE_FEATURES + [TARGET_COLUMN]
    missing = [col for col in required if col not in df.columns]
    errors = []
    for col in missing:
        msg = f"Required column missing: '{col}'"
        logger.error(msg)
        errors.append(msg)
    return errors


def _check_row_count(df: pd.DataFrame) -> list[str]:
    """Alert if the batch is suspiciously small (possible partial data pull)."""
    warnings = []
    if len(df) < MIN_ROW_COUNT:
        msg = (
            f"Row count {len(df):,} is below minimum threshold {MIN_ROW_COUNT:,}. "
            f"This may indicate a partial data pull or a pipeline failure upstream."
        )
        logger.warning(msg)
        warnings.append(msg)
    return warnings


def _check_target_values(df: pd.DataFrame) -> list[str]:
    """
    Validate the target column contains only allowed binary values.

    Why: if 'Consumer disputed?' arrives with unexpected values (e.g., 'N/A',
    'Unknown'), encoding it will silently produce wrong labels. Catch it here.
    """
    errors = []
    if TARGET_COLUMN not in df.columns:
        return errors  # Already caught by required-columns check

    # Strip whitespace and check against allowed set
    unique_vals = set(df[TARGET_COLUMN].dropna().astype(str).str.strip().unique())
    unexpected = unique_vals - TARGET_ALLOWED_VALUES
    if unexpected:
        msg = (
            f"Target column '{TARGET_COLUMN}' contains unexpected values: "
            f"{unexpected}. Expected: {TARGET_ALLOWED_VALUES}."
        )
        logger.error(msg)
        errors.append(msg)
    return errors


def _check_column_quality(
    df: pd.DataFrame, column: str
) -> ColumnQualityReport:
    """
    Run quality checks for a single column:
    - Null rate vs threshold
    - Cardinality bounds
    - Dtype check (loose — object covers most text features)
    """
    series = df[column] if column in df.columns else pd.Series(dtype="object")
    null_rate = series.isna().mean() if len(series) > 0 else 1.0
    unique_count = series.nunique()
    dtype = str(series.dtype)
    warnings: list[str] = []
    errors: list[str] = []

    # Null rate check
    threshold = NULL_RATE_THRESHOLDS.get(column)
    if threshold is not None and null_rate > threshold:
        msg = (
            f"'{column}': null rate {null_rate:.1%} exceeds threshold "
            f"{threshold:.1%}. This may signal an upstream pipeline break."
        )
        logger.warning(msg)
        warnings.append(msg)

    # Cardinality bounds check
    # Skip when null_rate == 1.0: the column is entirely null, which is already
    # flagged by the null rate check above. Checking cardinality on an all-null
    # column always returns 0, which would produce a spurious error/warning.
    bounds = CARDINALITY_BOUNDS.get(column)
    if bounds is not None and null_rate < 1.0:
        lo, hi = bounds
        if not (lo <= unique_count <= hi):
            msg = (
                f"'{column}': cardinality {unique_count} is outside expected "
                f"bounds [{lo}, {hi}]. Possible join error or encoding problem."
            )
            # Treat cardinality violation as an error for the target; warning for features
            if column == TARGET_COLUMN:
                logger.error(msg)
                errors.append(msg)
            else:
                logger.warning(msg)
                warnings.append(msg)

    return ColumnQualityReport(
        column=column,
        null_rate=null_rate,
        unique_count=unique_count,
        dtype=dtype,
        warnings=warnings,
        errors=errors,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_raw_data(df: pd.DataFrame, *, strict: bool = True) -> ValidationReport:
    """
    Run full schema and quality validation on raw complaint data.

    Parameters
    ----------
    df : pd.DataFrame
        Raw loaded DataFrame (before any preprocessing).
    strict : bool
        If True (default), raise ValidationError when validation fails.
        Set False only in testing or exploratory contexts.

    Returns
    -------
    ValidationReport
        Structured report with per-column quality metrics and overall pass/fail.

    Raises
    ------
    ValidationError
        When strict=True and the report does not pass.
    """
    logger.info("Starting schema validation. DataFrame shape: %s", df.shape)

    report = ValidationReport(row_count=len(df))

    # --- Leakage guard (warns but does not fail — drop columns downstream) ---
    report.leakage_warnings = _check_leakage_columns(df)

    # --- Required column presence (hard errors) ---
    report.schema_errors = _check_required_columns(df)

    # --- Row count sanity ---
    report.global_warnings.extend(_check_row_count(df))

    # --- Target value validation ---
    target_errors = _check_target_values(df)
    report.schema_errors.extend(target_errors)

    # --- Per-column quality checks ---
    columns_to_check = [
        col for col in INTAKE_FEATURES + [TARGET_COLUMN] if col in df.columns
    ]
    for col in columns_to_check:
        col_report = _check_column_quality(df, col)
        report.column_reports.append(col_report)

    logger.info("Validation complete. %s", report.summary())

    if strict and not report.passed:
        raise ValidationError(report)

    return report


def load_and_validate(
    csv_path: str,
    *,
    drop_leakage: bool = True,
    strict: bool = True,
) -> tuple[pd.DataFrame, ValidationReport]:
    """
    Load raw CSV data and immediately validate it.

    This is the single entry point for data loading. It enforces the
    following contract at the boundary:
    1. Schema is valid (required columns present, target is binary).
    2. Leakage columns are removed before any downstream processing.
    3. Quality anomalies are logged and surfaced in the report.

    Parameters
    ----------
    csv_path : str
        Path to the raw CSV file.
    drop_leakage : bool
        If True (default), leakage columns are dropped from the returned
        DataFrame. Set False only for audit/debugging.
    strict : bool
        Passed to validate_raw_data. Controls whether validation failures
        raise an exception or return a failed report.

    Returns
    -------
    (df, report) : tuple[pd.DataFrame, ValidationReport]
        Cleaned DataFrame (leakage columns dropped) and the validation report.
    """
    logger.info("Loading data from: %s", csv_path)
    df = pd.read_csv(csv_path, low_memory=False)
    logger.info("Loaded %d rows, %d columns.", len(df), len(df.columns))

    report = validate_raw_data(df, strict=strict)

    if drop_leakage:
        cols_to_drop = [col for col in LEAKAGE_COLUMNS if col in df.columns]
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)
            logger.info(
                "Dropped %d leakage column(s): %s", len(cols_to_drop), cols_to_drop
            )

    # Also drop Complaint ID — it's an identifier, not a feature.
    if COMPLAINT_ID_COLUMN in df.columns:
        df = df.drop(columns=[COMPLAINT_ID_COLUMN])
        logger.info("Dropped identifier column: '%s'", COMPLAINT_ID_COLUMN)

    return df, report


def compute_null_baseline(df: pd.DataFrame) -> dict[str, float]:
    """
    Compute and return null rates per column from a reference dataset
    (typically training data).

    Store this as an artifact and compare against it in production to
    detect upstream pipeline failures. A column that was 2% null during
    training but is now 40% null at serving time is a pipeline problem,
    not a real-world change.
    """
    baseline = {col: float(df[col].isna().mean()) for col in df.columns}
    logger.info(
        "Null baseline computed for %d columns. Top missing: %s",
        len(baseline),
        sorted(baseline.items(), key=lambda x: -x[1])[:5],
    )
    return baseline


def validate_against_baseline(
    df: pd.DataFrame,
    baseline: dict[str, float],
    *,
    drift_threshold: float = 0.05,
) -> dict[str, Any]:
    """
    Compare current null rates against a saved training baseline.

    A drift of >5pp (absolute) on any column triggers a warning.
    This is a lightweight completeness check — full distribution drift
    detection belongs in the monitoring layer (Evidently).

    Parameters
    ----------
    df : pd.DataFrame
        Current batch to check.
    baseline : dict[str, float]
        Saved null rates from training data.
    drift_threshold : float
        Absolute difference in null rate that triggers a warning.

    Returns
    -------
    dict with keys "drifted_columns" and "details".
    """
    drifted = {}
    for col, base_rate in baseline.items():
        if col not in df.columns:
            continue
        current_rate = float(df[col].isna().mean())
        delta = current_rate - base_rate
        if abs(delta) > drift_threshold:
            msg = (
                f"'{col}': null rate drifted from baseline {base_rate:.1%} "
                f"to {current_rate:.1%} (delta {delta:+.1%})."
            )
            logger.warning(msg)
            drifted[col] = {
                "baseline": base_rate,
                "current": current_rate,
                "delta": delta,
            }
    return {"drifted_columns": list(drifted.keys()), "details": drifted}
