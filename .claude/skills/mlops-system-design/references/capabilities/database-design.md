# Database Design for ML Systems

## Core Principle

The database is the foundation your ML system stands on. Choose the wrong storage engine and you will fight it at every stage -- ingestion, feature engineering, serving, and monitoring. The right choice depends on your access patterns, consistency needs, and scale requirements, not on what is trending.

## SQL vs NoSQL Decision Framework

Do not choose a database based on hype. Apply these concrete criteria:

**Choose SQL (PostgreSQL, MySQL) when:**
- You need ACID transactions across multiple tables (e.g., atomically updating a model's status and its evaluation metrics).
- Your data has well-defined relationships and you need joins (experiment metadata linked to metrics linked to artifacts).
- You need complex queries with aggregations, window functions, and subqueries (analyzing experiment results across multiple dimensions).
- Your data fits on a single machine or a small cluster with read replicas.

**Choose a document store (MongoDB, DynamoDB) when:**
- Your schema varies across records (different model types store different metadata fields).
- You need flexible schema evolution without migrations.
- Your access pattern is primarily key-value lookup or simple queries on a partition key.
- You need horizontal scaling beyond what a single SQL instance can handle.

**Choose a column-family store (Cassandra, HBase) when:**
- You need high write throughput for time-series data (prediction logs, feature values over time).
- Your access pattern is append-heavy with time-range reads.
- You can tolerate eventual consistency for higher availability and partition tolerance.

**Choose a graph database (Neo4j, Neptune) when:**
- You need to traverse relationships (model lineage, data dependency graphs, feature relationships).
- Relationship queries would require multiple self-joins in SQL, making them impractical.

**Choose a time-series database (InfluxDB, TimescaleDB) when:**
- Your primary workload is time-stamped metrics (model performance over time, prediction latency, drift scores).
- You need efficient time-range queries and automatic data retention policies.

## Indexing Strategies

Indexes determine whether your queries take milliseconds or minutes. Understand the tradeoffs:

**B-tree indexes** are the default in most SQL databases. They support equality and range queries efficiently. Use them for columns you filter on frequently (model_id, created_at, status). They are balanced -- reads and writes are both O(log n).

**LSM-tree indexes** (used in LevelDB, RocksDB, Cassandra) optimize for write-heavy workloads. Writes go to an in-memory buffer and are flushed to sorted files on disk. Reads may need to check multiple files. Choose LSM when your workload is write-heavy (high-volume prediction logging).

**Composite indexes** cover multiple columns in a single index. Column order matters -- the index on (model_id, created_at) supports queries filtering on model_id alone or on both, but not on created_at alone. Put the most selective column first.

**Covering indexes** include all columns needed by a query, so the database never touches the main table. For a query that only needs model_id, version, and accuracy, an index on (model_id, version) that includes accuracy eliminates table lookups entirely.

**Partial indexes** index only rows matching a condition. An index on predictions WHERE status = 'failed' is small and fast if most predictions succeed. Use these for monitoring queries that focus on anomalies.

**When not to index:** Do not index columns with very low cardinality (boolean flags) unless combined with selective columns. Do not index columns you never filter or sort on. Every index slows writes and consumes storage.

## Partitioning Strategies

When a single table grows beyond what one machine can handle, partition it.

**Range partitioning** splits data by value ranges (predictions from January in one partition, February in another). Natural for time-series data. Risk: hotspots if most queries hit the current time range.

**Hash partitioning** distributes data uniformly across partitions by hashing a key. Eliminates hotspots but makes range queries expensive (they must scan all partitions). Use for high-cardinality keys like user_id or request_id.

**Hotspot avoidance:** If one key receives disproportionate traffic (a popular model getting most prediction requests), add a random suffix to the partition key or use a composite partition key that spreads load.

**Partition pruning:** Design your partition scheme so that common queries touch only one or a few partitions. If you partition predictions by date and most queries filter by date, the database skips irrelevant partitions entirely.

## Replication Patterns

Replication provides durability and read scalability.

**Leader-follower (primary-replica):** One node handles all writes; replicas handle reads. Simple and well-understood. Replication lag means replicas may serve stale data. Use for ML metadata stores where slight staleness is acceptable for read queries.

**Multi-leader:** Multiple nodes accept writes, typically in different data centers. Useful for geo-distributed ML platforms where teams in different regions need low-latency writes. Conflict resolution is complex -- use last-writer-wins for simple cases or application-level resolution for critical data.

**Leaderless (Dynamo-style):** Any node accepts reads and writes. Uses quorum reads and writes (W + R > N) to ensure consistency. Highly available but harder to reason about. Use when availability during network partitions matters more than strong consistency.

## Consistency Models

**Strong consistency:** Every read returns the most recent write. Required when promoting a model to production -- you cannot tolerate a serving node loading a stale model version because it read from a lagging replica.

**Eventual consistency:** Reads may return stale data, but all replicas converge eventually. Acceptable for prediction logs, experiment browsing, and monitoring dashboards where seconds-old data is fine.

**Causal consistency:** If operation A causally precedes operation B, every node sees A before B. Useful when an experiment's evaluation metrics must be visible before its promotion status changes -- readers should never see a promoted model without its metrics.

**Practical rule:** Use strong consistency for the model registry and promotion workflow. Use eventual consistency for prediction logs, monitoring metrics, and experiment browsing. Use causal consistency when operations have dependencies that must be preserved.

## Schema Design Patterns for ML

### Feature Tables

Store features in a format optimized for both training (bulk reads) and serving (point lookups).

- **Offline feature table:** Columnar format (Parquet, Delta Lake) partitioned by entity and date. Optimized for full-scan reads during training. Include a timestamp column for point-in-time correct joins.
- **Online feature table:** Key-value store (Redis, DynamoDB) keyed by entity_id. Optimized for single-entity lookups at serving time with sub-millisecond latency. Store only the latest feature values.

### Prediction Logs

Append-only table with: prediction_id, model_version, input_features (JSON or structured), prediction_output, confidence_score, timestamp, latency_ms, and optional ground_truth (filled later when labels arrive).

Partition by date. Index on model_version and timestamp for monitoring queries. Retain raw prediction logs for at least 90 days for debugging and drift analysis.

### Model Metadata

Relational schema linking models to experiments, datasets, metrics, and artifacts:

- **models** table: model_id, name, description, created_by, created_at.
- **model_versions** table: version_id, model_id, artifact_path, training_data_ref, config_hash, status (staging/production/archived), promoted_at.
- **evaluation_metrics** table: version_id, metric_name, metric_value, slice_name, evaluated_at.
- **experiments** table: experiment_id, model_id, hypothesis, parameters (JSON), started_at, completed_at.

Use foreign keys to enforce referential integrity. The model registry is a source of truth -- it must be consistent.

### Experiment Results

Wide table or EAV (entity-attribute-value) pattern for flexible metric storage. Each experiment may track different hyperparameters and metrics. A JSON column for parameters and a normalized metrics table provides the best balance of flexibility and queryability.

## When to Use This

- Starting a new ML project and choosing the storage layer.
- Migrating from file-based storage (CSV, pickle files) to a proper database.
- Designing the schema for a feature store, model registry, or prediction logging system.
- Investigating slow queries in an existing ML platform.
- Scaling an ML system that has outgrown a single database instance.

## Red Flags to Watch For

- Using a single database type for all workloads (relational DB for time-series metrics, document store for transactional model registry).
- No indexes on columns used in WHERE clauses of frequent queries.
- Storing features as unstructured blobs with no schema validation.
- No partitioning strategy for tables that grow unboundedly (prediction logs).
- Strong consistency configured everywhere, causing unnecessary latency for workloads that tolerate staleness.
- No replication for the model registry -- a single node failure makes it impossible to know which model is in production.
- Prediction logs with no retention policy, growing until disk fills.
- Feature tables without timestamps, making point-in-time correct training joins impossible and introducing label leakage.
