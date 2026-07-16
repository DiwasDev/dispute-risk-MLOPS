# ML Infrastructure Patterns

## Core Principle

ML infrastructure is not application infrastructure with a model bolted on. ML systems have four sources of truth -- code, data, model weights, and configuration -- and all four must be versioned, tested, and monitored. Traditional CI/CD handles code. ML infrastructure must extend that discipline to data, models, and the interactions between them. The patterns in this document are the operational backbone that keeps an ML system reliable as it evolves.

## Training Pipeline Architecture

A training pipeline is not a script that trains a model. It is a sequence of discrete, testable, reproducible stages, each with defined inputs, outputs, and validation criteria.

### Stage 1: Data Ingestion

Pull raw data from source systems into the ML system's data layer. This stage handles full loads, incremental loads, retries on source failures, and data format normalization. The output is raw data in a consistent format (Parquet, Delta Lake) in the data lake.

**Key decision:** Full vs incremental ingestion. Full ingestion is simpler and guarantees completeness but is expensive for large datasets. Incremental ingestion is efficient but requires tracking watermarks and handling late-arriving data.

### Stage 2: Data Validation

Validate ingested data before any processing. Schema checks (column names, types, nullability), statistical checks (distribution means and variances within expected ranges, null rates below thresholds), volume checks (row counts within expected ranges), and freshness checks (data timestamp within expected recency).

**Hard stops vs warnings:** Define which validation failures halt the pipeline and which produce warnings. A schema change is a hard stop. A slight shift in a feature mean is a warning that gets logged and reviewed.

### Stage 3: Feature Engineering

Transform validated data into model-ready features. This stage must produce identical outputs whether run in batch training context or in online serving context. Save all transformation artifacts (scalers, encoders, bin edges) as versioned files loaded by both training and serving.

### Stage 4: Model Training

Fit the model to prepared data. Log every training run with: parameters, metrics (loss curves, validation scores), artifacts (model file, feature importance), code version, data version, and environment specification. Support hyperparameter tuning as an outer loop over training runs.

### Stage 5: Model Evaluation

Evaluate the trained model against held-out data using the metric ladder (business metrics, product metrics, model metrics). Compute slice-level metrics for all critical segments. Compare against the current production model. Compute confidence intervals via bootstrapping. Gate promotion on passing all evaluation criteria.

### Stage 6: Registration

Register the model in the model registry with full metadata and lineage. Set the model status to "staging" pending promotion. This stage is the handoff from training to serving.

**Pipeline orchestration:** Use Airflow, Prefect, Kubeflow Pipelines, or Metaflow. The orchestrator manages stage dependencies, retries, and logging. Each stage should be independently re-runnable -- if stage 4 fails, you should not need to re-run stages 1-3.

## Data Versioning Systems

Data versioning ensures you can reproduce any past training run and understand what changed when a model degrades.

**DVC (Data Version Control):** Git-like versioning for data files. Stores data in remote storage (S3, GCS) and tracks metadata (hashes, paths) in git. Lightweight, integrates with existing git workflows. Best for teams already using git who want to version datasets alongside code.

**LakeFS:** Git-like branching and committing for data lakes. Create branches to experiment with data transformations without affecting the main lake. Merge when validated. Best for teams working with large data lakes who need isolation for experimental data processing.

**Delta Lake:** ACID transactions on top of data lakes (Parquet on S3). Supports time travel (query data as it existed at a past timestamp), schema enforcement, and schema evolution. Best for teams using Spark who need transactional guarantees on their data lake.

**Decision framework:**
- File-level versioning of datasets: DVC.
- Branch-and-merge workflow on a data lake: LakeFS.
- Transactional data lake with time travel: Delta Lake.
- All three can coexist: DVC for final training datasets, Delta Lake for the feature lake.

## Model Versioning and Lineage

