# Leakage and Skew Detection in Code Review

For training-serving parity fundamentals, see `../../mlops-tabular/references/capabilities/training-serving-parity.md`. This file extends that foundation with code-review-specific detection patterns.

Training-serving parity covers what skew is, why it happens, and how to architect against it. This reference focuses on what a code reviewer should look for: specific code patterns that indicate data leakage or training-serving skew, automated detection heuristics, and a review checklist. These patterns are the most common sources of silently broken ML models -- they produce excellent offline metrics and terrible production performance.

## Code Patterns That Indicate Leakage

### fit_transform Before Split

The single most common leakage pattern. The reviewer should treat this as a critical finding.

**What to look for**: Any call to `fit_transform`, `fit`, or `fit_predict` on the full dataset before `train_test_split` is called. The scaler, encoder, or imputer learns statistics (mean, std, vocabulary, median) from the entire dataset including the test set. The model then trains on features that contain information from the test set.

**Concrete code smell**:
- `scaler.fit_transform(df)` followed later by `train_test_split(df)`
- `encoder.fit(df["category"])` before any split
- `SimpleImputer().fit_transform(X)` before `X_train, X_test = ...`

**Correct pattern**: Split first, then fit on training data only, then transform both training and test data. Or use `sklearn.Pipeline` which enforces this ordering automatically.

### Future-Looking Features

Features that use information from the future relative to the prediction time. These are available during training (because the dataset has all time points) but not available at serving time (because the future has not happened yet).

**What to look for**: Features with names or computations involving aggregates over time windows that extend past the prediction point. "Total purchases this month" available on day 1 of the month. "Average response time for this customer" computed over all interactions including ones after the prediction date.

**Review heuristic**: For every feature, ask: "At the moment this prediction would be made in production, would this feature value be available?" If the answer depends on future events, it is a leak.

### Target Encoding on Full Data

Target encoding (replacing a categorical value with the mean of the target for that category) is a powerful technique but leaks aggressively if done on the full dataset.

**What to look for**: Target encoding applied before cross-validation splitting. Target mean computed on the full training set including the current fold's validation data. No smoothing or regularization applied to the target encoding.

**Correct pattern**: Target encode within each cross-validation fold, using only the training portion of each fold. Apply Bayesian smoothing (blend category mean with global mean, weighted by category frequency) to prevent leakage from low-frequency categories.

### Time-Series Random Split

Randomly splitting time-series data allows future observations to leak into the training set.

**What to look for**: `train_test_split(df, test_size=0.2, random_state=42)` on data with a time dimension. `sklearn.model_selection.KFold` instead of `TimeSeriesSplit`. Any shuffle operation on temporally ordered data.

**Correct pattern**: Split by time. Everything before the cutoff is training, everything after is testing. Use `TimeSeriesSplit` for cross-validation. The test set should always be the chronologically latest data.

### Group Leakage

Data from the same entity (customer, patient, device) appearing in both training and test sets when the entity-level behavior is what the model predicts.

**What to look for**: No `GroupKFold` or `GroupShuffleSplit` when the dataset contains multiple observations per entity. A customer churn model where the same customer's records appear in both train and test -- the model memorizes the customer, not the churn pattern.

**Review heuristic**: If the data has an entity ID column and multiple rows per entity, the split must group by entity.

## Automated Detection Heuristics

These patterns can be caught with static analysis or simple grep searches during review.

**fit_transform before split**: Search for `fit_transform` or `.fit(` in the same file as `train_test_split`. Check line numbers -- if fit occurs before split, flag it. Regex: `fit_transform.*\n.*\n.*train_test_split` (approximate, but catches the pattern).

**Temporal feature indicators**: Search for feature names containing: `total`, `average`, `cumulative`, `lifetime`, `all_time`, `this_month`, `this_year`. Each requires manual review to verify the time window is backward-looking only.

**Random split on time data**: Search for `train_test_split` in files that also reference date/time columns or `pd.to_datetime`. If present, verify the split respects temporal ordering.

**Target leakage indicators**: Search for the target column name being used in feature computation. If `target_col` appears in both the feature engineering section and the label assignment section, investigate whether target information leaks into features.

**Scaling before split**: Search for `StandardScaler`, `MinMaxScaler`, `RobustScaler`, `Normalizer` instantiation. Trace whether `fit` is called before the split.

## Skew Detection in Code Review

### Different Preprocessing in Train vs Serve Files

The most structural form of skew: training and serving have separate preprocessing implementations.

**What to look for**: Preprocessing logic in `train.py` (or training pipeline) that is reimplemented in `serve.py` (or serving endpoint). Even if the logic looks identical, separate implementations will diverge over time as one is updated and the other is forgotten.

**Correct pattern**: A single preprocessing module imported by both training and serving. Or, better, a serialized sklearn.Pipeline that bundles preprocessing with the model.

### Hardcoded Statistics

Normalization means, standard deviations, bin edges, or vocabulary mappings hardcoded in serving code instead of loaded from training artifacts.

**What to look for**: Literal numbers in serving preprocessing code: `(x - 45.2) / 12.7`. Named constants for statistical values: `INCOME_MEAN = 62340`. Any statistical value that should come from the training data but is instead a literal in source code.

**Why it is dangerous**: Hardcoded values become stale when the model is retrained on new data. The model expects the new statistics from the new training run, but serving still uses the old hardcoded values.

### Library Version Mismatches

Different library versions between training and serving environments.

**What to look for**: Separate `requirements.txt` files for training and serving with different version pins. No lockfile. Dependencies pinned loosely (`scikit-learn>=1.0` instead of `scikit-learn==1.3.2`). Docker images for training and serving built from different base images.

**Correct pattern**: A single dependency specification shared between training and serving. If separate is necessary (serving may exclude training-only dependencies), shared dependencies must have identical version pins.

## Code Review Checklist for Leakage and Skew

Use this checklist when reviewing any ML code change:

**Data splitting**:
- Is data split before any preprocessing that learns from data?
- For time-series data, is the split temporal (not random)?
- For grouped data, does the split respect group boundaries?

**Feature engineering**:
- Are all features available at prediction time in production?
- Are aggregations backward-looking only (no future information)?
- Is target encoding done within cross-validation folds?

**Preprocessing parity**:
- Do training and serving use the same preprocessing code (single module or serialized pipeline)?
- Are all learned statistics (means, scales, vocabularies) loaded from artifacts, not hardcoded?
- Are library versions identical between training and serving environments?

**Validation**:
- Does a golden-set parity test exist (same inputs, same outputs, train vs serve)?
- Are feature distributions monitored at serving time and compared against training baselines?
- Does the CI pipeline include a train-predict roundtrip test?

## When to Use This

- During code review of any ML pipeline, feature engineering, or preprocessing code.
- When reviewing serving endpoint code that preprocesses inputs before prediction.
- When investigating production model performance that is worse than offline evaluation.
- When a new feature is added to an existing model.
- When the preprocessing pipeline is modified in any way.

## Red Flags to Watch For

- `fit_transform` called before `train_test_split` in the same script.
- Separate preprocessing implementations in training and serving codebases.
- Hardcoded statistical values in serving code.
- `train_test_split` with `shuffle=True` on time-series data.
- Target column name appearing in feature computation code.
- Different `requirements.txt` files for training and serving with divergent version pins.
- No golden-set parity test in the test suite.
- Features named with temporal aggregation terms that are not verified as backward-looking.
- No `GroupKFold` when the data has entity-level repeated observations.
- Encoders or scalers fitted inside a cross-validation loop but applied outside it.
