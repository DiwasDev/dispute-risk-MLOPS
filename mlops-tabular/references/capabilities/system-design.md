# ML Systems Architecture and Version Control

## Core Principle

Most ML fails at definition time, not at modeling time. Frame the problem well and half the work is done. The power of an ML engineer is saying no to ML with reasons -- not every problem needs it.

## When ML Is the Right Tool

Apply the six-word test before committing to an ML approach. The problem must satisfy all six conditions:

- **Learn**: the system must improve from examples, not just execute static rules.
- **Complex**: the relationships are not obvious enough to hand-code.
- **Patterns**: non-random structure exists in the data.
- **Existing data**: signals and labels are accessible today.
- **Predictions**: estimates are needed at decision time.
- **Unseen data**: training and serving share the same world -- the future looks roughly like the past.

If any word fails, ML is likely premature. Ship a heuristic or scorecard first, instrument metrics and logs, and use that baseline to collect data and define success.

## The Decision Triangle

Evaluate every ML proposal on three axes:

1. **Value gain** -- Does ML meaningfully outperform a heuristic or lookup? Always demonstrate a non-ML baseline first.
2. **Operational fit** -- Check latency budget per request, throughput targets and autoscaling plan, privacy and governance needs, interpretability requirements for stakeholders, and maintainability and cost of ownership.
3. **Risk profile** -- Map the feedback loop (label source, arrival time, proxies for delayed labels, window for implicit negatives, guardrails for feedback loops). Preempt silent failure patterns: training-serving divergence, feature leakage in offline data, data distribution shifts, and over-reliance on a single metric.

## Go / Not Now Rubric

**Go now** when: all six words pass, clear value over baseline, feedback loop is short or well-proxied, and operational constraints are met with margin.

**Not now** when: data or labels are missing, feedback is long and risk is high, constraints block feasibility, or a heuristic meets the goal well enough.

## Problem Framing

Turn messy ideas into clear prediction tasks using this template: "Given input X, predict target Y, for user or system Z, at decision time T, to optimize business outcome B."

For every framing, answer four questions:
- What action will use this prediction?
- Who owns the action?
- What happens if the model is wrong?
- What is the rollback path?

## The Metric Ladder

Design a metric ladder from business to model. Each level must connect to the one above:

1. **Business outcome** -- revenue, retention, cost saved. This is the north star.
2. **Product success metric** -- click-through rate, resolution time, conversion. Directly measurable in the product.
3. **Model evaluation metric** -- precision, recall, AUC, RMSE. What you optimize offline.
4. **Feature and data quality metrics** -- schema checks, missingness, drift on inputs, feature distribution stability, prediction distribution stability.

Pick one primary success metric, two or three guardrail metrics, and hard constraints that must never be violated.

## Choosing Offline Metrics by Task

- **Classification**: Accuracy is fragile with class imbalance. Prefer precision, recall, F1, and AUC. Set thresholds by cost of false positive vs false negative using cost matrices, not intuition. Align thresholds to segment and channel.
- **Regression**: Choose MAE, RMSE, or MAPE depending on the cost of large errors.
- **Ranking and recommendation**: Use NDCG, MAP, hit rate, coverage, and diversity.

Calibration matters: a good score reflects true likelihood. Check reliability plots and calibration error. Calibrated models enable rational downstream decisions.

## From Metric to Objective

The objective is what the algorithm optimizes. Choose a loss that matches your metric and real-world costs. Add weights for segments that matter more. For multi-objective design: list objectives that matter, identify conflicts, use a primary objective with secondary penalties, and explore the Pareto frontier for trade studies.

## Experiment and Launch Planning

Design an experiment plan before building: hypothesis and expected direction, exposure and unit of randomization, success metric and guardrails, duration and sample size plan. When randomized experiments are impossible, use backtests and holdouts, switched cohorts or staggered rollout, and watch for confounders and seasonality.

After launch, maintain: business metric dashboard, model metric dashboard, data and feature health alerts, weekly review cadence and retrain triggers.

## Silent Failure Patterns to Preempt

