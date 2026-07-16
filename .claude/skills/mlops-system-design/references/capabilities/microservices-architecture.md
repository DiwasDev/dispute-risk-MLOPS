# Microservices Architecture for ML Systems

## Core Principle

Microservices are an organizational scaling strategy, not a technical silver bullet. They let independent teams deploy independent services independently. If you do not have independent teams or independent deployment needs, microservices add complexity without benefit. Start monolithic. Extract services when you have a concrete reason -- not because it sounds modern.

## The Monolith-First Principle

A well-structured monolith is the right starting point for every ML system. It gives you:

- **Fast iteration:** Change any part of the system in a single codebase, deploy in a single step.
- **Simple debugging:** One process, one log stream, no distributed tracing needed.
- **No network overhead:** Function calls are nanoseconds; network calls are milliseconds.
- **Easy refactoring:** Move code between modules without cross-service migration.

**When to extract a service:**
- A component has a fundamentally different scaling profile (the prediction API needs 50 replicas but the training orchestrator needs 1).
- A component has a different deployment cadence (the feature pipeline changes weekly but the serving layer changes daily).
- A component needs a different technology stack (training in Python, serving in C++ for latency).
- An independent team owns a component and needs to deploy without coordinating with others.
- A component has a different reliability requirement (serving must be 99.99% available but batch training can tolerate failures and retries).

**When not to extract:**
- "Because microservices are best practice." They are not universal best practice.
- To enforce code boundaries. Use modules, packages, and interfaces within the monolith instead.
- Because one team read about it in a blog post. Organizational alignment matters more than architecture diagrams.

## Service Boundary Design

The hardest part of microservices is drawing the boundaries correctly. Get it wrong and you end up with a distributed monolith that has all the costs of distribution and none of the benefits.

**Use bounded contexts from Domain-Driven Design.** A bounded context is a boundary within which a term has a consistent meaning. In ML systems, natural bounded contexts include:

- **Feature platform:** Owns feature computation, storage, and serving. Knows about feature definitions, data sources, and freshness requirements. Does not know about models.
- **Training platform:** Owns experiment tracking, model training, and evaluation. Knows about datasets, hyperparameters, and metrics. Does not know about serving infrastructure.
- **Serving platform:** Owns model deployment, traffic management, and prediction API. Knows about latency budgets, scaling, and routing. Does not know about training.
- **Monitoring platform:** Owns drift detection, alerting, and dashboards. Knows about metrics, thresholds, and notification channels. Does not know about model internals.

Each bounded context has its own data model. A "model" in the training context has hyperparameters and evaluation metrics. A "model" in the serving context has an artifact path and latency profile. These are different representations of the same entity.

## Inter-Service Communication

### Synchronous Communication

**REST** for external-facing APIs and low-frequency inter-service calls. Simple, well-tooled, debuggable with curl.

**gRPC** for high-frequency, latency-sensitive internal calls. Feature store lookups from the serving layer, model ensemble aggregation, real-time feature computation. Protobuf schemas enforce type safety at compile time.

**When to use synchronous:** The caller needs the response before it can continue. The call completes in milliseconds. Failure of the callee should propagate to the caller.

### Asynchronous Communication

**Message queues (SQS, RabbitMQ)** for task distribution. One message, one consumer. Use for: training job dispatch, evaluation triggers, retraining requests.

**Event streams (Kafka, Pub/Sub)** for event broadcasting. One event, many consumers. Use for: model promotion events (serving, monitoring, and alerting all need to know), feature update events, prediction logging.

**When to use asynchronous:** The caller does not need an immediate response. The operation can tolerate seconds or minutes of delay. Multiple services need to react to the same event. You want to decouple the sender from the receiver.

## Service Discovery

Services need to find each other without hardcoded addresses.

