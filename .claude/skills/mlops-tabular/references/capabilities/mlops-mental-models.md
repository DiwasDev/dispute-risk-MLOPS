# MLOps Mental Models

## ML Is Not Software Engineering

In software engineering, code is the single source of truth. Change the code, change the behavior. In ML, there is no single source of truth -- there are four, and they must all be correct simultaneously:

1. **Code** -- the training logic, feature engineering, serving infrastructure
2. **Data** -- the training examples, their labels, their distributions
3. **Model Weights (Parameters)** -- the learned values that define model behavior
4. **Configuration** -- hyperparameters, feature flags, thresholds, environment settings

A bug in any one of these produces a system that runs without errors but makes wrong predictions. This is the fundamental architectural difference that makes ML systems harder to operate than traditional software.

### Six Debugging Sources

When a traditional software system fails, the cause is in the code. When an ML system fails, the cause could be in any of six places:

1. **Code errors** -- bugs in preprocessing, training, or serving logic
2. **Data anomalies** -- corrupted data, schema changes, missing values, stale data
3. **Labeling issues** -- incorrect labels, label definition changes, label delays
4. **Feature problems** -- feature drift, feature computation differences, feature leakage
5. **Configuration mistakes** -- wrong hyperparameters, wrong model version, wrong thresholds
6. **World changes** -- the real-world relationship between inputs and outputs has changed (concept drift)

This means debugging ML systems requires investigating all six dimensions, not just reading stack traces. Infrastructure metrics (CPU, memory, latency) are necessary but insufficient -- the system can be "healthy" by infrastructure standards while producing terrible predictions.

### Testing Is Fundamentally Different

In software: write a unit test, assert expected output for given input, done.
In ML: you cannot write a simple unit test that captures model correctness. You need:
- Statistical tests (are metrics within confidence intervals?)
- Slice-based evaluation (does the model work for all segments?)
- Behavioral testing (does the model respond sensibly to known perturbations?)
- Parity testing (do training and serving produce identical outputs for the same input?)

### Monitoring Is Essential, Not Optional

Traditional software either works or throws an error. ML systems degrade gradually as the world drifts. Without continuous monitoring, you will not know your model is failing until business metrics collapse -- days, weeks, or months after the degradation started.

## The Ten-Component Mental Model

Every production ML system consists of ten components. Each has a specific function and a specific failure mode when missing:

| Component | Function | What Breaks When Missing |
|-----------|----------|--------------------------|
| **Problem Framing** | Links prediction to business value | Building solutions to the wrong problem |
| **Data Validation** | Filters corrupt data before it reaches the model | Silent model degradation from bad training data |
| **Feature Pipeline** | Identical transformation in training and serving | Training-serving skew, wrong predictions in production |
| **Experiment Tracking** | Records reproducible lineage for every model | Cannot compare models, reproduce results, or debug regressions |
| **Model Evaluation** | Validates improvement over baseline | Deploying models that are worse than the current system |
| **Model Registry** | Enables versioning and rollback | No audit trail, no way to revert to a known-good model |
| **Deployment Strategy** | Safe rollout with gradual traffic expansion | Service incidents, slow recovery, all-or-nothing risk |
| **Monitoring** | Detects performance degradation in production | Undetected model decay until business impact is severe |
| **Drift Detection** | Early warning of distribution shifts | Stale predictions without awareness, missed retraining window |
| **Incident Response** | Structures failure reaction and learning | Reactive chaos, repeated failures, no organizational learning |

## Frameworks Change; Concepts Don't

The specific tools (ZenML, MLflow, Evidently, Airflow) will evolve and be replaced. The underlying concepts are durable:

- You will always need to version data alongside code
- You will always need to validate data before training
- You will always need identical preprocessing in training and serving
- You will always need to monitor models after deployment
- You will always need a rollback plan

Choose tools that implement these concepts well for your current constraints. Do not over-invest in tool-specific patterns that lock you in. Keep core logic (preprocessing, validation, evaluation) in pure Python that any framework can call.

## The Six-Week Build Timeline

A practical timeline for building a production MLOps system from scratch:

| Week | Focus | Deliverables |
|------|-------|-------------|
| **Week 1** | Problem statement + baseline | `problem_statement.md`, baseline model with honest metrics |
| **Week 2** | Reproducible training pipeline | Versioned pipeline, experiment tracking, artifact store |
| **Week 3** | Data validation + feature preprocessing + parity verification | Schema checks, sklearn.Pipeline, golden-set parity tests |
| **Week 4** | Evaluation framework + model registry | Slice-level evaluation, confidence intervals, model versioning |
| **Week 5** | Inference pipeline + shadow testing | Batch or real-time serving, shadow deployment comparison |
| **Week 6** | Monitoring + drift detection | Feature monitoring, prediction distribution tracking, drift alerts |

This timeline assumes a single engineer working on a tabular supervised learning problem with existing labeled data. Adjust based on team size, data complexity, and infrastructure maturity.

**Most teams should target Level 1 (reproducible pipelines) quickly, reach Level 2 (automated testing and promotion) within months, and pursue Level 3 (fully automated drift response) only when the scale justifies it.**

## When to Use This

- At the start of an MLOps project, to establish the mental framework for what needs to be built
- When explaining to stakeholders why ML systems require different infrastructure than traditional software
- When prioritizing which components to build next (use the ten-component table to identify gaps)
- When a team is debating tool choices (redirect to concepts; tools implement concepts)
- When estimating project timelines (use the six-week timeline as a starting reference)
