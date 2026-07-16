# Scalability Patterns for ML Systems

## Core Principle

Scalability is not about handling more load -- it is about maintaining performance characteristics as load grows. A system that serves 100 predictions per second at 50ms p99 latency is scalable only if it can serve 10,000 predictions per second at a similar latency with proportional resource increases. Plan for the growth you expect, not the growth you fantasize about. Premature scaling is as wasteful as no scaling plan at all.

## Horizontal vs Vertical Scaling

**Vertical scaling** means adding more CPU, memory, or GPU to a single machine. It is simple -- no code changes, no distributed systems complexity. But it has a hard ceiling (the biggest machine available) and a single point of failure.

**Horizontal scaling** means adding more machines. It requires your application to be designed for distribution but has no theoretical ceiling.

**Decision framework:**
- **Stateless services (API servers, prediction endpoints):** Always prefer horizontal scaling. Deploy multiple replicas behind a load balancer. Each replica handles requests independently. This is the default for ML serving.
- **Databases:** Scale vertically first. A bigger database instance is simpler than sharding. When vertical limits are reached, add read replicas for read-heavy workloads before considering sharding. Shard only when you must -- it adds permanent operational complexity.
- **Training workloads:** Scale vertically (bigger GPU) before distributing training. Distributed training adds synchronization overhead, communication bottlenecks, and debugging complexity. A single A100 handles most tabular and moderate-sized deep learning workloads.
- **Feature computation:** Scale horizontally with a distributed compute framework (Spark, Dask) when data exceeds single-machine memory.

## Caching Strategies

Caching is the highest-leverage scalability tool. A cache hit avoids the entire computation chain.

### Cache-Aside (Lazy Loading)

Application checks the cache first. On miss, it queries the database, writes the result to cache, and returns it. The most common pattern.

**Use for:** Feature lookups, model metadata, configuration. The application controls what gets cached and when.

**Risk:** Cache stampede -- when a popular key expires, hundreds of requests simultaneously hit the database. Mitigate with lock-based cache fill (only one request queries the DB, others wait) or stale-while-revalidate (serve stale data while refreshing in the background).

### Read-Through

The cache itself loads data from the database on a miss. The application only talks to the cache. Simpler application code but the cache must know how to query the source.

**Use for:** Feature stores where the online store acts as a read-through cache for the offline store.

### Write-Through

Every write goes to the cache and the database synchronously. The cache is always up to date but writes are slower.

**Use for:** Model registry entries where consistency is critical. You never want to serve a stale model version from cache.

### Write-Behind (Write-Back)

Writes go to the cache immediately and are asynchronously flushed to the database. Fast writes but risk of data loss if the cache fails before flushing.

**Use for:** Prediction logging where write latency matters and occasional log loss is tolerable.

### Choosing the Right Strategy

- If consistency matters more than latency: write-through.
- If write performance matters more than durability: write-behind.
- If you want simplicity and can tolerate cache misses: cache-aside.
- If the cache is the primary interface: read-through.

## CDN Placement

CDNs cache static content at edge locations close to users. For ML systems, CDNs are relevant for:

- **Model artifacts** served to edge devices (mobile, IoT). Cache model files at CDN edges to reduce download latency and origin bandwidth.
- **Batch prediction results** served as static files. If predictions are precomputed and served as JSON/CSV, a CDN handles the distribution.
- **Not for real-time predictions.** Dynamic prediction requests must hit your serving infrastructure, not a CDN.

## Database Read Replicas

Add read replicas when read traffic overwhelms the primary database. Route read queries (experiment browsing, dashboard queries, prediction log analysis) to replicas. Keep writes on the primary.

**Replication lag caveat:** After writing a new model version to the primary, a read from a replica might not see it yet. For read-after-write consistency, route those specific reads to the primary or use synchronous replication for critical tables.

## Sharding Strategies and Their Costs

Sharding splits data across multiple database instances. Each shard holds a subset of the data.

**Hash sharding:** Distribute rows by hashing a key (e.g., user_id). Even distribution, but range queries across shards are expensive.