- **DNS-based discovery (Kubernetes Services):** The simplest pattern. Each service gets a stable DNS name. The platform handles routing to healthy instances.
- **Service registry (Consul, etcd):** Services register themselves on startup and deregister on shutdown. Clients query the registry to find service instances. More flexible but more complex.
- **Sidecar proxy (Envoy, Istio):** A proxy runs alongside each service, handling discovery, load balancing, retries, and TLS. The application code is unaware of the mesh. Powerful but adds operational complexity.

**Start with DNS-based discovery.** Move to a service mesh only when you need features like mutual TLS, advanced traffic routing, or cross-service observability that justify the complexity.

## Data Ownership

**Each service owns its data. This is non-negotiable.** No shared databases. No other service reads from or writes to another service's tables.

**Why:** A shared database couples services at the data layer. Any schema change requires coordinating all services that access the table. Any query can create unexpected load on another service's data. Independent deployment becomes impossible.

**How to share data without shared databases:**
- **API calls:** Service A queries Service B's API to get data. Simple but creates runtime coupling.
- **Events:** Service B publishes events when data changes. Service A consumes events and maintains its own local copy. Decoupled but eventually consistent.
- **Data products:** A service publishes a well-defined data product (a dataset, a table, an API) with a schema contract. Other services consume the product, not the raw data.

## The Distributed Monolith Anti-Pattern

A distributed monolith looks like microservices on the architecture diagram but behaves like a monolith in practice. Symptoms:

- Services must be deployed together because they share a database or have tightly coupled APIs.
- A change in one service requires coordinated changes in two or three other services.
- You cannot run or test one service without running all its dependencies.
- Inter-service calls are synchronous chains three or four services deep.
- There is a "core" service that every other service depends on, creating a single point of failure.

**The fix is not more microservices.** The fix is better boundaries. Merge tightly coupled services back into one. Introduce asynchronous communication to break synchronous chains. Give each service its own data store.

## The Strangler Fig Migration Pattern

When migrating from a monolith to services, do not rewrite everything at once. Instead:

1. Identify one bounded context to extract.
2. Build the new service alongside the monolith.
3. Route traffic for that context to the new service (using a proxy or router).
4. Verify the new service works correctly (shadow traffic, then canary, then full).
5. Remove the old code from the monolith.
6. Repeat for the next bounded context.

The monolith shrinks gradually, like a tree strangled by a fig vine. At each step, the system is fully functional. There is never a big-bang cutover.

## Sidecar and Service Mesh for Cross-Cutting Concerns

Cross-cutting concerns (TLS, authentication, logging, tracing, rate limiting, circuit breaking) should not be duplicated in every service's application code.

**Sidecar pattern:** Deploy a proxy (Envoy) alongside each service. The proxy handles cross-cutting concerns transparently. The application code stays focused on business logic.

**Service mesh (Istio, Linkerd):** A fleet of sidecars managed by a control plane. Provides consistent policy enforcement, observability, and traffic management across all services.

**Use a service mesh when:** You have more than 10 services, you need mutual TLS between all services, you need advanced traffic routing (canary by header, fault injection for chaos testing), or your observability requirements demand distributed tracing without application instrumentation.

## When to Use This

- Deciding whether to keep a monolithic ML system or start extracting services.
- Drawing service boundaries for a new ML platform.
- Debugging coupling issues in an existing microservices architecture.
- Planning a migration from a monolith to services.
- Choosing communication patterns between ML platform components.

## Red Flags to Watch For

- Extracting services before the monolith has clear module boundaries.
- Services that share a database, defeating the purpose of service independence.
- Synchronous call chains spanning more than two services for a single request.
- No async communication -- every inter-service interaction is request-response.
- A "gateway" service that routes everything and becomes a bottleneck and single point of failure.
- Service boundaries drawn around technical layers (API service, database service) instead of business domains.
- Teams deploying services in lockstep because of tight coupling -- a distributed monolith.
- Adopting a service mesh for three services when DNS-based discovery would suffice.
