"""
steps/preprocess.py
===================
ZenML step for data splitting and pipeline fitting.

Thin wrapper — all logic lives in core/preprocessing.py.

Step contract:
    Input  : df (pd.DataFrame)        — validated, leakage-free raw DataFrame
    Outputs:
        X_train (pd.DataFrame)        — training features
        y_train (pd.Series)           — training labels (0/1)
        X_val   (pd.DataFrame)        — validation features
        y_val   (pd.Series)           — validation labels (0/1)

The fitted pipeline is NOT output here — it gets fitted in the training step
so that cross-validation can refit it inside each fold. This step only
performs the time-based split and returns the raw (unprocessed) splits.
The pipeline is built and fitted by the training step.
"""

from __future__ import annotations

import logging

import pandas as pd
from zenml import step

from core.preprocessing import time_based_split

logger = logging.getLogger(__name__)


@step
def split_data(
    df: pd.DataFrame,
    split_date: str = "2016-01-01",
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    """
    Apply time-based train/validation split to the validated DataFrame.

    Returns raw (unprocessed) splits. The preprocessing pipeline is fitted
    in the training step — fitting it here would cause data leakage through
    cross-validation folds.

    Parameters
    ----------
    df : pd.DataFrame
        Validated DataFrame from the ingest step.
    split_date : str
        ISO date cutoff. Default "2016-01-01" yields ~83%/17% split.

    Returns
    -------
    X_train, y_train, X_val, y_val
    """
    X_train, y_train, X_val, y_val = time_based_split(df, split_date=split_date)

    logger.info(
        "Split complete. Train: %d rows | Val: %d rows | "
        "Train positive rate: %.1f%% | Val positive rate: %.1f%%",
        len(X_train),
        len(X_val),
        y_train.mean() * 100,
        y_val.mean() * 100,
    )

    return X_train, y_train, X_val, y_val
