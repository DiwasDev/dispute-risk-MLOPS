# ML Serving Architecture

## Core Principle

Serving is where ML meets reality. The best model in the world is worthless if it cannot deliver predictions at the latency, throughput, and reliability the business requires. Serving architecture is not an afterthought -- it determines what models are feasible, what features can be used, and how fast you can iterate. Design your serving layer before you finalize your model.

## Batch vs Real-Time vs Streaming Inference

The serving mode is a fundamental architectural decision. Choose based on three dimensions: latency requirements, throughput needs, and data freshness.

### Batch Inference

Precompute predictions for all entities on a schedule. Store results in a database or file system for later lookup.

**Choose batch when:**
- Predictions are needed for a known set of entities (all products, all users).
- Staleness of hours or days is acceptable (weekly demand forecasts, nightly recommendations).
- The model is computationally expensive and amortizing cost over bulk processing is efficient.
- You do not need to incorporate real-time signals at prediction time.

**Architecture:** Scheduled job (Airflow, cron) triggers a pipeline that loads the model, reads input data from the offline feature store, generates predictions, validates output distributions, and writes results to a serving database or object store.

**Advantages:** Simple infrastructure, easy to debug (all inputs and outputs are logged), cost-efficient (use spot instances). **Disadvantages:** Cannot incorporate real-time context, predictions may be stale by serving time.

### Real-Time Inference

Compute predictions on demand per request. The model runs synchronously in the request path.

