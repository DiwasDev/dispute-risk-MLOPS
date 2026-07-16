"""
tests/test_validation.py
========================
Unit tests for core/validation.py.

No ZenML required — this is the key benefit of separating logic into core/.
All tests use synthetic DataFrames, not the real CSV (fast and deterministic).

Run with:
    pytest tests/test_validation.py -v
"""

from __future__ import annotations

import pandas as pd
import pytest

from core.validation import (
    TARGET_COLUMN,
    LEAKAGE_COLUMNS,
    INTAKE_FEATURES,
    ValidationError,
    ValidationReport,
    compute_null_baseline,
    validate_against_baseline,
    validate_raw_data,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_valid_df(n: int = 100) -> pd.DataFrame:
    """
    Minimal valid DataFrame with all required columns and correct values.
    Uses n rows so we stay above the MIN_ROW_COUNT threshold.
    """
    return pd.DataFrame(
        {
            "Product": ["Credit reporting"] * n,
            "Sub-product": [None] * n,
            "Issue": ["Incorrect information on credit report"] * n,
            "Sub-issue": [None] * n,
            "Consumer complaint narrative": [None] * n,
            "Company": ["Equifax"] * n,
            "State": ["GA"] * n,
            "ZIP code": ["30134"] * n,
            "Tags": [None] * n,
            "Consumer consent provided?": ["Consent not provided"] * n,
            "Submitted via": ["Web"] * n,
            "Date received": ["2015-10-14"] * n,
            TARGET_COLUMN: ["No"] * n,
            "Complaint ID": list(range(n)),
        }
    )


# ---------------------------------------------------------------------------
# Schema checks
# ---------------------------------------------------------------------------


class TestRequiredColumns:
    def test_valid_df_passes(self):
        df = _make_valid_df()
        report = validate_raw_data(df, strict=False)
        assert report.passed, f"Expected pass, got: {report.schema_errors}"

    def test_missing_required_column_fails(self):
        df = _make_valid_df().drop(columns=["Product"])
        report = validate_raw_data(df, strict=False)
        assert not report.passed
        assert any("Product" in e for e in report.schema_errors)

    def test_missing_target_column_fails(self):
        df = _make_valid_df().drop(columns=[TARGET_COLUMN])
        report = validate_raw_data(df, strict=False)
        assert not report.passed
        assert any(TARGET_COLUMN in e for e in report.schema_errors)

    def test_strict_mode_raises_on_failure(self):
        df = _make_valid_df().drop(columns=["Company"])
        with pytest.raises(ValidationError) as exc_info:
            validate_raw_data(df, strict=True)
        assert "Company" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Leakage guard
# ---------------------------------------------------------------------------


class TestLeakageGuard:
    def test_leakage_columns_generate_warnings_not_errors(self):
        df = _make_valid_df()
        # Add one leakage column
        df["Timely response?"] = "Yes"
        report = validate_raw_data(df, strict=False)
        # Should still pass (leakage triggers warnings, not hard errors)
        assert report.passed, "Leakage columns should warn, not fail"
        assert len(report.leakage_warnings) == 1
        assert "Timely response?" in report.leakage_warnings[0]

    def test_all_leakage_columns_trigger_warnings(self):
        df = _make_valid_df()
        for col in LEAKAGE_COLUMNS:
            df[col] = "dummy"
        report = validate_raw_data(df, strict=False)
        assert len(report.leakage_warnings) == len(LEAKAGE_COLUMNS)


# ---------------------------------------------------------------------------
# Target value validation
# ---------------------------------------------------------------------------


class TestTargetValues:
    def test_yes_and_no_pass(self):
        df = _make_valid_df()
        df[TARGET_COLUMN] = ["Yes"] * 50 + ["No"] * 50
        report = validate_raw_data(df, strict=False)
        assert report.passed

    def test_unexpected_target_value_fails(self):
        df = _make_valid_df()
        df.loc[0, TARGET_COLUMN] = "Maybe"
        report = validate_raw_data(df, strict=False)
        assert not report.passed
        assert any("unexpected values" in e for e in report.schema_errors)

    def test_all_no_passes(self):
        """Edge case: one-class batch still valid structurally."""
        df = _make_valid_df()
        df[TARGET_COLUMN] = "No"
        report = validate_raw_data(df, strict=False)
        assert report.passed


# ---------------------------------------------------------------------------
# Null rate checks
# ---------------------------------------------------------------------------


class TestNullRates:
    def test_expected_high_null_narrative_passes(self):
        """Narrative is ~84% null in the real data — this must not fail."""
        df = _make_valid_df(n=200)
        # Set 85% null — within the 90% threshold
        n_null = int(0.85 * len(df))
        df.loc[:n_null, "Consumer complaint narrative"] = None
        report = validate_raw_data(df, strict=False)
        assert report.passed

    def test_unexpected_null_spike_on_critical_column_warns(self):
        """Product at 50% null is above the 1% threshold — should warn."""
        df = _make_valid_df(n=200)
        df.loc[:100, "Product"] = None
        report = validate_raw_data(df, strict=False)
        # Check that the column report has a warning
        product_report = next(
            r for r in report.column_reports if r.column == "Product"
        )
        assert len(product_report.warnings) > 0

    def test_zero_nulls_on_date_received_passes(self):
        df = _make_valid_df()
        assert df["Date received"].isna().sum() == 0
        report = validate_raw_data(df, strict=False)
        date_report = next(
            r for r in report.column_reports if r.column == "Date received"
        )
        assert date_report.null_rate == 0.0


# ---------------------------------------------------------------------------
# Null baseline and drift detection
# ---------------------------------------------------------------------------


class TestNullBaseline:
    def test_compute_baseline_returns_all_columns(self):
        df = _make_valid_df()
        baseline = compute_null_baseline(df)
        for col in df.columns:
            assert col in baseline

    def test_baseline_null_rates_are_correct(self):
        df = _make_valid_df(n=100)
        # Sub-product is all None
        baseline = compute_null_baseline(df)
        assert baseline["Sub-product"] == pytest.approx(1.0)
        assert baseline["Product"] == pytest.approx(0.0)

    def test_drift_detection_flags_large_shift(self):
        df_train = _make_valid_df(n=100)
        baseline = compute_null_baseline(df_train)

        # Simulate serving data where 60% of State is suddenly null
        df_serving = _make_valid_df(n=100)
        df_serving.loc[:60, "State"] = None

        result = validate_against_baseline(df_serving, baseline, drift_threshold=0.05)
        assert "State" in result["drifted_columns"]

    def test_drift_detection_passes_when_stable(self):
        df = _make_valid_df(n=100)
        baseline = compute_null_baseline(df)
        result = validate_against_baseline(df, baseline, drift_threshold=0.05)
        assert result["drifted_columns"] == []


# ---------------------------------------------------------------------------
# ValidationReport
# ---------------------------------------------------------------------------


class TestValidationReport:
    def test_summary_contains_row_count(self):
        df = _make_valid_df(n=150)
        report = validate_raw_data(df, strict=False)
        assert "150" in report.summary()

    def test_summary_shows_pass_status(self):
        df = _make_valid_df()
        report = validate_raw_data(df, strict=False)
        assert "PASS" in report.summary()

    def test_summary_shows_fail_status_on_error(self):
        df = _make_valid_df().drop(columns=["Issue"])
        report = validate_raw_data(df, strict=False)
        assert "FAIL" in report.summary()