**Range sharding:** Split by value ranges (e.g., date ranges). Efficient for range queries but prone to hotspots (the current date shard gets all writes).

**Costs of sharding:** Cross-shard queries require scatter-gather. Joins across shards are impractical. Rebalancing shards when adding nodes is operationally complex. Schema changes must be coordinated across all shards. Transactions spanning shards require distributed coordination.

**Rule:** Exhaust vertical scaling and read replicas before sharding. Most ML systems never need sharding for their metadata stores. Prediction logs and feature tables are the most likely candidates.

## Connection Pooling

Database connections are expensive to create. A connection pool maintains a set of reusable connections.

- **Size the pool correctly.** Too small: requests queue waiting for connections. Too large: the database is overwhelmed by concurrent connections.
- **Formula:** Start with `pool_size = 2 * num_cpu_cores + 1` for CPU-bound workloads, larger for I/O-bound workloads.
- **Use PgBouncer or ProxySQL** as an external connection pooler when many application instances share a database.
- **For ML serving:** Each prediction endpoint replica needs its own pool to the feature store and model registry. Monitor connection wait time as a scaling signal.

## Async Processing

Not every operation needs to complete before the API responds.

- **Prediction logging:** Write to a local buffer, flush asynchronously. Do not make prediction latency depend on log write latency.
- **Model evaluation:** Queue evaluation jobs after training completes. The training API returns immediately with a job ID.
- **Retraining triggers:** Drift detection publishes an event to a message queue. A separate consumer picks it up and starts retraining. No synchronous chain.
- **Feature computation:** Batch feature jobs run on a schedule. Real-time features are computed asynchronously and pushed to the online store.

**Job queue choices:** Use Redis or SQS for simple task queues. Use Celery or Temporal for orchestrated multi-step workflows. Use Kafka for high-throughput event streaming.

## Load Balancing Algorithms

**Round-robin:** Distribute requests sequentially across replicas. Simple and fair when all replicas have equal capacity and all requests have equal cost.

**Least connections:** Route to the replica with the fewest active connections. Better when request processing times vary (some predictions are faster than others).

**Consistent hashing:** Map requests to specific replicas based on a hash of the request key. Useful when you want cache locality (same user always hits the same replica, maximizing local cache hit rate). Only a fraction of keys remap when replicas are added or removed.

**Weighted algorithms:** Assign weights to replicas based on capacity. Use when replicas have different hardware (some have GPUs, some do not) or when canary deployments route a small percentage of traffic to a new model.

## Auto-Scaling Patterns

- **CPU-based scaling:** Scale out when average CPU exceeds 70%. Simple but reactive -- by the time CPU spikes, latency has already degraded.
- **Request-rate scaling:** Scale based on requests per second. More predictive than CPU. Set thresholds based on load testing.
- **Latency-based scaling:** Scale out when p95 latency exceeds your SLO. Directly tied to user experience.
- **Predictive scaling:** Use historical patterns to scale proactively (e.g., scale up before the morning traffic surge). Available in AWS and GCP auto-scalers.
- **Queue depth scaling:** For async workers, scale based on the number of pending jobs. More workers when the queue grows, fewer when it drains.
- **Cooldown periods:** After scaling out, wait before scaling in to avoid thrashing. Typical cooldown: 5-10 minutes.

## When to Use This

- An ML system is approaching capacity limits and you need to plan for growth.
- Prediction latency is increasing under load and you need to identify bottlenecks.
- Designing a new ML platform and choosing the scaling strategy for each component.
- Evaluating whether to shard a database or optimize the current setup first.
- Setting up auto-scaling for ML serving endpoints.

## Red Flags to Watch For

- Sharding the database before exhausting vertical scaling and read replicas.
- No caching layer between the prediction endpoint and the feature store.
- Synchronous logging in the prediction hot path, adding latency to every request.
- Auto-scaling based only on CPU with no latency-based signals.
- Connection pools sized without load testing, causing either queuing or database overload.
- All traffic routed through a single load balancer with no health checks on backend replicas.
- No async processing for non-latency-critical operations like logging, evaluation, and drift detection.
- Horizontal scaling of stateful services without addressing state distribution.
