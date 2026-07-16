# ML Platform Design

## Core Principle

An ML platform exists to make the path from idea to production shorter, safer, and repeatable. It is not a product for end users -- it is infrastructure for ML engineers and data scientists. A good platform makes the right thing easy (reproducible experiments, validated deployments, monitored predictions) and the wrong thing hard (deploying without evaluation, training without versioning, serving without monitoring). Build the platform incrementally based on actual pain points, not based on what large tech companies built for problems you do not have.

## End-to-End ML Platform Components

A complete ML platform consists of four major subsystems. Each can start simple and grow in sophistication as needs demand.

### Feature Platform

Owns the lifecycle of features: definition, computation, storage, and serving. Provides a consistent interface so training and serving use the same feature values, eliminating training-serving skew.

**Components:** Feature registry (catalog of all feature definitions with metadata), offline store (bulk feature storage for training), online store (low-latency feature storage for serving), materialization pipeline (computes features and writes to both stores), feature validation (schema and distribution checks on computed features).

### Training Platform

Owns the lifecycle of experiments: data preparation, model training, hyperparameter tuning, and evaluation. Provides reproducibility and comparability across experiments.

**Components:** Experiment tracker (logs parameters, metrics, artifacts for every run), training orchestrator (manages compute allocation, job scheduling, and distributed training), hyperparameter tuner (systematic search over hyperparameter space), evaluation framework (standardized evaluation with slicing and fairness checks).

### Serving Platform

Owns the lifecycle of deployed models: deployment, traffic management, scaling, and prediction delivery. Provides reliable, low-latency predictions.

**Components:** Model server (loads and runs models), traffic router (A/B testing, canary, shadow routing), auto-scaler (adjusts replicas based on demand), prediction logger (captures inputs, outputs, and metadata for every prediction).

### Monitoring Platform

Owns the lifecycle of production health: metric collection, drift detection, alerting, and dashboards. Provides visibility into whether the system is working correctly.

**Components:** Metric collector (aggregates prediction, feature, and business metrics), drift detector (compares current distributions against baselines), alerting engine (fires alerts based on configurable thresholds), dashboard service (visualizes health across all models and pipelines).

## Feature Store Architecture

The feature store is the most impactful platform component for most ML teams. It solves the single most common source of bugs: training-serving skew.

### Offline Store

Columnar storage (Parquet files on S3, Delta Lake, BigQuery) optimized for bulk reads. Stores historical feature values with timestamps for point-in-time correct joins.

**Design decisions:**
- Partition by entity type and date for efficient time-range scans.
- Include event timestamps (when the feature value was true in the real world) and processing timestamps (when the feature was computed). Never use processing timestamps for point-in-time joins -- this causes label leakage.
- Retain history long enough to support retraining windows and backtesting. Typically 12-24 months.
- Support schema evolution -- adding new features should not require reprocessing all historical data.

### Online Store

Key-value store (Redis, DynamoDB) optimized for single-entity lookups. Stores only the latest feature values for each entity.

**Design decisions:**
- Key by entity ID (user_id, product_id). Value is a serialized feature vector or a map of feature names to values.
- TTL (time-to-live) based on feature freshness requirements. Real-time features: minutes. Slowly changing features: hours or days.
- Size limits per entity. Feature vectors should be compact -- do not store raw data, only computed features.
- Read latency target: sub-millisecond p99 for the serving path.

### Materialization Pipeline

The bridge between offline and online stores. Computes features from raw data and writes them to both stores.

**Batch materialization:** Scheduled pipeline (Spark, Airflow) computes features from source data and writes to both offline and online stores. Use for features derived from historical data (30-day purchase count, average session length).

**Streaming materialization:** Stream processor (Flink, Kafka Streams) computes features from real-time events and writes to the online store. Use for features that must reflect events within minutes or seconds (items in current cart, last click timestamp).

**Consistency guarantee:** The offline store and online store should contain the same feature values for the same entity at the same point in time. Validate this periodically by sampling entities and comparing values across stores.

### Feature Registry

A catalog of all feature definitions. Each entry includes: feature name, data type, description, owner, source data, computation logic reference, freshness SLO, and dependencies on other features.

**The registry is the source of truth** for what features exist and how they are computed. Data scientists browse the registry to discover reusable features. The materialization pipeline reads the registry to know what to compute. Monitoring uses the registry to know what to validate.

## Model Registry Design

The model registry is the single source of truth for which models exist, their quality, and which one is in production.

### Versioning

Every model version is an immutable artifact with a unique identifier. Versioning must be automatic -- no manual version numbering. Use a monotonically increasing version number or a content-addressable hash.

### Metadata

Each model version stores: training data reference (dataset version or query), training configuration (hyperparameters, feature list, algorithm), evaluation metrics (overall and per-slice), training code reference (git commit hash), environment specification (dependencies, runtime versions), training duration and compute used.

### Lineage

Lineage connects a model version to everything that produced it: which dataset, which features, which code, which configuration. When a model degrades in production, lineage lets you trace back to the exact inputs that produced it and identify what changed.

### Promotion Workflow

