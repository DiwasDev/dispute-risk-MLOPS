# ML Testing Patterns

ML testing requires patterns that do not exist in traditional software testing. The model is a learned artifact whose behavior is probabilistic, data-dependent, and non-deterministic across training runs. Standard assertions ("output equals expected") work for preprocessing but fail for model behavior. This reference provides concrete testing patterns organized by what they validate: data, models, integration, behavior, and regression. Sources include Google's ML testing practices, Jeremy Jordan's "Effective Testing for Machine Learning Systems," and Great Expectations patterns.

## Data Tests

Data is the most common source of ML failures. Data tests validate assumptions about incoming data before it reaches the model.

### Schema Validation

Verify that incoming data matches the expected schema: column names, data types, and constraints.

**What to test**: Column presence (all expected columns exist), column types (age is numeric, category is string), nullable constraints (target column has no nulls), uniqueness constraints (ID column is unique per row).

**When to run**: At pipeline entry (data loading step), at every step boundary where data format changes, and at serving time before prediction.

**Pattern**: Define the schema as a typed object (Pydantic model, pandera SchemaModel, or Great Expectations suite). Validate every DataFrame against the schema at load time. Fail immediately on violation with a specific error message identifying which column and constraint failed.

### Distribution Checks

Verify that data distributions match expectations established during training.

**What to test**: Value ranges (age between 0 and 120), mean and standard deviation within expected bounds, categorical cardinality (number of unique values), null rates below thresholds, target class balance within expected range.

**Pattern**: Compute baseline statistics from the training dataset. At each pipeline run, compare incoming data statistics against the baseline. Use statistical tests (KS test for continuous, chi-squared for categorical) with alerting thresholds. Flag but do not necessarily block on minor deviations; block on severe violations.

### Freshness and Completeness

Verify that data is current and complete.

**What to test**: Data timestamp within expected recency window (not stale), row count within expected range (not truncated), no unexpected gaps in time series data, all expected partitions present.

**Pattern**: Maintain metadata about expected data characteristics. Compare each data load against expectations. A training dataset that suddenly has 50% fewer rows than last month is a data pipeline failure, not a modeling problem.

## Model Tests

Model tests verify that the trained model behaves correctly without asserting specific metric values on small data.

### Training Smoke Test

Verify that the model trains without errors on a small dataset.

**What to test**: Model fits without exceptions, model produces a prediction for every input row, predictions have the correct shape and type, predictions are not all identical (degenerate model), predictions are within valid range (probabilities between 0 and 1).

**Pattern**: Create a small synthetic dataset (50-100 rows) that mirrors the schema and edge cases of real data. Train the model for a minimal number of iterations (1 tree, 1 epoch). Verify the model object is created and can predict. Do not assert metric values -- they are meaningless on tiny data.

### Prediction Shape Test

Verify that predictions match expected format.

**What to test**: Output shape matches input row count, prediction dtype is correct (float for probabilities, int for classes), multi-class predictions have correct number of columns, prediction values are within valid range.

### Invariance Tests

Verify that certain input changes do not affect predictions when they should not.

**What to test**: Changing a feature that should not influence the outcome (name, ID) does not change the prediction. Permuting the order of input rows does not change the set of predictions. Adding trailing whitespace to string features does not change predictions.

**Pattern**: Take a reference input, create a perturbed copy with irrelevant changes, predict on both, assert predictions are identical. These tests catch accidental feature leakage and preprocessing bugs.

### Directional Expectation Tests

Verify that the model's behavior aligns with domain knowledge.

**What to test**: Increasing income (all else equal) increases credit approval probability. Higher risk score decreases insurance offer probability. The direction of effect matches business intuition for key features.

**Pattern**: Create a base input. Create a modified version with one feature changed in a direction with known expected effect. Predict on both. Assert that the prediction moves in the expected direction. Do not assert magnitude -- just direction.

### Model Comparison Test

Verify that the new model is not worse than the baseline.

**What to test**: New model metrics meet or exceed baseline model metrics on a held-out validation set. If the new model is worse, the test fails and the model is not promoted.

**Pattern**: Maintain a fixed validation dataset (versioned, not used in training). Train the baseline model and the new model. Compare metrics on the validation set. Set a minimum improvement threshold or a maximum degradation tolerance.

## Integration Tests