- Training and serving diverge (different code paths, different feature computation).
- Feature leakage in offline data (features that peek at the label or the future).
- Data distribution shifts over time without detection.
- Over-reliance on a single metric (optimizing vanity metrics, metric gaming, one-metric obsession).

## Feedback Loop Architecture

Map the full feedback loop before building:
- Where do labels come from and how long do they take to arrive?
- What proxies exist when labels are delayed?
- What window defines implicit negatives?
- How do labels flow back into learning?
- What guardrails prevent runaway feedback loops?

Different domains have very different feedback characteristics. Recommenders and ads get natural feedback through clicks with short windows enabling fast learning, but window choice trades speed and accuracy. Fraud detection labels arrive weeks or months later with high cost of false negatives -- start with rules and human review, then add ML with a strong monitoring plan. Grocery demand forecasting can launch a good model, but the world changes and inputs drift; without early warning on shifts, waste and lost sales follow.

## ML vs Traditional Software Engineering

ML systems differ from traditional software in fundamental ways that affect architecture. In software engineering, behavior is defined by code -- code is the single source of truth. In ML, **there is no single source of truth -- there are four**, and they must all be correct simultaneously:

1. **Code** -- the training logic, feature engineering, serving infrastructure
2. **Data** -- the training examples, their labels, their distributions
3. **Model Weights (Parameters)** -- the learned values that define model behavior
4. **Configuration** -- hyperparameters, feature flags, thresholds, environment settings

This means:

- **Testing is harder**: you cannot write a simple unit test that captures model correctness. You need statistical tests, slice-based evaluation, and behavioral testing.
- **Debugging is harder**: a bug might be in any of six places -- code errors, data anomalies, labeling issues, feature problems, configuration mistakes, or world changes (concept drift). Failures are often silent -- the system produces plausible but wrong outputs. Traditional infrastructure metrics (CPU, memory, latency) are necessary but insufficient.
- **Versioning is broader**: you must version not just code but also data, model weights, configuration, and the environment. Reproducibility requires all four.
- **Monitoring is essential, not optional**: traditional software either works or throws an error. ML systems degrade gradually as the world drifts. Without monitoring, you will not know until business metrics collapse.

## Artifact Management and Reproducibility

Every ML experiment and production model should be reproducible from its artifacts: the code version, the data snapshot (or data version pointer), the configuration (hyperparameters, feature lists, thresholds), and the environment specification. Store these as immutable, versioned artifacts. When a model degrades, you need to compare it to the last known good version across all four dimensions to identify what changed.

## When to Use This

- At project kickoff, before any modeling work begins.
- When a stakeholder asks "can we use ML for this?"
- When scoping a new ML feature or product.
- When an existing ML system is underperforming and you need to re-evaluate fundamentals.
- When designing the monitoring and rollback plan for a model going to production.

## Red Flags to Watch For

- No non-ML baseline has been established or compared against.
- The six-word test has not been applied, or one or more words clearly fail.
- Labels are unavailable, delayed beyond the decision window, or extremely noisy with no mitigation plan.
- The metric ladder is missing a level -- model metrics exist but no business outcome is defined.
- No rollback path exists if the model degrades.
- Operational constraints (latency, privacy, interpretability) have not been documented.
- The team is optimizing a single offline metric without guardrails.
- There is no plan for monitoring after deployment.
- The feedback loop is undefined or dangerously tight (model predictions influence future training labels with no dampening).

## The Complete MLOps Pipeline

An ML system in production is not a single pipeline -- it is a system of pipelines, each with a distinct responsibility. Understanding the full lifecycle and how to decompose it into manageable units is the difference between a prototype that works once and a system that works reliably over time.

### The MLOps Lifecycle Stages

The full lifecycle consists of ten distinct stages. Each stage has a purpose, a failure mode when skipped, and decisions that must be made explicitly.

**1. Data Ingestion** -- Pulling raw data from sources into the ML system. This includes database queries, API calls, file downloads, and stream consumers. Decisions: what sources to pull from, how often, how to handle source failures, whether to do full or incremental loads. Skipping proper ingestion leads to ad-hoc data pulls that differ between training and serving.

