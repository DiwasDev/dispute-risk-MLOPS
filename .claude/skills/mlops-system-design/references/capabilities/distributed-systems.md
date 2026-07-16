# Distributed Systems for ML

## Core Principle

Distribution is not a feature -- it is a tax you pay to achieve scale or availability that a single machine cannot provide. Every network call introduces latency, partial failure, and ordering ambiguity that do not exist in single-process systems. Distribute only what you must, and understand the costs of every boundary you introduce.

## CAP Theorem -- What It Actually Means

CAP is widely misunderstood. It does not say "pick two of three." It says: **during a network partition, you must choose between consistency and availability.** When the network is healthy, you can have both.

- **Consistency (C):** Every read returns the most recent write or an error.
- **Availability (A):** Every request receives a non-error response, though it may not reflect the most recent write.
- **Partition tolerance (P):** The system continues operating despite network partitions between nodes.

Network partitions happen in any distributed system. You cannot opt out of P. So the real choice is: when a partition occurs, do you return stale data (AP) or refuse to serve (CP)?

**For ML systems:** The model registry should be CP -- serving a stale model version during a partition is dangerous. Prediction logging can be AP -- losing a few log entries during a partition is acceptable if the system stays available. Feature serving depends on the use case: if stale features cause bad predictions with high business cost, choose CP; if slightly stale features are acceptable, choose AP.

## Consistency Models in Practice

Beyond CAP, real systems offer a spectrum of consistency:

**Linearizability** -- the strongest guarantee. Every operation appears to take effect at a single point in time. Expensive because it requires coordination between nodes on every write. Use for model promotion (you need all serving nodes to agree on which model is live).

**Sequential consistency** -- all operations appear in some total order consistent with each process's local order. Slightly weaker than linearizability but easier to implement.

**Causal consistency** -- preserves cause-and-effect ordering. If process A writes and tells process B, then B's subsequent read sees A's write. Does not order unrelated operations. Good for experiment tracking where metric writes must be visible before status updates.

**Eventual consistency** -- all replicas converge eventually, but reads may return stale data at any moment. Cheapest and most available. Use for prediction logs, monitoring dashboards, and any read path where seconds-old data is acceptable.

## Consensus Protocols

When multiple nodes must agree on a value (which model is the leader, what is the committed log sequence), you need consensus.

**Raft** is the go-to protocol for understanding and implementation. It elects a leader, the leader handles all writes, and followers replicate. If the leader fails, a new election happens. Raft is used in etcd, Consul, and CockroachDB. Understand Raft before trying to understand anything else.

**Paxos** is the theoretical foundation. It is correct but notoriously hard to implement. Most practical systems use Raft or a Paxos variant. Know that Paxos exists and that Raft is its understandable descendant.

**When you need consensus in ML systems:** Coordinating model promotion across multiple serving replicas. Electing a leader for distributed training coordination. Maintaining a consistent feature store catalog.

**When you do not need consensus:** Prediction logging (append to local log, replicate asynchronously). Monitoring metric collection (eventual consistency is fine). Experiment tracking (causal consistency suffices).

## Distributed Transactions

When an operation spans multiple services or databases, you need a strategy for atomicity.

### Two-Phase Commit (2PC)

A coordinator asks all participants to prepare, then tells them all to commit or abort. Guarantees atomicity but has serious downsides: the coordinator is a single point of failure, all participants are blocked during the protocol, and any participant failure blocks the entire transaction.

**Use 2PC when:** You have a small number of participants, the transaction is short-lived, and you control all participants. Example: atomically writing a model artifact to storage and its metadata to the registry.

### Sagas

A saga is a sequence of local transactions where each step has a compensating action that undoes it. If step 3 fails, you run compensating actions for steps 2 and 1 in reverse.

**Orchestration sagas** use a central coordinator that tells each service what to do. Easier to understand and debug. The coordinator is a single point of failure but can be made highly available.

**Choreography sagas** use events. Each service listens for events and reacts. No central coordinator, but the flow is harder to follow and debug.

**Use sagas when:** The transaction spans multiple services with different databases. Example: a model deployment saga that (1) validates the model, (2) deploys to staging, (3) runs smoke tests, (4) promotes to production. If smoke tests fail, compensating actions undeploy from staging and mark the model as failed.

