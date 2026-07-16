# Production Readiness and Case Studies

Production readiness is the discipline of confirming that a model is safe, observable, and maintainable before it serves real users. A model that performs well in a notebook but lacks monitoring, rollback capability, or documentation is not production-ready. This reference covers checklists, requirements, common pitfalls, and maturity models for ML systems.

## The Production Readiness Checklist

Use this checklist before any model goes live. Every item must be satisfied, not aspirational.

### Data Quality

- Schema validation is enforced on all inputs (types, ranges, required fields, allowed categories).
- Data drift detection is running with defined thresholds and alert routing.
- Bad data is quarantined (not silently dropped), with failure reason logged and data owner notified.
- Validation error messages are human-readable: field name, rule violated, current value, and fix steps.
- Golden input tests are in place and run on every deploy and server start.

### Model Quality

- Offline evaluation completed with confidence intervals on primary and secondary metrics.
- Slice-level evaluation completed for all critical business segments.
- Metrics computed on a proper temporal split (no future leakage).
- Model card filled out: use cases, limitations, training data scope, sensitive features, failure patterns, owner.
- Comparison against current production baseline documented.

### Serving Infrastructure

- Latency requirements defined (p50, p95, p99 targets) and tested under expected load.
- Throughput requirements defined (requests per second) and load-tested.
- Warmup procedure defined: cache priming, model loading, replay of recent traffic.
- Fallback behavior defined: what happens when the model is unavailable (previous score, conservative rule, graceful degradation).
- Idempotency handled: duplicate requests produce consistent results without side effects.

### Deployment Safety

- Deployment pattern chosen and documented (shadow, canary, blue-green, A/B).
- Rollback path tested: can restore previous model version in under five minutes.
- Stop criteria pre-defined: specific metric thresholds that trigger automatic or manual rollback.
- Training-serving parity verified: golden inputs produce expected outputs through the full serving path.
- All artifacts (model, encoders, scalers, config) versioned and stored in the registry with checksums.

### Monitoring and Alerting

- Monitoring ladder in place: business outcomes, product metrics, model metrics, data/feature health.
- Prediction distribution monitoring active (histograms compared against baseline).
- Feature health tracking active (mean, std, missingness, sparsity for key features).
- Alert severity levels defined with routing to appropriate owners.
- Runbook written for the top three most likely failure modes.
- Dashboard created with slice selectors, deploy annotations, and the monitoring ladder layers.

### Documentation and Ownership

- Model card published and accessible to the team.
- Runbook published with triage steps, escalation paths, and rollback instructions.
- On-call ownership assigned: who gets paged, who approves rollback, who owns each alert category.
- Data contracts agreed with upstream data producers (schemas, units, timezones, breaking change policy).

## Requirements: Latency, Throughput, Accuracy

### Latency

- Define latency targets based on user experience, not model capability. A 200ms target means the full request (feature lookup, inference, post-processing) must complete in 200ms.
- Measure p95 and p99, not just average. Tail latency is what users remember.
- Budget latency across the pipeline: feature retrieval (X ms), inference (Y ms), post-processing (Z ms).
- Test under realistic load, not just single-request benchmarks.

### Throughput

- Estimate peak traffic from historical data with a safety margin (typically 2-3x average).
- Load test with realistic request patterns, not synthetic uniform traffic.
- Plan for burst scenarios: marketing campaigns, seasonal peaks, viral events.
- Horizontal scaling plan: can you add capacity within minutes if needed?

### Accuracy

- Define the minimum acceptable accuracy for the product to deliver value.
- Set accuracy guardrails: the threshold below which the model must be rolled back.
- Accuracy targets should be set per slice, not just globally. A model that is 95% accurate overall but 60% accurate for a critical minority is not acceptable.
- Track accuracy trends over time. Gradual degradation is as dangerous as sudden drops.

## Infrastructure Requirements

### Compute

- Right-size serving instances for the model. Over-provisioning wastes money; under-provisioning causes latency spikes.
- Separate training infrastructure from serving infrastructure. Training bursts should not affect serving latency.
- GPU vs CPU: most tabular models serve well on CPU. Reserve GPU serving for deep learning models where inference is the bottleneck.

### Storage

- Model artifacts, feature stores, and prediction logs all need storage with appropriate durability and access patterns.
- Hot storage for active model versions and feature lookups.
- Cold storage for archived models, historical predictions, and audit trails.
- Plan retention policies: how long to keep prediction logs, feature snapshots, and archived models.

### Networking

- Feature stores and model servers should be co-located to minimize network latency.
- Plan for cross-region serving if users are geographically distributed.
- Rate limiting and circuit breakers protect serving infrastructure from cascade failures.

## Common Pitfalls

### Training-Serving Skew

The most common and most insidious production ML bug. The model sees different feature values in production than it saw in training because the feature computation path differs. Prevention: share the same transformation code for training and serving, save all transformers as artifacts, and run golden input tests on every deploy.

### Silent Data Quality Degradation

Upstream data changes (renamed fields, unit changes, new categories, timezone shifts) propagate through the pipeline without errors but produce garbage predictions. Prevention: schema validation, data contracts with producers, and drift monitoring.

### Over-Reliance on Global Metrics