**2. Data Validation** -- Checking that incoming data meets expectations before any processing. Schema validation (column names, types, ranges), statistical validation (distribution checks, null rates, cardinality), and freshness checks (is this data from today or last month?). Decisions: what thresholds trigger a hard stop vs a warning, how to handle partial failures. Without validation, garbage data flows silently into training and corrupts models.

**3. Feature Engineering** -- Transforming raw data into model-ready features. Includes encoding, scaling, imputation, aggregation, and feature selection. Decisions: which transformations to apply, how to handle the train-serve skew problem (the same transformation logic must run identically at training time and inference time), whether to use a feature store. This is where most training-serving divergence bugs originate.

**4. Model Training** -- Fitting a model to prepared data. Includes hyperparameter tuning, cross-validation, and experiment tracking. Decisions: algorithm selection, hyperparameter search strategy, compute budget, how long to train, when to stop. Training without experiment tracking means you cannot compare runs or reproduce results.

**5. Model Evaluation** -- Measuring model quality against held-out data using the metric ladder defined earlier. Includes slice-based evaluation (does the model work for all segments?), fairness checks, and comparison against the current production model. Decisions: what thresholds a model must pass to be promoted, which slices are critical, whether to use champion-challenger testing. Skipping evaluation means deploying models that are worse than what is already running.

**6. Model Registry** -- Storing trained models with metadata: version, training data reference, evaluation metrics, lineage, and promotion status (staging, production, archived). Decisions: naming conventions, promotion criteria, retention policy. Without a registry, there is no single source of truth for which model is in production or how to roll back.

**7. Deployment** -- Moving a registered model to a serving environment. This can be batch (generate predictions on a schedule), real-time (API endpoint), or embedded (model shipped inside an application). Decisions: serving pattern, latency requirements, scaling strategy, canary vs blue-green vs shadow deployment. Deploying without a rollback plan is the fastest path to an outage.

**8. Monitoring** -- Tracking the health of the deployed model in production. Includes prediction distribution monitoring, latency tracking, error rates, and business metric dashboards. Decisions: what to monitor, alerting thresholds, who gets paged. Without monitoring, model degradation is invisible until a stakeholder notices bad outcomes.

**9. Drift Detection** -- Comparing current data and prediction distributions against a reference baseline to detect when the world has changed. Data drift (input distributions shift), concept drift (the relationship between inputs and outputs changes), and prediction drift (model outputs shift). Decisions: which drift tests to use, what reference window to compare against, what magnitude of drift is actionable. Drift detection without a response plan is just noise.

**10. Retraining Trigger** -- Deciding when and how to retrain. Triggers can be scheduled (weekly, monthly), performance-based (evaluation metric drops below threshold), or drift-based (drift exceeds threshold). Decisions: trigger criteria, whether to retrain from scratch or incrementally, how to validate the retrained model before promoting it. Automatic retraining without automatic evaluation is dangerous -- you must gate promotion on quality checks.

### Decomposing into Pipeline Units

A monolithic pipeline that does everything from ingestion to deployment in a single run is fragile, slow, and hard to debug. Decompose the lifecycle into distinct pipeline units that can run independently.

**Training Pipeline** -- The core learning loop. Takes data, preprocesses it, trains a model, evaluates it, and registers it in the model registry. This pipeline runs when you need a new model: on a schedule, when triggered by drift, or manually. It should be fully reproducible -- given the same data and configuration, it produces the same model. Steps: data ingestion, data validation, feature engineering, model training, model evaluation, model registration.

**Inference Pipeline** -- The prediction path. Loads a registered model, accepts input data, generates predictions, and stores or returns them. For batch inference, this runs on a schedule against a dataset. For real-time inference, this is an API endpoint. The inference pipeline must use the exact same feature engineering logic as the training pipeline -- this is the single most common source of bugs in production ML. Steps: load model, load/receive data, apply feature transformations, predict, store/return predictions.

**Drift Detection Pipeline** -- The early warning system. Compares reference data distributions (from training) against current production data distributions. Produces drift reports and can trigger alerts or retraining. Runs on a schedule -- daily or weekly depending on how fast your domain changes. Steps: load reference data profile, load current data window, compute drift metrics, generate report, evaluate against thresholds, trigger alerts if needed.