Every model version must be traceable to: the exact code that produced it (git commit), the exact data it was trained on (data version or query), the exact configuration used (hyperparameters, feature list), and the environment it was trained in (library versions, hardware).

**Lineage graph:** Model V3 was trained on dataset D7, which was derived from features F12 and F15, which were computed from raw data R4. When model V3 degrades, walk the lineage graph to identify what changed: did the code change? The data? The features? The environment?

**Practical implementation:** Store lineage as metadata in the model registry. Each model version entry links to a dataset version, a code commit, a configuration file, and an environment specification. Use immutable artifact storage -- never overwrite a model artifact, always create a new version.

## CI/CD for ML

Traditional CI/CD handles code. ML CI/CD must handle three additional dimensions.

### Code CI

Standard software CI: linting, unit tests, integration tests on every code change. For ML code specifically:
- Unit test feature engineering functions with known inputs and expected outputs.
- Unit test data validation rules with synthetic data that both passes and violates.
- Integration test the full training pipeline on a small sample dataset.
- Test that the serving code loads a model and returns predictions in the expected format.

### Model CI

Triggered when a training pipeline produces a new model. Automated checks:
- Evaluation metrics meet minimum thresholds (absolute gates).
- No regression versus the current production model on key metrics (relative gates).
- Slice-level evaluation passes for all critical segments.
- Model size and inference latency are within serving constraints.
- Golden input tests produce expected outputs.

### Data CI

Triggered when new data arrives or feature definitions change. Automated checks:
- Schema validation passes (no unexpected columns, types, or nullability changes).
- Distribution checks pass (no significant drift from expected ranges).
- Completeness checks pass (null rates, row counts within bounds).
- Feature computation produces expected outputs for known test cases.

**Pipeline:** Code change triggers code CI. Code CI passing triggers a training pipeline run. Training pipeline completion triggers model CI. New data arrival triggers data CI. Data CI passing triggers retraining if configured. All gates are automated, logged, and auditable.

## Monitoring and Observability for ML

ML monitoring operates at four layers. Each layer catches different failure modes.

### Layer 1: Infrastructure Monitoring

CPU, memory, disk, GPU utilization, network I/O, container health. Standard DevOps monitoring. Catches hardware failures, resource exhaustion, and scaling issues. Tools: Prometheus, Grafana, CloudWatch, Datadog.

**ML-specific:** Monitor GPU memory usage per model, GPU utilization percentage (low utilization means wasted spend), model loading time, and container restart frequency.

### Layer 2: Application Monitoring

Request rate, error rate, latency (p50, p95, p99), throughput, queue depth, cache hit rate. Standard application monitoring. Catches serving infrastructure issues. Tools: Prometheus, Grafana, application APM.

**ML-specific:** Monitor prediction request rate per model, feature store lookup latency, model inference latency (separate from total request latency), and batch pipeline duration and success rate.

### Layer 3: Model Monitoring

Prediction distribution shape, confidence score distribution, prediction class balance, model accuracy (when labels arrive), slice-level metrics. ML-specific monitoring that catches model degradation.

**What to track:** Histogram of prediction scores over time, fraction of predictions in each class, mean and variance of prediction confidence, performance metrics reconciled against ground truth on a lag.

### Layer 4: Data Monitoring

Feature distributions, null rates, cardinality, upstream data freshness, schema compliance. Catches data quality issues before they affect the model.

**What to track:** Per-feature distribution statistics (mean, variance, percentiles) compared against a training-time baseline, null rate per feature over time, categorical feature cardinality, data arrival time relative to SLO.

## Drift Detection Architecture

Drift detection compares current data and prediction distributions against a reference baseline.

**Reference baseline:** Feature distributions and prediction distributions from the training data or from a known-good production window.

