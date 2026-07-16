"""
core/preprocessing.py
=====================
Pure Python preprocessing logic. No ZenML imports.

This module builds the sklearn.Pipeline that is the single serialized object
used in both training and serving. Identical preprocessing is guaranteed by
the pipeline — there is no separate serving code path, no recomputed statistics,
no chance of train-serve skew from this module.

## Why sklearn.Pipeline is non-negotiable for production

Training-serving skew is the #1 silent failure in production ML. The model
sees different features in production than it learned on. No errors — just
quietly wrong predictions. sklearn.Pipeline serializes every fitted transformer
(imputation fill values, OHE vocabularies, TargetEncoder encodings) into a
single artifact. Load that artifact at serving time and preprocessing is
guaranteed identical.

## Feature strategy (derived from EDA)

Null handling — each column's strategy is deliberate:
- Categorical with >60% null (Tags, narrative consent, Sub-issue, Sub-product):
  sentinel fill ("MISSING") — the absence is informative.
- Low-null categoricals (State, ZIP): mode fill — rare, not informative.

Encoding:
- Low-cardinality (<= 15 unique): OneHotEncoder — sparse, interpretable.
  Product(12), Submitted via(6), Tags(3+MISSING=4),
  Consumer consent provided?(4+MISSING=5).
- High-cardinality (> 15 unique): TargetEncoder with empirical Bayes smoothing.
  Company(3,064), Issue(95), Sub-issue(67+MISSING), State(62),
  Sub-product(47+MISSING).
  Smoothing prevents overfitting on rare categories. Unknown categories at
  serving time fall back to the global mean — safe default behavior.
- ZIP code: dropped (24K cardinality, State already covers geography).

Date features: year, month, day_of_week extracted from 'Date received'.
Text feature: narrative character length (0 if null) — proxy for complaint
detail without NLP complexity.

Scaling: StandardScaler on numeric outputs for logistic regression compatibility.
Tree-based models are scale-invariant, but including the scaler costs nothing
and keeps the pipeline model-agnostic.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler, TargetEncoder

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column group definitions
# ---------------------------------------------------------------------------

# Target column — needed for TargetEncoder fit; excluded from X.
TARGET_COLUMN = "Consumer disputed?"

# Low-cardinality categoricals: OHE (≤15 unique values after sentinel fill).
# handle_unknown='ignore' → unseen categories at serving get all-zero row
# (no crash, no information leakage from future categories).
LOW_CARD_CATS: list[str] = [
    "Product",          # 12 unique
    "Submitted via",    # 6 unique
    "Tags",             # 3 unique + MISSING sentinel
    "Consumer consent provided?",  # 4 unique + MISSING sentinel
]

# High-cardinality categoricals: TargetEncoder with empirical Bayes smoothing.
# smooth='auto' selects the smoothing factor via cross-validation inside fit().
# Unknown categories at serving → global mean (safe fallback).
HIGH_CARD_CATS: list[str] = [
    "Company",      # 3,064 unique — target encoding prevents 3K OHE columns
    "Issue",        # 95 unique
    "Sub-issue",    # 67 unique + MISSING sentinel
    "State",        # 62 unique
    "Sub-product",  # 47 unique + MISSING sentinel
]

# Columns that get sentinel ("MISSING") fill for nulls.
# These have high null rates where absence carries signal.
SENTINEL_FILL_COLS: list[str] = [
    "Tags",
    "Consumer consent provided?",
    "Sub-issue",
    "Sub-product",
]

# Columns that get mode fill for nulls (rare nulls, not informative).
MODE_FILL_COLS: list[str] = [
    "State",
    "Company",   # <0.01% null — safe to mode fill
    "Issue",     # 0% null in practice
]

# Date column: decomposed into numeric features.
DATE_COLUMN = "Date received"

# Text column: length extracted as numeric feature.
NARRATIVE_COLUMN = "Consumer complaint narrative"

# Drop this — too high cardinality, geographically redundant with State.
DROP_COLS: list[str] = ["ZIP code"]

# All feature columns (after leakage/ID drop by validation step).
ALL_FEATURE_COLS: list[str] = (
    LOW_CARD_CATS
    + HIGH_CARD_CATS
    + [DATE_COLUMN, NARRATIVE_COLUMN]
)


# ---------------------------------------------------------------------------
# Custom transformers (pure Python / numpy — no sklearn subclasses with state
# beyond what __init__ stores)
# ---------------------------------------------------------------------------


class DateFeatureExtractor(BaseEstimator, TransformerMixin):
    """
    Extract year, month, day_of_week from a date string column.

    Why not cyclical encoding here? Day-of-week has very weak signal in
    this complaint dataset (complaints filed any day of the week). Year and
    month capture secular trends (complaint volumes grew over 2011-2016) and
    seasonality. We keep it simple: three integers. If cyclical encoding adds
    value, it belongs in a feature iteration, not the MVP.

    Implements the sklearn transformer interface so it integrates into
    Pipeline and ColumnTransformer without special handling.
    """

    def __init__(self, date_format: str = "%Y-%m-%d") -> None:
        self.date_format = date_format

    def fit(self, X: pd.DataFrame | np.ndarray, y=None) -> "DateFeatureExtractor":
        # Stateless — nothing to learn from training data.
        return self

    def transform(
        self, X: pd.DataFrame | np.ndarray
    ) -> np.ndarray:
        """Return (n, 3) array: [year, month, day_of_week]."""
        # ColumnTransformer passes a 2D array; we want the first column.
        if isinstance(X, np.ndarray):
            col = pd.Series(X[:, 0])
        else:
            col = X.iloc[:, 0]

        dates = pd.to_datetime(col, errors="coerce")
        result = np.column_stack([
            dates.dt.year.fillna(2013).astype(int),   # fallback: dataset midpoint
            dates.dt.month.fillna(6).astype(int),
            dates.dt.dayofweek.fillna(2).astype(int),
        ])
        return result

    def get_feature_names_out(self, input_features=None) -> np.ndarray:
        return np.array(["date_year", "date_month", "date_dayofweek"])


class NarrativeLengthExtractor(BaseEstimator, TransformerMixin):
    """
    Extract narrative character length as a numeric feature.

    Why length instead of TF-IDF or embeddings? The EDA shows: complaints
    WITH a narrative have a 25.2% dispute rate vs 20.5% without one — a 4.7pp
    lift. The presence and length of a narrative is a meaningful signal.
    Full NLP (embeddings, TF-IDF on 55K unique narratives) is deferred per
    architecture.md — it's in the "deferred" list for good reason: it adds
    complexity and serving latency without a proven incremental lift over
    this simpler proxy.

    Null (no narrative) → 0 length. This encodes the absence as the minimum
    value, which is true and preserves the binary signal (has/doesn't have
    a narrative).
    """

    def fit(self, X, y=None) -> "NarrativeLengthExtractor":
        return self

    def transform(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        if isinstance(X, np.ndarray):
            col = pd.Series(X[:, 0].astype(str))
        else:
            col = X.iloc[:, 0].astype(str)

        # "nan" is pandas string representation of NaN — treat as 0
        lengths = col.apply(lambda s: 0 if s in ("nan", "None", "") else len(s))
        return lengths.values.reshape(-1, 1).astype(float)

    def get_feature_names_out(self, input_features=None) -> np.ndarray:
        return np.array(["narrative_length"])


class SentinelImputer(BaseEstimator, TransformerMixin):
    """
    Fill nulls with a fixed sentinel string and return as object array.

    sklearn's SimpleImputer(strategy='constant') works but loses the object
    dtype on categorical columns when used inside ColumnTransformer with
    mixed types. This wrapper is explicit and readable.

    Why sentinel over mode fill for high-null columns?
    A customer with no Tags wasn't tagged as a servicemember or older American.
    That absence is itself a category, and the model should learn from it.
    Mode fill would erase this signal by substituting the most common non-null
    value — actively misleading the encoder.
    """

    def __init__(self, sentinel: str = "MISSING") -> None:
        self.sentinel = sentinel

    def fit(self, X, y=None) -> "SentinelImputer":
        return self  # Stateless

    def transform(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        if isinstance(X, np.ndarray):
            df = pd.DataFrame(X)
        else:
            df = X.copy()
        return df.fillna(self.sentinel).values.astype(object)

    def get_feature_names_out(self, input_features=None) -> np.ndarray:
        if input_features is not None:
            return np.asarray(input_features)
        return np.array([f"sentinel_{i}" for i in range(1)])


# ---------------------------------------------------------------------------
# Pipeline builder
# ---------------------------------------------------------------------------


def _build_low_card_pipeline() -> Pipeline:
    """
    Pipeline for low-cardinality categoricals:
    SentinelImputer → OneHotEncoder.

    handle_unknown='ignore': unseen categories at serving → all-zero row.
    This is safe — the model sees a "neutral" encoding rather than crashing
    or producing garbage. For a complaint router, an unknown product category
    defaulting to neutral is correct behavior.

    sparse_output=False: return dense array. With only ~20 OHE columns total
    from this group, dense is fine and simpler to debug.
    """
    return Pipeline([
        ("imputer", SentinelImputer(sentinel="MISSING")),
        ("encoder", OneHotEncoder(
            handle_unknown="ignore",
            sparse_output=False,
            dtype=np.float32,
        )),
    ])


def _build_high_card_pipeline() -> Pipeline:
    """
    Pipeline for high-cardinality categoricals:
    SentinelImputer → TargetEncoder.

    TargetEncoder (sklearn >= 1.3) replaces each category with the conditional
    mean of the target, smoothed toward the global mean:

        encoding = (n_cat * mean_cat + k * mean_global) / (n_cat + k)

    where k (the smoothing factor) is chosen by cross-validation when
    smooth='auto'. This prevents a category with 2 examples and 100% dispute
    rate from getting an encoding of 1.0 — it gets pulled toward the 21%
    global rate.

    Unknown categories at serving time → global mean (the 21.2% dispute rate).
    This is the correct fallback: we know nothing about this company/issue
    specifically, so we predict the base rate.

    cv=5: TargetEncoder uses 5-fold cross-fitting during training to prevent
    target leakage within the training set itself. This is important: without
    cross-fitting, the target encoder would see the target for each row when
    computing that row's encoding — data leakage within training.
    """
    return Pipeline([
        ("imputer", SentinelImputer(sentinel="MISSING")),
        ("encoder", TargetEncoder(
            smooth="auto",
            cv=5,
            target_type="binary",
        )),
    ])


def build_feature_pipeline(*, include_scaler: bool = True) -> ColumnTransformer:
    """
    Build the full ColumnTransformer that maps raw intake features → feature matrix.

    This is NOT the full model pipeline — it's the preprocessing stage.
    The caller (build_full_pipeline) wraps this in a Pipeline with the model.

    Parameters
    ----------
    include_scaler : bool
        If True (default), StandardScaler is applied to ALL transformer outputs.
        Set False when using tree-based models that don't need scaling.
        Note: even with include_scaler=True, trees are unaffected by scale —
        there is no downside to leaving it on, and it keeps the pipeline
        model-agnostic.

    Returns
    -------
    ColumnTransformer that accepts a raw DataFrame and outputs a numeric matrix.
    """
    transformers = [
        (
            "low_card_cats",
            _build_low_card_pipeline(),
            LOW_CARD_CATS,
        ),
        (
            "high_card_cats",
            _build_high_card_pipeline(),
            HIGH_CARD_CATS,
        ),
        (
            "date_features",
            DateFeatureExtractor(),
            [DATE_COLUMN],
        ),
        (
            "narrative_length",
            NarrativeLengthExtractor(),
            [NARRATIVE_COLUMN],
        ),
    ]

    ct = ColumnTransformer(
        transformers=transformers,
        remainder="drop",       # Drop ZIP code and any other unspecified columns
        verbose_feature_names_out=False,
    )

    return ct


def build_full_pipeline(model, *, include_scaler: bool = True) -> Pipeline:
    """
    Build the complete training pipeline: preprocessing → (z scaler) → model.

    This is the object that gets:
    1. Fitted on training data (pipeline.fit(X_train, y_train))
    2. Serialized with joblib/mlflow (single artifact)
    3. Loaded at serving time (pipeline.predict_proba(X_serving))

    The entire preprocessing chain — imputation fill values, OHE vocabularies,
    TargetEncoder statistics, scaler mean/std — are frozen inside this object
    after fit(). Loading the artifact at serving time guarantees identical
    preprocessing with zero code duplication.

    Parameters
    ----------
    model : sklearn-compatible estimator
        The classifier to append as the final pipeline step.
    include_scaler : bool
        Whether to include StandardScaler between preprocessing and the model.
        Default True for logistic regression. Can be False for trees (no effect
        either way, but reduces one transformation step).

    Returns
    -------
    sklearn.pipeline.Pipeline ready for fit() and predict_proba().
    """
    steps = [("preprocessor", build_feature_pipeline(include_scaler=include_scaler))]

    if include_scaler:
        steps.append(("scaler", StandardScaler()))

    steps.append(("model", model))

    pipeline = Pipeline(steps)
    logger.info(
        "Built full pipeline with %d steps: %s",
        len(steps),
        [s[0] for s in steps],
    )
    return pipeline


# ---------------------------------------------------------------------------
# Data splitting (time-based — enforced by problem_statement.md)
# ---------------------------------------------------------------------------


def time_based_split(
    df: pd.DataFrame,
    *,
    split_date: str = "2016-01-01",
    date_column: str = DATE_COLUMN,
    target_column: str = TARGET_COLUMN,
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    """
    Split into train/validation using a time cutoff.

    WHY time-based, not random?
    Random splitting assumes rows are i.i.d. Complaint data is not — it has
    temporal structure (complaint volume grew, product mix changed, company
    behaviors evolved). A random split would let training rows from 2016 inform
    validation rows from 2013 — the model would appear to generalize well but
    would be learning from the future. Time-based split evaluates the model
    on complaints filed AFTER the training period, which is how it will be
    used in production.

    Parameters
    ----------
    df : pd.DataFrame
        Full validated DataFrame (leakage columns already dropped).
    split_date : str
        ISO date string. Rows before this date → train; on/after → validation.
        Default "2016-01-01": ~298K train / ~60K val (83%/17% split).
    date_column : str
        Column containing the date (will be parsed with pd.to_datetime).
    target_column : str
        Target column name.

    Returns
    -------
    X_train, y_train, X_val, y_val
    """
    df = df.copy()
    df[date_column] = pd.to_datetime(df[date_column], errors="coerce")

    # Drop rows where target is null (can't train on them)
    before = len(df)
    df = df.dropna(subset=[target_column])
    dropped = before - len(df)
    if dropped > 0:
        logger.warning("Dropped %d rows with null target.", dropped)

    # Encode target: "Yes" → 1, "No" → 0
    y = (df[target_column].str.strip() == "Yes").astype(int)
    X = df.drop(columns=[target_column])

    cutoff = pd.Timestamp(split_date)
    train_mask = df[date_column] < cutoff
    val_mask = ~train_mask

    X_train, y_train = X[train_mask], y[train_mask]
    X_val, y_val = X[val_mask], y[val_mask]

    logger.info(
        "Time-based split at %s: train=%d (%.1f%% positive), val=%d (%.1f%% positive)",
        split_date,
        len(X_train),
        y_train.mean() * 100,
        len(X_val),
        y_val.mean() * 100,
    )
    return X_train, y_train, X_val, y_val


# ---------------------------------------------------------------------------
# Feature name helper
# ---------------------------------------------------------------------------


def get_feature_names(fitted_pipeline: Pipeline) -> list[str]:
    """
    Extract feature names from a fitted pipeline for SHAP / debugging.

    Returns the feature names after preprocessing (before the model step).
    Only works after pipeline.fit() has been called.
    """
    preprocessor: ColumnTransformer = fitted_pipeline.named_steps["preprocessor"]
    try:
        names = list(preprocessor.get_feature_names_out())
        return names
    except Exception as exc:
        logger.warning("Could not extract feature names: %s", exc)
        return []
