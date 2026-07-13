# Data Quality & Schema Validation

## Why Data Quality Is the Foundation

In production ML, data quality problems are the most common root cause of model failures. A model trained on corrupted data learns the wrong patterns. A model served features from a broken pipeline produces confidently wrong predictions. Unlike code bugs that crash loudly, data bugs produce models that return plausible-looking but incorrect outputs -- the silent failure pattern that makes ML systems treacherous to operate.

Data quality is not a one-time check. It is a continuous discipline: validate data on ingestion, monitor it over time, and fail fast when something goes wrong rather than letting bad data propagate through training and serving.

## Schema Definition and Validation

A schema defines the expected structure of your data: which columns exist, what types they have, and what constraints they must satisfy. Every dataset entering your pipeline should be validated against its schema before any processing begins.

### What a Schema Should Specify

**Column presence:** which columns must exist. A missing column should halt the pipeline immediately rather than producing a model trained on fewer features than expected.

**Data types:** each column's expected type (integer, float, string, boolean, datetime). Type mismatches -- like a numeric feature arriving as a string -- cause subtle bugs that can survive through training and only surface as degraded predictions.

**Value constraints:** acceptable ranges for numeric columns (age between 0 and 150, price greater than 0), allowed values for categorical columns (known categories plus a defined handling for unknowns), and format patterns for strings (email addresses, phone numbers, date formats).

**Nullability rules:** which columns may contain nulls and at what maximum rate. A column that was 2% null during training but is now 40% null indicates a data pipeline failure.

**Cardinality bounds:** for categorical columns, the expected number of unique values or an acceptable range. A category column that suddenly has 10x more unique values may indicate a join error or encoding problem.

### Validation Strategy

Validate at every boundary where data enters or leaves a pipeline stage:

- **On ingestion:** check the raw data against the source schema before any transformation.
- **After transformation:** check the transformed features against the feature schema before training.
- **At serving time:** check the input features against the model's expected schema before scoring.
- **On output:** check that predictions fall within expected ranges (probabilities between 0 and 1, prices non-negative).

Fail fast and fail loudly. A validation failure should stop the pipeline and alert the team, not silently continue with bad data.

## Data Quality Metrics

Track these metrics continuously, not just at training time. The model does not crash when data is bad -- it trains on the bad data, learns wrong patterns, and confidently serves wrong predictions. A database column renamed without notifying the ML team means the pipeline trains on wrong features without errors.

| Metric | Purpose | Example Threshold |
|--------|---------|-------------------|
| Completeness | Non-null percentage per column | Alert if drops >5% from baseline |
| Freshness | Time since last data update | Alert if >2x expected cadence |
| Consistency | Cross-column agreement | Alert on any violation |
| Distribution Stability | Feature distribution shifts | PSI > 0.25 triggers investigation |
| Volume | Record count per batch | Alert if outside ±30% of trailing average |
| Accuracy | Values match ground truth | Periodic manual audit |

**Completeness:** the fraction of non-null values per column. Establish a baseline from your training data and alert when completeness drops below it. A feature that was 98% complete and drops to 80% is a pipeline problem.

**Freshness:** how recently the data was updated. If your pipeline expects daily data but the source table has not been updated in three days, downstream features are stale. Set freshness SLOs (e.g., user embeddings must refresh within 6 hours) and alert on violations.

**Consistency:** do values agree across related columns? If a record has "state = California" but "zip code = 10001" (New York), something is wrong. Cross-column consistency checks catch join errors and data corruption.

**Accuracy:** do values match ground truth? This is the hardest to measure because ground truth is often unavailable or delayed. Use spot checks, manual audits, and known-good reference datasets.

**Distribution stability:** does the distribution of each feature match historical patterns? A sudden shift in the distribution of a feature -- without a known real-world cause -- suggests a data pipeline change, not a genuine shift in the world.

**Volume:** is the expected number of records arriving? A training batch that is half the usual size may indicate a partial data pull. Set bounds on expected record counts.

## Null Handling

Nulls are inevitable in production data. The critical requirement is that null handling is consistent between training and serving and that the strategy is deliberate, not accidental.

**Define a null strategy for each feature:** some nulls are meaningful (a customer has no phone number because they chose not to provide one) and some are errors (a phone number column is null because the data pipeline failed). Handle these differently.

**Common null strategies:**
- Fill with a sentinel value (e.g., -1 for numeric, "UNKNOWN" for categorical) when nullness itself is informative.
- Fill with the training-set statistic (mean, median, mode) when you want to make the null invisible to the model. Save the fill values as artifacts.
- Drop rows with nulls only if the null rate is low and the data is abundant. Never silently drop rows without logging how many were dropped.
- Create a binary "is_null" indicator feature alongside the filled value, allowing the model to learn from both the imputed value and the fact of missingness.

