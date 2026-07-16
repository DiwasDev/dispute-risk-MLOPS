# Messaging and Event-Driven Architecture for ML Systems

## Core Principle

Asynchronous messaging decouples producers from consumers in time, space, and implementation. The producer does not need to know who consumes the message, when they consume it, or how they process it. For ML systems, this decoupling is essential -- training, serving, monitoring, and retraining operate on fundamentally different timescales and should not be locked in synchronous call chains.

## Message Queues vs Event Streams

These are different tools for different problems. Do not use them interchangeably.

### Message Queues

A message queue distributes tasks to workers. Each message is consumed by exactly one consumer. Once consumed, the message is removed.

**Characteristics:** Point-to-point delivery. Competing consumers (multiple workers pull from the same queue). No replay -- once processed, the message is gone. Order is best-effort (strict ordering requires single-consumer configuration).

**Use for:** Training job dispatch (one worker trains one model). Evaluation task distribution. Retraining triggers (one trigger, one retraining run). Prediction batch processing (each worker handles a chunk).

### Event Streams

An event stream is an append-only log. Events are published to a topic and remain available for a configurable retention period. Multiple independent consumers can read the same events at their own pace.

**Characteristics:** Publish-subscribe delivery. Multiple consumer groups read independently. Full replay capability -- a new consumer can start from the beginning. Strict ordering within a partition.

**Use for:** Model promotion events (serving, monitoring, alerting, and audit all need to know). Prediction logging (multiple consumers: monitoring, drift detection, billing). Feature update events (training pipeline and serving pipeline both consume). Data change events (CDC from source systems feeding the feature pipeline).

### Decision Framework

- One message, one consumer, task distribution: **message queue.**
- One event, many consumers, event log: **event stream.**
- Need replay for debugging or new consumers: **event stream.**
- Simple task dispatch with no replay needs: **message queue.**

## Kafka Architecture

Kafka is the dominant event streaming platform for ML systems. Understanding its architecture is essential.

**Topics** are named channels for events. One topic per event type: `model-promoted`, `prediction-logged`, `feature-updated`, `drift-detected`.

**Partitions** are the unit of parallelism within a topic. Each partition is an ordered, append-only log. A topic with 12 partitions can be consumed by up to 12 consumers in parallel. Choose the partition key carefully -- events with the same key go to the same partition and are processed in order. For prediction logs, partition by model_id to keep each model's predictions ordered.

**Consumer groups** enable independent consumption. Each consumer group tracks its own offset (position in the log). The monitoring consumer group and the drift-detection consumer group both read from `prediction-logged` independently, at their own pace, without interfering with each other.

**Exactly-once semantics** in Kafka require idempotent producers (enabled by configuration) and transactional consumers (read-process-write in a single transaction). In practice, design for at-least-once delivery and make consumers idempotent -- it is simpler and more robust.

## Event-Driven Architecture Patterns

### Event Sourcing

Store the sequence of events that led to the current state, not just the current state. The state is derived by replaying events.

**For ML systems:** Store every model lifecycle event (trained, evaluated, promoted, rolled-back, retired) rather than just the current status. Replay events to reconstruct the full history of any model. Useful for audit trails and debugging production incidents.

**Tradeoff:** Event replay can be slow for long histories. Use snapshots to speed up reconstruction. Event schema evolution requires careful handling (consumers must handle old event formats).

### CQRS (Command Query Responsibility Segregation)

Separate the write model (commands that change state) from the read model (queries that return state). Each can be optimized independently.

**For ML systems:** The write side handles model registration, promotion, and metric logging. The read side serves dashboards, experiment comparisons, and model metadata lookups. The write side can use an event store; the read side can use a denormalized database optimized for queries.

### Saga Orchestration vs Choreography

**Orchestration:** A central saga coordinator directs each step. The coordinator calls services in sequence, handles failures, and runs compensating actions. Easier to understand, debug, and monitor. The coordinator is a single point of failure (make it highly available).