A model can have excellent aggregate metrics while failing badly for specific user segments. Prevention: mandatory slice-level evaluation before promotion, per-slice monitoring in production.

### Alert Fatigue

Too many alerts, or alerts set too sensitively, train the team to ignore them. Eventually a real alert gets missed. Prevention: regular alert tuning, tracking alert-to-action ratio, throttling repeat alerts.

### Stale Models

Models that were trained months ago on data that no longer represents the current world. Prevention: scheduled retraining cadence, drift detection that triggers retraining, staleness alerts.

### Missing Fallback Behavior

When the model is unavailable or returns an error, what happens? If the answer is "the request fails," users are unprotected. Prevention: define and test fallback behavior (cached previous prediction, conservative rule, default value).

### Documentation Rot

Model cards and runbooks that were written once and never updated. Prevention: tie documentation updates to the promotion workflow. Promotion requires an up-to-date model card.

## MLOps Maturity Models

### Level 0: Manual

- Training in notebooks, manual deployment by copying files.
- No experiment tracking, no registry, no monitoring.
- Debugging requires talking to the person who trained the model.
- Rollback means "find the old file somewhere."

### Level 1: Automated Training

- Training pipelines are scripted and reproducible.
- Experiment tracking records runs, parameters, and metrics.
- Deployment is still manual or semi-automated.
- Basic monitoring exists (model is up/down) but no drift detection.

### Level 2: Automated Training and Deployment

- Full CI/CD pipeline for model training, evaluation, and deployment.
- Model registry with promotion stages and gate checks.
- Canary or shadow deployment pattern in use.
- Monitoring covers the full ladder (business, product, model, data).
- Runbooks and rollback procedures are documented and tested.
- Retraining triggered on schedule or by drift detection.

### Level 3: Full Automation with Governance

- Automated retraining with automated promotion through gates.
- Human approval required only for high-risk changes.
- Comprehensive audit trail for compliance.
- Feedback loops are monitored and managed (exploration policies, counterfactual logging).
- Cross-model coordination for multi-model products.
- Continuous improvement: postmortems feed back into better gates, monitoring, and features.

### Progressing Through Levels

- Most teams should aim for Level 2 as the baseline for production ML.
- Level 0 to Level 1 is the highest-impact transition. Start here.
- Do not try to jump from Level 0 to Level 3. Each level builds on the previous one.
- The right level depends on the stakes. A recommendation sidebar can operate at Level 1. A fraud detection system should be at Level 2 or 3.

## Case Study Patterns

### Pattern: Cafeteria Demand Forecast

A demand forecasting model was promoted based on strong offline metrics. Canary deployment to the smallest dorm cluster revealed rising food waste in one cluster despite similar accuracy. Root cause: distribution shift in one dorm's ordering behavior. The staging plus canary pattern protected the entire campus while the issue was found and fixed. The previous model remained live during investigation.

### Pattern: Campus Bus ETA

Daylight saving time caused a timestamp parser to misinterpret labels, leading to ETAs that were off by one hour. A simple schema rule enforcing timezone awareness and label delay range would have blocked the broken training data. After the fix, a combined batch (precomputed route stats) plus online (live GPS adjustment) architecture provided both low latency and fresh predictions.

### Pattern: Study Video Recommendations During Exam Week

Watch time dropped for senior students during exams. Investigation revealed delayed late-night content uploads caused a feature drop. The fix was prioritizing the overnight ingestion job. Recovery was confirmed within 24 hours using a cohort-level monitoring panel. This demonstrates why slice-level monitoring (by student cohort) catches issues that global averages hide.

### Pattern: Morning Music Skip Rate

Overall engagement minutes looked healthy, but slice-level monitoring revealed a spike in skip rate on old Android devices in the morning. Root cause: cold model caches after overnight restart. Fix: warmup replay before morning traffic peak. Verified the next day through the same slice dashboard.

## When to Use This

- **Before first production launch**: Walk through the full production readiness checklist. Every unchecked item is a risk to document and accept or mitigate.
- **When assessing team maturity**: Use the maturity model to identify the current level and plan the next level of investment.
- **During incident postmortems**: Cross-reference the incident with the checklist to identify which missing item would have prevented it.
- **When planning infrastructure**: Use the requirements section to size compute, storage, and networking appropriately.
- **When onboarding new ML engineers**: The checklist and maturity model provide a shared vocabulary for what "production-ready" means.

## Red Flags to Watch For

- **"It works in the notebook" as the bar for shipping**: Notebook performance is necessary but nowhere near sufficient.
- **No latency budget**: If nobody has defined latency targets, the first production load spike will be a surprise.
- **No fallback behavior**: If the model goes down and there is no fallback, users get errors.
- **Checklist items marked "will do later"**: Deferred items accumulate as production risk. Ship with the checklist complete or document accepted risks explicitly.
- **No on-call ownership**: If nobody is responsible for the model in production, nobody will notice when it breaks.
- **Maturity level mismatch with stakes**: A high-stakes model (safety, finance, healthcare) running at Level 0 or 1 is an incident waiting to happen.
- **Retraining has never been tested**: If you have never retrained and redeployed, the first time you need to will be during a crisis.
- **No data contracts with upstream teams**: You will discover upstream changes through broken predictions instead of through communication.