## Clock Synchronization Challenges

Distributed systems cannot rely on synchronized clocks. NTP can drift by milliseconds, and even with GPS-synced clocks (Google Spanner's TrueTime), there is always uncertainty.

**Consequences for ML systems:**
- **Prediction timestamps** from different serving nodes may not be strictly ordered. Do not use wall-clock timestamps as the sole ordering mechanism for prediction logs.
- **Feature freshness** cannot be determined by comparing timestamps across machines. Use logical clocks (Lamport timestamps, vector clocks) or centralized timestamp services for ordering guarantees.
- **Training data cutoffs** based on timestamps may include or exclude data depending on clock skew. Use monotonically increasing sequence numbers from a single source when exact cutoffs matter.

## Idempotency in Distributed Systems

Network failures cause retries. Retries cause duplicate processing. Idempotency ensures that processing the same request multiple times produces the same result as processing it once.

- **Assign unique IDs at the source.** Every prediction request, training job trigger, and retraining event gets a UUID from the caller.
- **Check before processing.** Before executing a side effect, check if the ID has already been processed.
- **Store results atomically with the ID.** Write the result and mark the ID as processed in the same transaction.
- **Design operations to be naturally idempotent** when possible. Setting a model's status to "production" is idempotent. Incrementing a counter is not.

## Failure Modes

### Partial Failures

In a distributed system, some nodes succeed while others fail. This is the fundamental difference from single-machine systems. A prediction request may reach the model but the response may be lost. The feature store may be available but one replica may be stale.

**Design for partial failure:** Use timeouts (never wait forever), retries with exponential backoff and jitter, circuit breakers to stop calling failing services, and fallbacks (cached predictions, default values, graceful degradation).

### Byzantine Faults

A Byzantine fault occurs when a node behaves maliciously or arbitrarily (sends incorrect data, lies about its state). Most internal ML systems do not need Byzantine fault tolerance -- that level of mistrust is for blockchain or adversarial environments.

**When to consider:** If your ML system accepts model artifacts from untrusted sources, validate them cryptographically. If feature data comes from external partners, validate distributions before ingestion.

## Distributed System Anti-Patterns

### The Distributed Monolith

Services are deployed independently but are tightly coupled through shared databases, synchronous call chains, or coordinated deployments. You get the complexity of distribution with none of the benefits. **Fix:** Each service owns its data. Communication is through well-defined APIs or events. Services can be deployed independently.

### Chatty Services

Services make dozens of synchronous calls to each other to handle a single request. Latency compounds, failure probability increases, and debugging becomes a nightmare. **Fix:** Batch related calls, cache aggressively, consider denormalizing data so a service has what it needs locally, or merge chatty services back into one.

### Cascading Failures

Service A depends on B, which depends on C. C slows down, B's thread pool fills up waiting for C, A's thread pool fills up waiting for B. The entire system fails because of one slow service. **Fix:** Circuit breakers at every service boundary. Timeouts that are shorter than the caller's timeout. Bulkheads that isolate failure domains. Load shedding that drops excess traffic gracefully.

### Retry Storms

When a service fails, all callers retry simultaneously, creating a thundering herd that prevents recovery. **Fix:** Exponential backoff with random jitter. Retry budgets (limit the fraction of requests that are retries). Client-side circuit breakers that stop retrying after repeated failures.

## When to Use This

- Designing an ML platform that spans multiple services or data centers.
- Debugging latency or reliability issues in a distributed ML pipeline.
- Deciding whether to split a monolithic ML system into services.
- Choosing consistency and replication strategies for feature stores or model registries.
- Investigating why prediction results are inconsistent across serving replicas.

## Red Flags to Watch For

- Services communicate through a shared database instead of well-defined APIs.
- No timeouts on inter-service calls, allowing one slow service to block the entire system.
- Synchronous call chains spanning three or more services for a single prediction request.
- Wall-clock timestamps used as the sole ordering mechanism for events across machines.
- No circuit breakers or fallbacks -- a single service failure brings down the entire platform.
- Retry logic without exponential backoff or jitter, causing thundering herd on recovery.
- Consensus protocols used where eventual consistency would suffice, adding unnecessary latency.
- The team cannot explain what happens to a prediction request if any single service is unavailable.