**Monitoring Pipeline** -- The health dashboard. Tracks model performance metrics over time, prediction distributions, data quality metrics, and system health (latency, errors, throughput). Unlike drift detection which compares distributions, monitoring tracks individual metrics over time and fires alerts when they cross thresholds. Steps: collect prediction logs, compute performance metrics (if labels are available), compute distribution statistics, update dashboards, evaluate alert rules, notify on-call if triggered.

**Retraining Pipeline** -- The automated response. Triggered by drift detection or monitoring alerts, this pipeline orchestrates a full retrain-evaluate-promote cycle. It is essentially the training pipeline wrapped with additional gates: the new model must outperform the current production model on evaluation metrics before it is promoted. Steps: trigger training pipeline, compare new model against current production model, promote if quality gates pass, roll back if they fail, notify stakeholders of outcome.

### Which Pipelines Does Your Project Need?

Not every project needs all five pipelines. Over-engineering the infrastructure before the model works is a common trap. Use this decision framework:

**Every project needs a training pipeline.** If you are doing ML, you are training models. Make it reproducible from day one -- this costs almost nothing and saves enormous debugging time later.

**Every project going to production needs an inference pipeline.** The moment predictions leave a notebook and affect a user or business process, you need a defined inference path with versioned models.

**Add drift detection when your data changes over time.** If your inputs come from user behavior, market conditions, sensor readings, or any external source that evolves, you need drift detection. If your data is static (historical analysis, one-time classification of a fixed dataset), you do not.

**Add monitoring when the cost of silent failure is high.** If a degraded model causes financial loss, safety risk, or customer harm, monitoring is not optional. If the model is advisory and a human reviews every prediction, monitoring can be lighter.

**Add automated retraining when manual retraining is too slow or too frequent.** If you need to retrain monthly and the process takes an afternoon, manual is fine. If you need to retrain daily or the domain drifts unpredictably, automate it. Never automate retraining without automated evaluation gates.

A practical starting point for most projects: training pipeline and inference pipeline from the start, drift detection and monitoring added before production launch, automated retraining added after you have confidence in your evaluation gates.

### MLOps Maturity Levels

MLOps maturity describes how automated and reliable your ML operations are. Use these levels to assess where you are and plan where to go next. Do not jump levels -- each level builds on the practices of the previous one.

**Level 0 -- Manual.** Everything runs in notebooks or scripts. Training is manual, deployment is manual (copy model file, restart service), there is no versioning of data or models, and no monitoring. This is where every project starts. It is fine for exploration and prototyping. It is not fine for production.

**Level 1 -- Pipeline Automation.** Training is a reproducible pipeline that can be triggered with a single command. Models are versioned in a registry. Inference has a defined pipeline or serving endpoint. Data validation runs before training. You can reproduce any past experiment. The key shift: going from "it works on my machine" to "anyone can run this and get the same result."

**Level 2 -- CI/CD for ML.** Pipelines are tested automatically. Code changes trigger pipeline runs in CI. Model evaluation happens automatically and gates promotion. Infrastructure is defined as code. Multiple environments (dev, staging, production) exist with separate stacks. The key shift: going from "I manually check if the new model is good" to "the system automatically validates and promotes models."

**Level 3 -- Full Automation with Monitoring.** Drift detection runs continuously. Retraining triggers automatically when drift or performance degradation is detected. New models are evaluated and promoted without human intervention (with guardrails). Monitoring dashboards track all levels of the metric ladder. Alerts fire when business metrics, model metrics, or data quality metrics degrade. The key shift: going from "we retrain when someone notices a problem" to "the system detects and responds to problems before they impact the business."

Most teams should aim for Level 1 quickly, reach Level 2 within the first few months of production deployment, and pursue Level 3 only when the scale or velocity of the problem demands it. Level 3 is expensive to build and maintain -- the operational complexity of fully automated retraining with production gates is significant. Do not build it until you have strong evaluation and monitoring foundations.