**Choose real-time when:**
- Inputs are only available at request time (user's current context, live sensor data).
- Sub-second latency is required (fraud detection, search ranking, real-time pricing).
- The prediction must incorporate the latest available features.

**Architecture:** Load-balanced API endpoints running model servers. Each request fetches features from the online feature store, runs inference, and returns the prediction. The model is loaded into memory at server startup.

**Advantages:** Freshest possible predictions, can use real-time features. **Disadvantages:** Requires always-on infrastructure, latency-sensitive, more complex operational management.

### Streaming Inference

Consume events from a stream, compute predictions, and write results to another stream or database. Predictions are triggered by data events rather than API calls.

**Choose streaming when:**
- Predictions must be triggered by events (new transaction, sensor reading, user action).
- Near-real-time latency is acceptable (seconds, not milliseconds).
- You need to process a continuous flow of predictions without explicit API calls.
- The output feeds a downstream system rather than a user-facing response.

**Architecture:** Stream processor (Kafka Streams, Flink, Spark Streaming) consumes input events, fetches features, runs the model, and publishes prediction events. The model is embedded in the stream processor.

## Model Serving Frameworks

**TensorFlow Serving:** Production-grade serving for TensorFlow models. Supports model versioning, A/B testing, batching, and GPU acceleration. Best when your models are TensorFlow-native and you need tight integration with the TF ecosystem.

**Triton Inference Server (NVIDIA):** Multi-framework serving (TensorFlow, PyTorch, ONNX, XGBoost, custom). Supports dynamic batching, model ensembles, and GPU scheduling. Best when you have heterogeneous models or need GPU utilization optimization.

**BentoML:** Python-first serving framework. Package any Python model into a production API with built-in batching, monitoring, and containerization. Best for teams that want fast iteration from notebook to serving without learning a new framework.

**MLflow Serving:** Lightweight serving backed by MLflow's model format. Best for teams already using MLflow for experiment tracking who want simple serving without additional infrastructure.

**Decision framework:**
- Single framework, GPU-heavy: TensorFlow Serving or Triton.
- Multiple frameworks, GPU optimization needed: Triton.
- Python models, fast iteration priority: BentoML.
- Already using MLflow, simple serving needs: MLflow Serving.
- Custom requirements, full control: FastAPI or Flask with your own serving logic.

## Feature Serving

The serving layer's feature strategy determines prediction latency and freshness.

**Online feature store** for real-time inference. Key-value store (Redis, DynamoDB) with sub-millisecond lookups keyed by entity ID. Features are precomputed and materialized by a pipeline. The serving endpoint looks up features at request time.

**Offline feature store** for batch inference. Columnar storage (Parquet, Delta Lake) optimized for bulk reads. The batch pipeline reads all features for all entities in a single scan.

**Precomputed feature vectors** for ultra-low-latency serving. Instead of looking up individual features, precompute the entire feature vector for each entity and store it as a single blob. One lookup per prediction instead of N feature lookups.

**Request-time feature computation** for features that cannot be precomputed (features derived from the current request, like query-document similarity). Keep these computations lightweight -- heavy computation in the request path kills latency.

## Model Caching and Warmup

Loading a model from disk into memory takes seconds to minutes for large models. This creates cold-start latency that degrades user experience during deployments and auto-scaling events.

- **Preload models at startup.** Load all expected model versions before the readiness probe passes. No traffic reaches the instance until models are ready.
- **Model caching.** Keep recently used model versions in memory. Use LRU eviction when memory is constrained.
- **Warm-up requests.** After loading a model, run a batch of representative inference requests to warm JIT compilers, populate CPU caches, and initialize lazy-loaded components. First real requests should not pay the cold-start penalty.
- **Shared model artifacts.** Store model files on a shared filesystem (EFS, NFS) or use a model cache (S3 with local SSD caching) so new instances load models quickly.

## A/B Testing Infrastructure

A/B testing in ML serving requires traffic splitting, metric collection, and statistical analysis.

**Traffic splitting:** Route users (not requests) to model variants using a hash of user_id. This ensures each user gets a consistent experience. Use a feature flag system or a serving proxy to manage routing. Support multiple concurrent experiments with layered randomization.

**Metric collection:** Log every prediction with the experiment variant, user_id, timestamp, model version, and business outcome (when it arrives). Store in a prediction log that both the serving team and the analytics team can query.

**Statistical significance:** Pre-compute sample size requirements using power analysis. Run experiments for the planned duration, not until you see a result you like. Use sequential testing methods if you need to monitor results before the experiment completes.

## Shadow Deployments

Run a new model alongside production, scoring the same traffic, but only serving production model results to users. Compare the new model's predictions against production and ground truth.

- Zero user risk during evaluation.
- Catches performance issues (latency, memory, errors) under real traffic patterns.
- Requires infrastructure to run two models per request (doubles compute cost during shadow period).
- Shadow results should be logged to a separate table for offline analysis.

## Multi-Model Serving

Production systems often serve multiple models simultaneously: different models for different segments, model ensembles, or multiple model versions during A/B tests.

**Router-based:** A routing layer decides which model handles each request based on request attributes (user segment, region, experiment assignment). Each model runs in its own serving instance.

**Ensemble serving:** Multiple models score the same request and their outputs are combined (averaging, stacking, voting). Triton supports model ensembles natively with pipeline DAGs.

**Multi-tenant serving:** A single serving infrastructure hosts models from multiple teams. Requires resource isolation (memory limits, GPU quotas per model), fair scheduling, and per-model monitoring.

## GPU Serving Optimization

GPUs are expensive. Maximize utilization:

**Dynamic batching:** Instead of processing requests one at a time, accumulate requests for a short window (e.g., 10ms) and batch them into a single GPU inference call. Batch inference is dramatically more efficient -- 10 predictions batched cost barely more than 1. Triton and TensorFlow Serving support dynamic batching natively.

**Model parallelism:** For models too large to fit on a single GPU, split the model across GPUs. Tensor parallelism splits individual layers; pipeline parallelism splits the model into stages across GPUs.

**Right-sizing:** Not every model needs a GPU. Tabular models (XGBoost, LightGBM, logistic regression) serve efficiently on CPU. Reserve GPUs for deep learning models where GPU inference is meaningfully faster.

**Quantization for serving:** Reduce model precision from FP32 to FP16 or INT8. Reduces memory footprint and increases throughput with minimal accuracy loss for most models. Profile accuracy impact before deploying quantized models.

**Instance selection:** Use GPU instances with the right memory and compute for your model size. A smaller, cheaper GPU that fits your model is better than a large GPU at 20% utilization.

## When to Use This

- Designing the serving architecture for a new ML system.
- Choosing between batch and real-time serving for a specific use case.
- Selecting a model serving framework for production deployment.
- Optimizing GPU utilization for serving infrastructure.
- Setting up A/B testing infrastructure for ML experiments.
- Debugging latency issues in an existing serving layer.

## Red Flags to Watch For

- Choosing real-time serving when batch serving meets the latency requirements and would be simpler.
- No model warmup, causing the first N requests after deployment to have dramatically higher latency.
- A/B tests that randomize by request instead of by user, creating inconsistent experiences.
- Shadow deployments running indefinitely without a decision framework for promotion.
- GPU instances serving tabular models that would run just as fast on CPU at a fraction of the cost.
- No dynamic batching on GPU serving, processing one request at a time and wasting GPU compute.
- Feature lookups in the serving hot path without caching, adding unnecessary latency to every prediction.
- No fallback when the model fails to load -- the endpoint returns 500 instead of degrading gracefully.