**Detection methods:**
- **KS test (Kolmogorov-Smirnov):** For continuous features. Tests whether two distributions are different. Sensitive to any distribution change.
- **Chi-squared test:** For categorical features. Tests whether category frequencies have changed.
- **PSI (Population Stability Index):** Quantifies distribution shift with interpretable thresholds: PSI < 0.1 (no significant shift), 0.1-0.25 (moderate shift, investigate), > 0.25 (significant shift, action required).
- **Wasserstein distance:** Measures the minimum cost to transform one distribution into another. More intuitive than KS for understanding the magnitude of shift.

**Architecture:** A scheduled pipeline reads current production data (from prediction logs or feature logs), computes distribution statistics, compares against the reference baseline using the chosen tests, and publishes drift scores. Alerts fire when drift exceeds thresholds. Drift events can trigger the retraining pipeline.

## Retraining Automation

### Trigger-Based Retraining

Retrain when a condition is met:
- Drift score exceeds threshold (data distribution has shifted enough that the model may be stale).
- Model performance metric drops below threshold (ground truth confirms degradation).
- Upstream data source has a major schema or distribution change.

**Advantages:** Retrains only when needed, avoids unnecessary compute cost, responds to actual problems.

### Schedule-Based Retraining

Retrain on a fixed cadence (daily, weekly, monthly) regardless of drift or performance.

**Advantages:** Simple to implement and reason about. Guarantees the model incorporates recent data within a predictable window. Does not require drift detection infrastructure.

**Disadvantages:** May retrain unnecessarily (wasting compute) or too infrequently (missing drift between scheduled runs).

### Choosing Between Them

- **Start with schedule-based** if you do not yet have drift detection infrastructure. Weekly or monthly depending on how fast your domain changes.
- **Migrate to trigger-based** when you have reliable drift detection and evaluation gates. Trigger-based is more efficient and more responsive.
- **Combine both:** Schedule-based as a floor (retrain at least monthly), trigger-based for responding to detected drift between scheduled runs.

**Critical safety rule:** Never deploy a retrained model without automated evaluation. Every retrained model must pass the same model CI gates as a manually trained model. Automatic retraining without automatic evaluation is a path to silently deploying worse models.

## Reproducibility Infrastructure

Reproducibility means: given the same inputs (code, data, configuration, environment), the training pipeline produces the same model. This requires:

- **Code versioning:** Every training run links to a git commit.
- **Data versioning:** Every training run links to a data version (DVC hash, Delta Lake timestamp, dataset snapshot ID).
- **Configuration versioning:** Hyperparameters, feature lists, and thresholds stored as versioned config files, not hardcoded in code.
- **Environment versioning:** Docker images with pinned dependency versions. The environment specification is an artifact, not a wiki page.
- **Random seed management:** Set seeds for all sources of randomness (data splitting, model initialization, dropout). Document which operations are non-deterministic even with seeds (GPU floating-point operations, distributed training).

**Verification:** Periodically reproduce a past training run and verify the resulting model matches the original. Divergence indicates a reproducibility gap that must be investigated.

## When to Use This

- Setting up ML infrastructure for a new team or project.
- Auditing an existing ML system for gaps in versioning, testing, or monitoring.
- Designing a retraining automation strategy.
- Implementing CI/CD for an ML pipeline.
- Investigating a production incident where the model degraded and you need to identify the root cause.

## Red Flags to Watch For

- Training pipeline is a single monolithic script with no stage separation, making debugging and re-runs impossible.
- No data versioning -- training runs reference "the latest data" with no way to know what that was.
- Model CI checks only overall metrics, not slice-level metrics. A model that degrades for a critical segment passes the gate.
- Drift detection alerts fire but no response process exists -- alerts become noise.
- Automatic retraining without automatic evaluation gates, risking deployment of worse models.
- No reproducibility verification -- the team assumes reproducibility without testing it.
- Monitoring covers infrastructure (Layer 1) and application (Layer 2) but not model (Layer 3) or data (Layer 4).
- CI/CD handles code changes but not data changes or model changes, leaving two of the four sources of truth ungated.
