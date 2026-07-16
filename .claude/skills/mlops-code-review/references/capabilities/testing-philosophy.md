# Testing Philosophy for ML Code

The dominant testing orthodoxy in software engineering -- unit test everything, mock all dependencies, achieve high coverage -- does not serve ML systems well. ML code has a fundamentally different failure mode: the system can be "correct" at the unit level (each function does what its docstring says) while the end-to-end behavior is wrong (the model makes bad predictions because components interact incorrectly). This reference presents an integration-first, anti-mocking philosophy specifically adapted for ML systems, drawing on Kent Beck's later work, the "TDD is Dead" discourse (DHH, Beck, Fowler), and the Google Testing Blog.

## The Case Against Mocks in ML

Mocks replace real dependencies with fake objects that return predetermined values. In traditional software, this isolates units for testing. In ML systems, mocks create a dangerous illusion.

**Mocks test implementation, not behavior**: When you mock a data loader, you test that the training function calls `data_loader.load()` with the right arguments. You do not test that real data flows correctly through real preprocessing into real training. The contract between components -- data shapes, value ranges, column names, dtypes -- is exactly what matters in ML, and mocks bypass all of it.

**Mocks make refactoring painful**: If you mock every dependency, every refactoring of internal interfaces requires updating every mock. Moving preprocessing from the data loader to the feature engineer breaks all tests even if the pipeline behavior is unchanged. Tests should support refactoring, not punish it.

**Mocks hide integration bugs**: The most common ML bugs are integration bugs: a feature column is renamed upstream, a dtype changes from int64 to float64, a preprocessing step is reordered. Mocks cannot catch these because they hardcode the contract. The real contract is defined by the actual data flowing through the actual code.

**The mock trap in ML pipelines**: A test that mocks the data loader, mocks the preprocessor, and mocks the model verifies that the orchestrator calls three methods in order. This test provides zero confidence that the pipeline produces correct predictions. It is a test of ceremony, not behavior.

## Integration-First Testing

The primary testing strategy for ML code should be integration tests that run real code on small, real-like data.

**Test the real pipeline on small data**: Create a synthetic dataset (50-100 rows) that mirrors the schema and statistical properties of production data. Run the full pipeline -- data loading, preprocessing, training, evaluation -- on this dataset. Verify that the pipeline completes without errors, produces a model artifact, and generates non-degenerate metrics.

**Synthetic data design**: The synthetic dataset should include edge cases that production data will contain: missing values in expected columns, rare categories, boundary values for numerical features, the full range of the target variable. This dataset is a living test fixture that evolves with the data contract.

**Speed is not an excuse to mock**: A full pipeline run on 100 rows with 10 trees takes seconds. The cost of running real code is trivially small. If the pipeline is too slow on small data, the pipeline has a performance problem that should be fixed, not hidden behind mocks.

**Test data contracts explicitly**: If step A produces a DataFrame with columns ["age", "income", "risk_score"] and step B expects those columns, write a test that runs step A and feeds its output to step B. The test verifies the contract through actual execution, not through type annotations or mocked return values.

## What to Unit Test

Unit tests are valuable for pure functions -- functions with no side effects whose output depends only on their input. ML code has plenty of these.

**Preprocessing logic**: A function that bins ages into categories, encodes categoricals, or computes a derived feature is pure. Given a specific input DataFrame, it should produce a specific output DataFrame. Test these deterministically with exact assertions.

**Metric computation**: A function that computes precision, recall, or AUC from predictions and labels is pure. Create synthetic predictions where you know the correct metric values and verify the function computes them exactly.

**Validation rules**: A function that checks whether a DataFrame has the expected schema, whether values are in range, or whether there are too many missing values is pure. Test with valid and invalid inputs.

**Configuration parsing**: A function that reads a YAML file and returns a typed configuration object is pure. Test with valid and invalid configuration files.