Models move through stages: **development** (experimental, not validated), **staging** (passed evaluation gates, ready for production testing), **production** (serving live traffic), **archived** (retired from production, retained for rollback).

Promotion from staging to production should require: evaluation metrics above defined thresholds, no regression versus the current production model on key slices, approval from the model owner (manual gate), and passing golden input tests.

Demotion (rollback) should be a single action that promotes the previous production version back to production status.

## Experiment Tracking Infrastructure

Every training run should capture: a unique run ID, the full parameter set (hyperparameters, feature list, data splits), all computed metrics (training loss curves, validation metrics, test metrics), artifacts (model files, plots, feature importance), the code version (git hash or branch), and the environment (library versions, hardware).

**Comparison:** The tracking system must support comparing runs side by side -- sorting by metric, filtering by parameter ranges, visualizing metric curves overlaid. Without comparison, experiment tracking is just logging.

**Integration:** Experiment tracking should be zero-effort. A single function call at the start of training initializes tracking. Metrics and parameters are logged automatically or with minimal instrumentation. MLflow, Weights & Biases, and Neptune are mature options.

## Data Pipeline Design

### ETL vs ELT

**ETL (Extract, Transform, Load):** Transform data before loading into the destination. Use when the destination has limited compute (a relational database) or when you want to minimize storage costs by only loading transformed data.

**ELT (Extract, Load, Transform):** Load raw data first, then transform in the destination. Use when the destination has abundant compute (a data warehouse like BigQuery or Snowflake). Retains raw data for reprocessing if transformation logic changes.

**For ML:** ELT is generally preferred. Load raw data into a data lake, then run feature engineering pipelines. Retaining raw data lets you recompute features when definitions change without going back to source systems.

### Batch vs Streaming Pipelines

**Batch:** Process data in scheduled intervals (hourly, daily). Simpler, cheaper, sufficient when features do not need to reflect the last few minutes of events.

**Streaming:** Process events as they arrive. Required for real-time features (items in cart, current session behavior). More complex infrastructure (Kafka, Flink) and harder to debug.

**Hybrid (Lambda/Kappa):** Batch pipeline for historical features, streaming pipeline for real-time features. Most production ML systems use this hybrid approach.

### Data Quality Gates

Every pipeline stage should validate its output before passing data downstream:

- **Schema validation:** Column names, types, and nullable constraints match expectations.
- **Distribution checks:** Feature means, variances, and percentiles are within expected ranges.
- **Completeness checks:** Null rates below thresholds, no missing partitions.
- **Freshness checks:** Data timestamp is within the expected recency window.
- **Volume checks:** Row counts are within expected ranges (guard against silent upstream failures that produce empty datasets).

Fail the pipeline loudly when validation fails. A pipeline that silently passes bad data is worse than one that stops.

## Cost Optimization

ML infrastructure costs can grow quickly. Optimize at every layer:

**Training costs:**
- Use spot instances (AWS) or preemptible VMs (GCP) for training workloads. Training is interruptible -- checkpoint regularly and resume from the last checkpoint after preemption. Savings: 60-90% versus on-demand.
- Right-size training instances. Profile memory and compute usage before selecting the instance type. An instance at 20% utilization is wasting 80% of its cost.
- Limit hyperparameter search budget. Early stopping and Bayesian optimization reduce the number of training runs needed.

**Serving costs:**
- Right-size serving instances based on actual load, not peak theoretical load. Use auto-scaling to match capacity to demand.
- Use CPU instances for tabular models (XGBoost, LightGBM, linear models). Reserve GPU instances for deep learning models where GPU inference is measurably faster.
- Model compression (quantization, pruning, distillation) reduces serving compute per prediction. Profile accuracy impact before deploying compressed models.
- Batch predictions when real-time is not required. Batch processing on spot instances is dramatically cheaper than always-on serving endpoints.

**Storage costs:**
- Apply retention policies to prediction logs, experiment artifacts, and feature history. Keep 90 days of detailed logs, aggregate older data.
- Use tiered storage (hot/warm/cold) for feature history. Recent data on fast storage, historical data on cheap storage.
- Compress artifacts (model files, datasets) before storing in object storage.

## When to Use This

- Designing an ML platform for a new organization or team.
- Evaluating build-vs-buy decisions for platform components.
- Auditing an existing ML platform for gaps in reproducibility, monitoring, or cost efficiency.
- Planning the next investment in ML infrastructure.
- Onboarding new ML engineers who need to understand the platform architecture.

## Red Flags to Watch For

- Building a full platform before having a single model in production. Solve real problems first, then generalize.
- Feature store without a registry, so nobody knows what features exist or how they are computed.
- Model registry without lineage, making it impossible to trace a production model back to its training data and code.
- No data quality gates in pipelines, allowing bad data to silently flow into training and serving.
- Experiment tracking that logs parameters but not the code version, making reproduction impossible.
- Promotion workflow with no evaluation gates -- models go from training to production without automated quality checks.
- Online and offline feature stores with no consistency validation, allowing training-serving skew to develop silently.
- No cost monitoring on ML infrastructure, allowing training and serving costs to grow unchecked.
- Building streaming pipelines for features that only need daily freshness, adding unnecessary complexity and cost.
