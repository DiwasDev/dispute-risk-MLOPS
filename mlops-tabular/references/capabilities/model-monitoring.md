# Model Monitoring & Observability

## Why ML Systems Need Specialized Monitoring

Traditional software breaks loudly -- a crash, an exception, a timeout. ML systems fail silently. The model keeps returning predictions, the HTTP status codes stay 200, latency looks normal, but the predictions are quietly wrong. A cafeteria demand model works perfectly until a festival brings visitors unseen in training data and food runs out. A plagiarism detector degrades as AI writing assistants change the input distribution. Servers stay healthy while usefulness declines.

This silent-failure property means standard infrastructure alerts (CPU, memory, error rate, latency) are necessary but insufficient. ML monitoring must watch the content of inputs and outputs, not just the health of the container serving them.

## The Three ML-Specific Risks

Every monitoring setup should be designed to catch these three failure modes:

**Training-serving skew** happens when the model sees different feature values in production than it saw during training. Common causes include different feature computation logic between training and serving, missing features being filled with different defaults, recomputed preprocessing statistics (e.g., mean/variance computed from live traffic instead of reusing the training set values), or loading the wrong model file version.

**Data drift** occurs when the input distribution shifts over time. Device mix changes, user demographics shift, a new marketing campaign brings different customers. The model was trained on one population and now serves another.

**Concept drift** means the relationship between inputs and labels has changed. The same features that once predicted churn no longer do because the product changed, or the same image features that identified objects fail under new lighting conditions.

## Monitoring vs. Observability

Monitoring answers "is something wrong?" -- it watches dashboards and fires alerts when metrics cross thresholds. Observability answers "why is it wrong?" -- it provides the data lineage and instrumentation to trace a bad prediction back to its root cause.

A mature system needs both. Monitoring catches the fire; observability helps you find the arsonist.

## What to Monitor: The Evaluation Ladder

Organize monitoring in layers, from the most fundamental to the most business-relevant:

**Layer 1 -- Data and prediction health monitors.** Track missingness rates, feature distributions, and prediction distribution shape. These require no labels and alert fastest. Monitor null rates per feature, the fraction of unknown or out-of-vocabulary categories, median and percentile shifts in numeric features, and the shape of prediction score distributions.

**Layer 2 -- Model metrics.** Precision, recall, F1, MAE, NDCG, or whatever offline metric you chose. These require labels, which often arrive late. Use them for periodic reconciliation rather than real-time alerting.

**Layer 3 -- Product metrics.** Minutes watched, click-through rate, refund rate, conversion rate. These connect model quality to user experience.

**Layer 4 -- Business outcomes.** Revenue, safety incidents, customer retention. The north-star reason the model exists.

Most real-time alerting should focus on Layers 1 and 2 because they move first. Layer 3 and 4 shifts confirm that a model problem is actually hurting users.

## Proxies That Speak Early

When labels are delayed or absent, proxy signals let you detect problems before harm compounds:

- **Input health:** jumps in unknown categories, sudden changes in feature medians, compressed or expanded score ranges.
- **Feature drift:** daily distribution plots of key features compared against a training-time baseline. Monitor population mix dimensions like device type, region, or language.
- **Prediction drift:** compare prediction distributions over time and across slices. Watch for sudden uniformity (the model returning the same score for everything) or regional score drift.
- **Missing/default values fraction:** a spike in nulls often signals an upstream pipeline failure, not a model problem.

## Catching Training-Serving Skew

Skew checks do not require labels and can run continuously:

- **Golden-set parity:** maintain a small set of fixed examples. Score them offline and online. The scores must match exactly. Any divergence means something is different between the two paths.
- **Frozen preprocessing:** save all preprocessing statistics (scaling parameters, bin edges, encoder mappings) as artifacts during training. Load those same artifacts in serving. Never recompute statistics from live data.
- **Feature distribution comparison:** log features at serving time and compare their distributions to the training-time distributions. A significant shift in a feature that has not changed semantically suggests a computation bug.
- **Model version confirmation:** verify that the model file loaded in production matches the version recorded in the training run's metadata.

## Catching Data Drift Early

- Plot daily distributions of key features against a training-time baseline.
- Monitor population-mix dimensions: device type, region, user segment.
- Track the fraction of missing or default-filled values over time.
- Alert on sharp changes before users notice quality degradation.

## Catching Concept Drift Without Labels

- Compare prediction distributions over time and across slices.
- Watch for sudden uniform predictions or drifting regional scores.
- Use shadow models (a retrained model running in parallel with no user impact) to detect when a newer model disagrees significantly with the production model.
- Run rolling backtests: periodically evaluate the production model on recent labeled data once labels arrive.

## Alerting Strategy

Not every metric shift warrants a page. Design alerts in tiers:

- **Immediate / page-worthy:** golden-set parity failure (skew), prediction volume dropping to zero, null rate spiking above a hard threshold, guardrail metric (error rate, latency) breaching its ceiling.
- **Same-day investigation:** feature distribution shift beyond two standard deviations from baseline, prediction distribution shape change, upstream data freshness SLO violation.
- **Weekly review:** slow drift trends, model-metric reconciliation once labels arrive, population-mix changes.

Set SLOs for data, not just services. Examples: user embeddings must refresh within 6 hours (freshness); feature table must be 99% complete (completeness). Track lineage so you can connect each prediction to the features, batch job, and code version that produced it.

## Root Cause Analysis

When an alert fires, the investigation pattern is:

1. Check if the issue is data or model. Did input distributions change, or is the model producing unexpected outputs on normal inputs?
2. If data: trace upstream. Which pipeline stage, batch job, or data source changed? Use lineage metadata to find the offending batch.
3. If model: check for skew first (golden set), then drift (feature distributions vs. baseline), then concept change (model metrics on recent labeled data).
4. Use canary, shadow, and replay deployments to validate a fix before full rollout.

## Deployment Safety Patterns

**Canary deployment:** route a small fraction of traffic to the new model. If monitoring metrics stay healthy, gradually increase. If anything wobbles, roll back instantly.

**Shadow deployment:** run the new model in parallel, scoring real traffic but not serving results to users. Compare its outputs to the production model. Surface problems with zero user impact.

**Replay testing:** feed recent production traffic through a new model build offline. Compare outputs to what the production model produced. Catches regressions before any deployment.

## When to Use This

- You are deploying a model to production for the first time and need to set up monitoring from day one.
- A model has been running in production and you suspect quality degradation but have no dashboards to confirm.
- You are debugging a production incident where model predictions seem wrong but infrastructure looks healthy.
- You are designing a retraining pipeline and need to decide what triggers retraining.

## Red Flags to Watch For

- The only monitoring is infrastructure-level (CPU, memory, latency) with no input/output content monitoring.
- No golden-set parity test exists between training and serving.
- Preprocessing statistics are recomputed from live data instead of loaded from training artifacts.
- There is no alerting on feature null rates or distribution shifts.
- Labels are delayed but the team has no proxy signals to monitor in the interim.
- The team cannot trace a bad prediction back to the data batch and code version that produced it.
- Model retraining is scheduled on a fixed cadence with no data-driven trigger based on drift detection.
- A model has been in production for months but no one has checked whether its prediction distribution has changed.
- Caches or retries in the serving path could mask stale or duplicated feature values without any staleness checks.