Integration tests verify that components work together correctly.

### Full Pipeline on Synthetic Data

The single most valuable ML test. Run the entire pipeline -- data loading, preprocessing, feature engineering, training, evaluation, prediction -- on a synthetic dataset.

**What to test**: Pipeline completes without errors. Output artifacts are created (model file, metrics file, evaluation report). Metrics are valid numbers. Predictions can be generated from the saved model.

**Pattern**: Commit a small synthetic dataset to the repository. Run the full pipeline in CI on every commit. This test catches contract violations, import errors, configuration issues, and shape mismatches.

### Train-Predict Roundtrip

Verify that a model trained in the pipeline can generate predictions through the serving path.

**What to test**: Train a model, save it, load it in the serving code, and generate predictions. Predictions from the loaded model match predictions from the in-memory model (no serialization corruption).

**Pattern**: This test specifically catches serialization bugs, pipeline vs model artifact mismatches, and preprocessing discrepancies between training and serving code.

### Artifact Loading and Saving

Verify that all pipeline artifacts (model, scaler, encoder, configuration) can be saved and loaded correctly.

**What to test**: Save artifact, load artifact, use loaded artifact to produce output, compare output against original. Verify artifact metadata (version, timestamp, configuration hash) is preserved.

## Behavioral Tests

Behavioral tests verify model behavior on specific scenarios that matter for the business.

### Perturbation Sensitivity

Verify that small input changes produce proportionally small output changes.

**What to test**: Changing age by 1 year should not flip a prediction from approve to deny. Changing income by 1% should not cause a large prediction shift. Sensitivity should be proportional to the change magnitude.

**Pattern**: Take a reference input near a decision boundary. Apply small perturbations to each feature. Measure prediction change. Flag features where small perturbations cause disproportionate prediction changes -- this may indicate overfitting, feature scaling issues, or numerical instability.

### Slice-Based Tests

Verify model performance across important subgroups.

**What to test**: Model performance (accuracy, precision, recall) for each important demographic, geographic, or business segment. Performance should meet minimum thresholds for all slices, not just the aggregate.

**Pattern**: Define slices based on business requirements and fairness criteria. Evaluate the model on each slice independently. Fail if any slice falls below the minimum threshold. This catches models that perform well on average but fail for specific groups.

## Regression Tests

Regression tests detect unexpected changes in model behavior across versions.

### Golden Input Tests

Maintain a fixed set of inputs with expected prediction ranges.

**What to test**: A set of 20-50 carefully chosen inputs that represent important business scenarios. For each input, the prediction should fall within a documented range. If a model change causes predictions on golden inputs to change significantly, the test fails.

**Pattern**: Store golden inputs and expected ranges in a committed test file. Run golden input tests after every model retrain. Review any golden input failures before promoting the model.

### Prediction Distribution Tests

Compare the prediction distribution of the new model against the previous version.

**What to test**: The overall prediction distribution (mean, median, percentiles) should not shift dramatically between model versions. If the new model suddenly predicts much higher or lower on the same data, something has changed that requires investigation.

## CI Integration Patterns

**On every commit**: Run schema validation tests, unit tests for preprocessing, and the full pipeline smoke test on synthetic data. Target: under 5 minutes.

**On model-related changes**: Run behavioral tests, slice-based tests, and model comparison tests. Target: under 30 minutes.

**Before model promotion**: Run golden input tests, prediction distribution comparison, and full evaluation on held-out data. This is the gate before production deployment.

## When to Use This

- When setting up the test suite for a new ML project -- use this as the pattern catalog.
- When reviewing test code in PRs -- verify that the right categories of tests are present.
- When a model fails in production -- check which test category would have caught it and add that test.
- When the test suite runs for too long -- restructure using the CI integration tiers.

## Red Flags to Watch For

- No data validation tests -- the pipeline trusts upstream data implicitly.
- No smoke test that runs the full pipeline on synthetic data.
- Tests that assert exact metric values on tiny datasets -- these are brittle and meaningless.
- No invariance tests -- the model may be using features it should not.
- No slice-based evaluation -- aggregate metrics hide subgroup failures.
- Tests that pass but do not test the serving path -- train-predict roundtrip is missing.
- No golden input tests -- model behavior changes go unnoticed between versions.
- All tests run on every commit with no tiering -- slow CI discourages frequent commits.