**Feature engineering functions**: Individual feature transformations that take a column and return a transformed column. Test with known inputs and expected outputs.

## What NOT to Test

**Internal implementation details**: Do not test which internal methods a class calls, in what order, or how many times. Do not test that `_fit_scaler` is called before `_transform_features`. Test the output of the public interface.

**Framework internals**: Do not test that scikit-learn's `StandardScaler` correctly computes means. Do not test that XGBoost's `fit` method accepts a DataFrame. These are the library's responsibility.

**Exact metric values on tiny data**: A model trained on 20 rows producing accuracy of 0.6 is meaningless. Test that the metric is a valid number in [0, 1], not that it equals a specific value. Exact metric assertions on tiny data create brittle tests that break with library version changes.

**Logging and print statements**: Do not test that the training function logs "Training started." Logging is an implementation detail.

**Private methods**: If a method is private (prefixed with `_`), it is an implementation detail. Test it through the public interface.

## The ML Test Pyramid

The traditional test pyramid (many unit tests, some integration tests, few end-to-end tests) inverts for ML systems.

**Broad integration base**: The majority of tests should be integration tests that run pipeline segments or the full pipeline on synthetic data. These catch the most common and most dangerous bugs: contract violations, shape mismatches, dtype errors, missing column handling.

**Thin unit layer for pure logic**: Unit tests cover pure functions -- preprocessing transforms, metric computations, validation rules. These tests are fast, deterministic, and provide targeted coverage of business logic.

**No mock layer**: There is no layer of mock-based unit tests. Mocking is used only when a real dependency is genuinely impractical (an external API with rate limits, a cloud service with cost implications). Even then, prefer a test double (a lightweight real implementation) over a mock.

**Smoke tests as the safety net**: The most valuable single test is a smoke test that runs the entire pipeline end-to-end on synthetic data. If this test passes, the pipeline is structurally sound. If it fails, something fundamental is broken. This test should run in CI on every commit.

## Property-Based Testing for Data Transformations

Property-based testing (using the `hypothesis` library) generates random inputs and verifies that properties hold for all of them. This is particularly powerful for data transformations.

**Useful properties for ML transforms**:
- **Shape preservation**: The output DataFrame has the same number of rows as the input.
- **Type consistency**: Output dtypes match the expected schema regardless of input values.
- **Idempotency**: Applying the transform twice produces the same result as applying it once (for transforms that should be idempotent).
- **Null handling**: The transform handles missing values without raising exceptions, regardless of which columns have nulls.
- **Monotonicity**: For transforms like binning or scaling, ordering is preserved -- if input A > input B, then transformed A >= transformed B.

**Example application**: Generate random DataFrames with the expected schema (using `hypothesis.extra.pandas`) and verify that the preprocessing pipeline produces output with the correct shape, dtypes, and no unexpected nulls. This catches edge cases that hand-crafted test data misses.

## When to Use This

- When setting up the testing strategy for a new ML project -- start with integration tests.
- When reviewing tests that are heavily mocked -- challenge whether the mocks are catching real bugs.
- When tests break during refactoring despite no behavior change -- mocks are likely coupling tests to implementation.
- When the team has high test coverage but low confidence in the pipeline's correctness.
- When onboarding new team members to the project's testing philosophy.

## Red Flags to Watch For

- More mock objects than real objects in a test file.
- Tests that verify method call order rather than output correctness.
- No integration test that runs the pipeline end-to-end on synthetic data.
- Test data that does not include edge cases (nulls, rare categories, boundary values).
- Assertions on exact metric values from tiny datasets.
- Tests that pass but the pipeline fails on real data -- a sign the tests are not testing the right things.
- No synthetic test dataset committed to the repository.
- Tests that take minutes because they run on large data -- use small, representative synthetic data instead.
- Test files that are longer than the code they test -- complexity in tests defeats the purpose.
- Property-based tests missing for data transformation functions that should maintain invariants.
