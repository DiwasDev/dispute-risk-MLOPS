# API Design for ML Systems

## Core Principle

An API is a contract between your system and every consumer that depends on it. A well-designed API makes the right thing easy and the wrong thing hard. For ML systems, this means prediction endpoints must be as reliable and predictable as any database query -- consumers should never need to understand your model internals to use your service correctly.

## REST Principles

REST is the default choice for external-facing ML APIs. Follow resource-oriented design:

- **Resources are nouns, not verbs.** Use `/predictions`, not `/getPrediction`. Use `/models/{model_id}/predictions`, not `/runModel`.
- **HTTP verbs carry the action.** GET for retrieval (model metadata, prediction status), POST for creation (new prediction request), PUT for full replacement, PATCH for partial update, DELETE for removal.
- **Status codes communicate outcomes.** 200 for success, 201 for created, 202 for accepted (async prediction queued), 400 for bad input (invalid features), 404 for not found (unknown model version), 422 for valid syntax but semantically wrong input (feature values out of expected range), 429 for rate limited, 500 for server error, 503 for model loading or warmup.
- **Pagination for list endpoints.** Use cursor-based pagination for prediction logs and experiment results. Offset-based pagination breaks when new records are inserted. Return `next_cursor` in the response body.
- **Consistent error format.** Every error response should include an error code (machine-readable), message (human-readable), and details (field-level validation errors). Never return raw stack traces.

## API Versioning Strategies

**URL path versioning** (`/v1/predictions`, `/v2/predictions`) is the simplest and most explicit. Consumers know exactly which version they are calling. Use this as the default.

**Header versioning** (`Accept: application/vnd.myapi.v2+json`) keeps URLs clean but is harder to test in a browser and easier to forget. Use this only when you have sophisticated API consumers who manage headers programmatically.

**Never version by query parameter** (`/predictions?version=2`). It conflates versioning with filtering and breaks caching.

**Versioning discipline:** support at most two major versions simultaneously. Deprecation notices should go out at least 90 days before shutdown. Version the prediction schema separately from the model version -- a model update should not require an API version bump if the request/response schema is unchanged.

## gRPC for Internal Services

Use gRPC for communication between internal ML microservices. Choose gRPC over REST when:

- **Low-latency inter-service calls** are required (feature store lookups, model ensemble aggregation).
- **Streaming** is needed (streaming predictions, real-time feature updates).
- **Strongly typed contracts** matter (protobuf schemas enforce types at compile time, preventing the stringly-typed bugs common in JSON APIs).
- **Polyglot services** need to communicate (protobuf generates clients for Python, Go, Java, C++ from a single schema).

Keep REST for external consumers and browser-facing endpoints. gRPC requires HTTP/2 and is harder to debug with standard tools.

## GraphQL Tradeoffs

GraphQL offers flexibility -- consumers request exactly the fields they need. For ML systems, it is useful for model metadata APIs where different consumers (dashboards, CLI tools, notebooks) need different subsets of experiment data.

**Downsides:** N+1 query problems require careful DataLoader implementation. Caching is harder than REST (no URL-based cache keys). Query complexity can be unbounded without depth limiting. For prediction endpoints, GraphQL adds complexity without benefit -- predictions have a fixed schema.

**Rule of thumb:** Use GraphQL for metadata and experiment browsing APIs. Use REST or gRPC for prediction endpoints.

## Authentication Patterns

- **API keys** for server-to-server communication. Simple, but rotate regularly and never embed in client-side code.
- **OAuth2 with JWT** for user-facing APIs. Use short-lived access tokens (15 minutes) with refresh tokens. Include scopes to limit what each consumer can do (read predictions, submit training jobs, promote models).
- **Mutual TLS** for internal service-to-service communication in high-security environments.
- **Never** pass model predictions through unauthenticated endpoints. Even internal APIs should authenticate -- zero-trust networking applies to ML services.

## Rate Limiting Design

Rate limiting protects your serving infrastructure from abuse and ensures fair access:

- **Per-consumer limits** based on API key or OAuth client. Different tiers for different consumers.
- **Sliding window** algorithm for smooth enforcement (not fixed windows that allow bursts at boundaries).
- **Return 429 with Retry-After header** so clients know when to retry.
- **Separate limits for prediction endpoints vs metadata endpoints.** Predictions are compute-heavy; metadata queries are cheap.
- **For batch prediction APIs,** limit by total items per request and requests per minute.

## Idempotency

Prediction requests should be idempotent when possible. Use idempotency keys for operations that create side effects (logging predictions, triggering retraining).

- Client sends `Idempotency-Key: <uuid>` header.
- Server stores the response for that key and returns the cached response on retry.
- Key expiration should be 24 hours minimum to handle delayed retries.
- This prevents duplicate prediction logs, double-charged credits, and duplicate training triggers.

## ML Prediction Endpoint Design

### Single Prediction

```
POST /v1/models/{model_id}/predictions
{
  "features": {"age": 35, "income": 75000, "category": "A"},
  "options": {"explain": true, "threshold": 0.5}
}
```

Return prediction, confidence, model version, and optional explanation. Always include the model version in the response so consumers can correlate predictions with specific model releases.

### Batch Prediction

```
POST /v1/models/{model_id}/predictions/batch
{
  "instances": [{"features": {...}}, {"features": {...}}],
  "options": {"explain": false}
}
```

Set a maximum batch size (e.g., 1000 instances). For larger batches, use async patterns.

### Async Prediction

For heavy models or large batches, return 202 Accepted with a job ID. The client polls a status endpoint or receives a webhook callback when results are ready.

```
POST /v1/models/{model_id}/predictions/async -> 202 {"job_id": "abc123"}
GET /v1/predictions/jobs/abc123 -> {"status": "completed", "results_url": "..."}
```

## When to Use This

- Designing a new ML serving API from scratch.
- Migrating from notebook-based predictions to a production API.
- Adding new consumers to an existing prediction service.
- Reviewing an API design for consistency and correctness before launch.

## Red Flags to Watch For

- Prediction endpoints that return 200 for every request, even when the model fails to load or features are invalid.
- No API versioning strategy, meaning any model schema change breaks all consumers simultaneously.
- Authentication tokens with no expiration or rotation policy.
- Batch endpoints with no size limit, allowing a single request to overwhelm the serving infrastructure.
- No idempotency mechanism for endpoints that log predictions or trigger side effects.
- Error responses that leak internal details (model file paths, stack traces, infrastructure names).
- Using GraphQL for prediction endpoints where a fixed REST schema would be simpler and faster.
- No rate limiting on compute-heavy prediction endpoints.