**Choreography:** Each service listens for events and reacts. No central coordinator. Services are more decoupled, but the flow is implicit -- understanding the full saga requires reading multiple services' event handlers. Debugging is harder because there is no single place to see the saga's state.

**For ML deployment sagas:** Prefer orchestration. A deployment saga (validate model, deploy to staging, run smoke tests, promote to production) has a clear sequence and needs clear rollback. An orchestrator makes the flow explicit and auditable.

## Dead Letter Queues

When a consumer cannot process a message after multiple retries, send it to a dead letter queue (DLQ) instead of dropping it or retrying forever.

- Configure a maximum retry count (typically 3-5 attempts with exponential backoff).
- After exhausting retries, route the message to the DLQ.
- Monitor DLQ depth -- a growing DLQ indicates a systematic processing problem.
- Regularly review and reprocess DLQ messages after fixing the underlying issue.
- For ML pipelines: a DLQ on the training trigger queue catches malformed training requests that would otherwise be silently dropped.

## Message Ordering Guarantees

- **Kafka:** Ordered within a partition, not across partitions. If order matters for a specific entity (all events for model X must be processed in order), use the entity ID as the partition key.
- **SQS:** Standard queues offer best-effort ordering. FIFO queues guarantee ordering within a message group (similar to Kafka partitions) with a throughput limit of 300 messages/second per group.
- **RabbitMQ:** Ordered within a single queue consumed by a single consumer. Multiple consumers break ordering.
- **Design principle:** If ordering matters, ensure the ordering unit (entity ID, model ID) maps to a single partition or queue.

## Backpressure Handling

When producers generate events faster than consumers can process them, you need backpressure.

- **Kafka:** Consumers naturally apply backpressure by consuming at their own rate. The retention period acts as a buffer. If a consumer falls behind, events are available for replay until the retention period expires.
- **Queue-based:** Monitor queue depth. If it exceeds a threshold, scale consumers horizontally. If consumers cannot scale, throttle producers.
- **For ML systems:** Prediction logging producers should never be blocked by slow monitoring consumers. Use event streams so the serving path is unaffected by consumer speed.

## Choosing Between Kafka, RabbitMQ, SQS, and Pub/Sub

**Kafka:** High-throughput event streaming with replay. Use when you have multiple consumers for the same events, need event replay, or process more than 10,000 events per second. Operational overhead: significant (cluster management, partition rebalancing, schema registry).

**RabbitMQ:** Feature-rich message broker with flexible routing (exchanges, bindings, routing keys). Use for task distribution with complex routing logic. Lower throughput than Kafka but simpler for request-reply patterns. Operational overhead: moderate.

**AWS SQS:** Managed queue with zero operational overhead. Use for simple task distribution when you are on AWS and do not need replay or multiple consumers. FIFO variant for ordering. Integrates natively with Lambda for serverless processing.

**Google Pub/Sub:** Managed event streaming with Kafka-like semantics. Use when you are on GCP and want Kafka capabilities without managing a cluster. Supports multiple subscribers, message retention, and replay.

**Decision shortcut:** If you need replay and multiple consumers, use Kafka (or Pub/Sub on GCP). If you need simple task dispatch, use SQS (or Cloud Tasks on GCP). If you need complex routing, use RabbitMQ.

## When to Use This

- Designing communication between ML platform services (training, serving, monitoring).
- Replacing synchronous API calls that create tight coupling between ML components.
- Building a prediction logging pipeline that feeds multiple downstream consumers.
- Implementing retraining triggers based on drift detection events.
- Choosing a messaging technology for a new ML platform.

## Red Flags to Watch For

- Using a message queue when you need multiple independent consumers for the same event.
- Using an event stream for simple task dispatch where a queue would be simpler.
- No dead letter queue, causing failed messages to be retried forever or silently dropped.
- Partition key chosen without considering ordering requirements, causing out-of-order processing.
- No monitoring on consumer lag, allowing consumers to fall hours or days behind without detection.
- Synchronous API calls between services that should communicate asynchronously (training triggers, drift alerts, promotion notifications).
- Event schemas with no versioning strategy, making it impossible to evolve events without breaking consumers.
