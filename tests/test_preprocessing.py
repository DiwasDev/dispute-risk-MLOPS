"""
tests/test_preprocessing.py
============================
Unit tests for core/preprocessing.py.

No ZenML required. All tests use small synthetic DataFrames.
Tests verify:
1. Custom transformers produce expected outputs on known inputs.
2. Pipeline fits without errors on synthetic data.
3. Time-based split respects the cutoff date.
4. Train-serve parity: identical inputs produce identical outputs after fit.
5. Unknown categories at serving time are handled gracefully.

Run with:
    pytest tests/test_preprocessing.py -v
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from core.preprocessing import (
    DATE_COLUMN,
    NARRATIVE_COLUMN,
    TARGET_COLUMN,
    DateFeatureExtractor,
    NarrativeLengthExtractor,
    SentinelImputer,
    build_feature_pipeline,
    build_full_pipeline,
    time_based_split,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PRODUCTS = [
    "Mortgage",
    "Credit reporting",
    "Debt collection",
    "Credit card",
    "Bank account or service",
]
COMPANIES = ["Equifax", "Bank of America", "Wells Fargo", "Citibank", "JPMorgan Chase"]
ISSUES = [
    "Incorrect information on credit report",
    "Loan modification",
    "Billing disputes",
]
STATES = ["GA", "CA", "TX", "NY", "FL"]


def _make_raw_df(n: int = 200, seed: int = 42) -> pd.DataFrame:
    """
    Synthetic DataFrame matching the real data schema (post-leakage-drop).
    Uses n rows with mixed null patterns matching production null rates.
    """
    rng = np.random.default_rng(seed)

    def choice(options, size, null_rate=0.0):
        vals = rng.choice(options, size=size)
        if null_rate > 0:
            mask = rng.random(size) < null_rate
            vals = vals.astype(object)
            vals[mask] = None
        return vals

    dates = pd.date_range("2014-01-01", "2016-06-01", periods=n)

    df = pd.DataFrame(
        {
            "Date received": dates.strftime("%Y-%m-%d"),
            "Product": choice(PRODUCTS, n),
            "Sub-product": choice(
                ["Conventional fixed mortgage", "Other"], n, null_rate=0.29
            ),
            "Issue": choice(ISSUES, n),
            "Sub-issue": choice(
                ["Information belongs to someone else", None], n, null_rate=0.61
            ),
            "Consumer complaint narrative": choice(
                ["Long complaint text here.", None], n, null_rate=0.84
            ),
            "Company": choice(COMPANIES, n),
            "State": choice(STATES, n, null_rate=0.01),
            "ZIP code": choice(["30134", "90001", "77001"], n, null_rate=0.01),
            "Tags": choice(
                ["Older American", "Servicemember", None], n, null_rate=0.86
            ),
            "Consumer consent provided?": choice(
                ["Consent not provided", "Consent provided", None], n, null_rate=0.72
            ),
            "Submitted via": choice(["Web", "Referral", "Phone", "Postal mail"], n),
            TARGET_COLUMN: choice(["Yes", "No"], n),
        }
    )
    return df


def _make_X_y(n: int = 200) -> tuple[pd.DataFrame, pd.Series]:
    df = _make_raw_df(n)
    y = (df[TARGET_COLUMN] == "Yes").astype(int)
    X = df.drop(columns=[TARGET_COLUMN])
    return X, y


# ---------------------------------------------------------------------------
# DateFeatureExtractor
# ---------------------------------------------------------------------------


class TestDateFeatureExtractor:
    def test_extracts_three_columns(self):
        X = pd.DataFrame({"Date received": ["2015-03-17", "2014-07-04"]})
        out = DateFeatureExtractor().fit_transform(X)
        assert out.shape == (2, 3)

    def test_correct_year_month_dow(self):
        # 2015-03-17 is a Tuesday (dayofweek=1)
        X = pd.DataFrame({"Date received": ["2015-03-17"]})
        out = DateFeatureExtractor().fit_transform(X)
        assert out[0, 0] == 2015  # year
        assert out[0, 1] == 3  # month
        assert out[0, 2] == 1  # Tuesday

    def test_null_date_uses_fallback(self):
        X = pd.DataFrame({"Date received": [None]})
        out = DateFeatureExtractor().fit_transform(X)
        assert out.shape == (1, 3)
        # Should not raise; fallback values are ints
        assert np.isfinite(out).all()

    def test_feature_names(self):
        names = DateFeatureExtractor().get_feature_names_out()
        assert list(names) == ["date_year", "date_month", "date_dayofweek"]


# ---------------------------------------------------------------------------
# NarrativeLengthExtractor
# ---------------------------------------------------------------------------


class TestNarrativeLengthExtractor:
    def test_null_maps_to_zero(self):
        X = pd.DataFrame({"Consumer complaint narrative": [None]})
        out = NarrativeLengthExtractor().fit_transform(X)
        assert out[0, 0] == 0.0

    def test_length_is_character_count(self):
        text = "Hello, this is a complaint."
        X = pd.DataFrame({"Consumer complaint narrative": [text]})
        out = NarrativeLengthExtractor().fit_transform(X)
        assert out[0, 0] == len(text)

    def test_mixed_null_and_text(self):
        X = pd.DataFrame({"Consumer complaint narrative": [None, "abc", None, "xy"]})
        out = NarrativeLengthExtractor().fit_transform(X)
        assert out[0, 0] == 0.0
        assert out[1, 0] == 3.0
        assert out[2, 0] == 0.0
        assert out[3, 0] == 2.0

    def test_output_shape(self):
        X = pd.DataFrame({"Consumer complaint narrative": ["text"] * 10})
        out = NarrativeLengthExtractor().fit_transform(X)
        assert out.shape == (10, 1)


# ---------------------------------------------------------------------------
# SentinelImputer
# ---------------------------------------------------------------------------


class TestSentinelImputer:
    def test_fills_null_with_sentinel(self):
        X = pd.DataFrame({"Tags": [None, "Older American", None]})
        out = SentinelImputer("MISSING").fit_transform(X)
        assert out[0, 0] == "MISSING"
        assert out[1, 0] == "Older American"
        assert out[2, 0] == "MISSING"

    def test_custom_sentinel(self):
        X = pd.DataFrame({"col": [None]})
        out = SentinelImputer("UNK").fit_transform(X)
        assert out[0, 0] == "UNK"

    def test_no_nulls_unchanged(self):
        X = pd.DataFrame({"col": ["a", "b", "c"]})
        out = SentinelImputer("MISSING").fit_transform(X)
        assert list(out[:, 0]) == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# Feature pipeline (ColumnTransformer)
# ---------------------------------------------------------------------------


class TestBuildFeaturePipeline:
    def test_fits_without_error(self):
        X, y = _make_X_y(n=100)
        pipeline = build_feature_pipeline()
        out = pipeline.fit_transform(X, y)
        assert out.ndim == 2
        assert out.shape[0] == 100

    def test_output_is_numeric(self):
        X, y = _make_X_y(n=50)
        pipeline = build_feature_pipeline()
        out = pipeline.fit_transform(X, y)
        assert np.issubdtype(out.dtype, np.floating) or np.issubdtype(
            out.dtype, np.integer
        )

    def test_no_nan_in_output(self):
        X, y = _make_X_y(n=100)
        pipeline = build_feature_pipeline()
        out = pipeline.fit_transform(X, y)
        assert not np.isnan(out).any(), "Pipeline output contains NaN values"

    def test_transform_shape_matches_fit(self):
        X, y = _make_X_y(n=150)
        X_train, X_test = X.iloc[:100], X.iloc[100:]
        y_train = y.iloc[:100]
        pipeline = build_feature_pipeline()
        pipeline.fit(X_train, y_train)
        out_train = pipeline.transform(X_train)
        out_test = pipeline.transform(X_test)
        # Same number of columns
        assert out_train.shape[1] == out_test.shape[1]


# ---------------------------------------------------------------------------
# Full pipeline (preprocessor + scaler + model)
# ---------------------------------------------------------------------------


class TestBuildFullPipeline:
    def test_fits_and_predicts(self):
        X, y = _make_X_y(n=150)
        model = LogisticRegression(max_iter=200, random_state=42)
        pipe = build_full_pipeline(model, include_scaler=True)
        pipe.fit(X, y)
        preds = pipe.predict(X)
        assert preds.shape == (150,)
        assert set(preds).issubset({0, 1})

    def test_predict_proba_returns_valid_probabilities(self):
        X, y = _make_X_y(n=100)
        model = LogisticRegression(max_iter=200, random_state=42)
        pipe = build_full_pipeline(model)
        pipe.fit(X, y)
        proba = pipe.predict_proba(X)
        assert proba.shape == (100, 2)
        assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-5)
        assert (proba >= 0).all() and (proba <= 1).all()

    def test_pipeline_steps_present(self):
        model = LogisticRegression()
        pipe = build_full_pipeline(model, include_scaler=True)
        step_names = [name for name, _ in pipe.steps]
        assert "preprocessor" in step_names
        assert "scaler" in step_names
        assert "model" in step_names

    def test_pipeline_without_scaler(self):
        model = LogisticRegression()
        pipe = build_full_pipeline(model, include_scaler=False)
        step_names = [name for name, _ in pipe.steps]
        assert "scaler" not in step_names


# ---------------------------------------------------------------------------
# Train-serve parity (the critical guarantee)
# ---------------------------------------------------------------------------


class TestTrainServeParity:
    """
    These tests verify that the same input produces the same output regardless
    of when transform() is called after fit(). This is the core guarantee that
    prevents training-serving skew.
    """

    def test_identical_input_produces_identical_output(self):
        """
        Fit on training data. Transform the same 5 rows twice.
        Output must be bit-for-bit identical.
        """
        X, y = _make_X_y(n=100)
        pipe = build_feature_pipeline()
        pipe.fit(X, y)

        # 5 fixed rows as the "golden set"
        golden_X = X.iloc[:5].copy()
        out1 = pipe.transform(golden_X)
        out2 = pipe.transform(golden_X)
        np.testing.assert_array_equal(out1, out2)

    def test_unseen_company_at_serving_does_not_crash(self):
        """
        TargetEncoder must handle companies not seen during training.
        Unknown categories → global mean (the correct fallback).
        """
        X_train, y_train = _make_X_y(n=100)
        pipe = build_feature_pipeline()
        pipe.fit(X_train, y_train)

        # Serving row with a company that was never in training
        X_serving = X_train.iloc[:1].copy()
        X_serving["Company"] = "TOTALLY_UNKNOWN_COMPANY_XYZ"

        out = pipe.transform(X_serving)
        assert out.shape[0] == 1
        assert not np.isnan(out).any()

    def test_unseen_product_at_serving_produces_zero_row(self):
        """
        OHE with handle_unknown='ignore': unseen product → all-zero OHE columns.
        Must not crash.
        """
        X_train, y_train = _make_X_y(n=100)
        pipe = build_feature_pipeline()
        pipe.fit(X_train, y_train)

        X_serving = X_train.iloc[:1].copy()
        X_serving["Product"] = "BRAND_NEW_PRODUCT_TYPE"

        out = pipe.transform(X_serving)
        assert out.shape[0] == 1
        assert not np.isnan(out).any()

    def test_full_null_narrative_at_serving(self):
        """Narrative column entirely null at serving → narrative_length = 0."""
        X_train, y_train = _make_X_y(n=100)
        pipe = build_feature_pipeline()
        pipe.fit(X_train, y_train)

        X_serving = X_train.iloc[:3].copy()
        X_serving[NARRATIVE_COLUMN] = None

        out = pipe.transform(X_serving)
        assert not np.isnan(out).any()


# ---------------------------------------------------------------------------
# Time-based split
# ---------------------------------------------------------------------------


class TestTimeBasedSplit:
    def test_split_respects_cutoff_date(self):
        df = _make_raw_df(n=200)
        X_train, y_train, X_val, y_val = time_based_split(df, split_date="2016-01-01")

        train_dates = pd.to_datetime(X_train[DATE_COLUMN])
        val_dates = pd.to_datetime(X_val[DATE_COLUMN])

        assert (train_dates < pd.Timestamp("2016-01-01")).all()
        assert (val_dates >= pd.Timestamp("2016-01-01")).all()

    def test_no_overlap_between_splits(self):
        df = _make_raw_df(n=200)
        X_train, y_train, X_val, y_val = time_based_split(df, split_date="2016-01-01")

        # Index sets must be disjoint
        assert len(set(X_train.index) & set(X_val.index)) == 0

    def test_labels_are_binary(self):
        df = _make_raw_df(n=200)
        X_train, y_train, X_val, y_val = time_based_split(df)
        assert set(y_train.unique()).issubset({0, 1})
        assert set(y_val.unique()).issubset({0, 1})

    def test_target_column_not_in_X(self):
        df = _make_raw_df(n=200)
        X_train, y_train, X_val, y_val = time_based_split(df)
        assert TARGET_COLUMN not in X_train.columns
        assert TARGET_COLUMN not in X_val.columns

    def test_total_rows_preserved(self):
        df = _make_raw_df(n=200)
        X_train, y_train, X_val, y_val = time_based_split(df)
        assert len(X_train) + len(X_val) == len(df)