**The parity requirement applies:** whatever null-handling logic you use in training must be identically applied in serving. Save the fill values, the sentinel values, and the logic as pipeline artifacts.

## Outlier Detection

Outliers can be genuine extreme values or data errors. The distinction matters:

**Statistical outliers** (values more than N standard deviations from the mean, or outside the interquartile range by a multiple) should be flagged but not automatically removed. In fraud detection, outliers are often the signal. In demand forecasting, they may be genuine spikes.

**Impossible values** (negative ages, prices of zero for paid products, dates in the future for historical data) are errors and should be caught by schema validation.

**Approach for production systems:**
- Flag outliers during validation and log them.
- Apply winsorization or capping only when the domain justifies it (e.g., capping income at the 99th percentile for a credit model).
- Save the capping thresholds as artifacts and apply the same thresholds in serving.
- Monitor the outlier rate over time. A sudden increase in outliers may signal a data source problem.

## Quality Monitoring in Production

Data quality is not just a training-time concern. In production, data changes continuously, and quality must be monitored continuously.

**Input monitoring:** for every feature served to the model, track null rates, value distributions, and cardinality over time. Compare against training-time baselines. Alert on deviations.

**Upstream dependency monitoring:** your data comes from somewhere -- a database, an API, a batch job. Monitor the health of these sources. If an upstream batch job fails silently, your features become stale without any error in your own pipeline.

**Data SLOs:** define service-level objectives for your data, just as you would for a web service:
- Freshness: data must be no more than X hours old.
- Completeness: at least Y% of records must have non-null values for critical features.
- Volume: daily record count must be within Z% of the trailing average.
Track these SLOs on a dashboard and alert on violations.

**Lineage tracking:** connect each prediction to the data batch, feature versions, and code version that produced it. When a bad prediction is discovered, lineage lets you trace it back to the root cause. Without lineage, debugging is guesswork.

## Schema Evolution

Schemas change over time as the product evolves: new features are added, old ones are deprecated, definitions shift. Manage schema evolution deliberately:

**Additive changes** (adding a new column) are generally safe. The new column should have a default or null strategy defined for older data that lacks it.

**Breaking changes** (removing a column, changing a column's type, changing a column's semantics) require coordination. If a model depends on a feature that is being removed, the model must be retrained without that feature before the column is dropped.

**Version your schemas** alongside your data and code. When the schema changes, record which version of the schema was used for each training run and each production model. This prevents the situation where a schema change breaks a production model silently.

**Migration strategy:** when a schema change is needed, run the old and new schemas in parallel during a transition period. Validate data against both. Only retire the old schema when all dependent models have been updated.

## Test Automation for Data Quality

Automate data quality checks so they run consistently without human intervention:

**Unit-level data tests:** validate individual columns against their schema constraints. These run fast and catch basic errors.

**Cross-column tests:** validate relationships between columns (consistency checks, referential integrity).

**Distribution tests:** compare current data distributions against historical baselines using statistical tests (KS test, chi-squared test, PSI). These catch drift and pipeline changes.

**End-to-end mini pipeline tests:** run the full pipeline on a small sample of data. If the mini job completes with valid outputs, the full job is likely to succeed. If the mini job fails, you catch the error before wasting compute on a full run.

**Golden dataset tests:** maintain a small, curated dataset with known correct values. Run it through the pipeline and verify outputs match expected results. This catches regressions in transformation logic.

**CI integration:** run data validation tests as part of continuous integration. Every code change that touches data processing should trigger schema and distribution checks against a test dataset.

## When to Use This

- You are setting up a new ML pipeline and need to define data contracts between pipeline stages.
- You are diagnosing why a retrained model performs worse than the previous version -- data quality is the first suspect.
- You are integrating a new data source and need to validate it before trusting it for model training.
- You are experiencing intermittent model quality issues that correlate with data pipeline schedules.
- You need to establish monitoring for a production ML system that currently has no data quality checks.

## Red Flags to Watch For

- No schema is defined for the training data -- the pipeline accepts whatever arrives.
- Null handling differs between training and serving, or nulls are silently dropped without logging.
- There are no data freshness checks, so stale data can silently degrade model quality.
- The pipeline has no fail-fast behavior -- it continues processing even when data validation fails.
- Data quality is only checked at training time, not during production serving.
- Schema changes are made without versioning, so it is unclear which schema a production model expects.
- There is no lineage from predictions back to the data batch that produced them.
- Outlier handling thresholds are computed at serving time from live data instead of loaded from training artifacts.
- The team has no automated data tests -- quality is checked manually, if at all.
- Volume changes (sudden drops or spikes in record count) go undetected because no volume monitoring exists.
- Cross-column consistency is never validated, so join errors or data corruption can persist undetected.
