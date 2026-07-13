# Example: Loan Default Prediction

A reference example showing what a completed tabular MLOps project looks like, from problem statement through production deployment.

## Problem Statement

Predict which loan applicants will default on their payments. Binary classification on structured tabular data with ~14% positive rate (imbalanced classes). The model must be retrained periodically as borrower demographics shift, and predictions must be served via a batch inference pipeline with instant rollback capability.

## Data Description

- **Training set**: `loans_2015.csv` -- 10,000 rows of synthetic loan applications with features like income, credit score, loan amount, employment length, and debt-to-income ratio. ~14% default rate (moderate imbalance -- enough to matter for metric selection but not so extreme that SMOTE is the first resort).
- **Drift set**: `loans_2018.csv` -- 10,000 rows with shifted distributions simulating temporal drift. ~39% default rate (nearly 3x the training rate). This simulates a real-world scenario like an economic downturn where the relationship between borrower features and default outcomes has changed (concept drift, not just data drift).
- **Features**: Mix of numeric financial indicators. Target column: `default` (0/1).

### Why This Dataset Teaches MLOps Well

The 14% → 39% default rate shift is a compelling teaching example because:
- It demonstrates that a model trained on 14% default rate will dramatically underpredict defaults when the rate triples
- It shows concept drift (the relationship between features and default has changed, not just the feature distributions)
- It motivates the need for drift detection, monitoring, and retraining triggers
- The moderate training imbalance (14%) requires careful metric selection (precision-recall based, not accuracy) but does not require aggressive resampling

## Pipeline Architecture

The project builds progressively through 6 stages, each solving a real production problem:

```
v1  notebook.py          Baseline with deliberate data leakage (inflated AUC ~0.82)
v2  steps/ + pipelines/  ZenML pipeline, honest metrics (AUC ~0.80)
v3  + MLflow tracker     Experiment comparison across runs
v4  + sklearn.Pipeline   Bundled scaler+model eliminates train-serve skew
v5  + Evidently          Drift detection pipeline catches silent degradation
v6  + Model Control Plane  Inference pipeline with promotion and rollback
```

Three pipelines in the final system:

1. **Training pipeline**: `load_data -> preprocess -> train -> evaluate`. Produces a versioned model registered in the Model Control Plane. Logs accuracy, AUC, precision, recall, and F1 to the model version metadata.

2. **Drift check pipeline**: Runs Evidently on new data against training data. Produces a drift report identifying which features have shifted.

3. **Inference pipeline**: Loads whichever model version is tagged `production` in the Model Control Plane. Runs batch predictions. Model and scaler are loaded via `get_step_context().model.load_artifact()`.

## Key Lessons

**Data leakage is invisible without proper pipeline structure.** The notebook baseline scales before splitting, inflating AUC by ~2 points. The ZenML pipeline enforces correct ordering (split first, scale second) because each step has explicit inputs and outputs.

**The Artifact Golden Rule matters.** Data moves between steps as artifacts (DataFrames, arrays), not file paths. This makes the pipeline portable from local to cloud orchestrators without code changes.

**Model versioning enables instant rollback.** `python run.py --promote --version 1` switches the production model in under 30 seconds. The inference pipeline automatically picks up the change because it references `ModelStages.PRODUCTION`, not a version number.

**Drift detection is a separate pipeline, not a step in training.** Drift checks run on a schedule against incoming data. When drift is detected, it triggers retraining -- it does not block inference.

**Experiment tracking and model versioning serve different purposes.** MLflow is for comparing experiments (hyperparameter search, model selection). The Model Control Plane is for the winning model that gets versioned and deployed.

## Stack

Local development stack with MLflow experiment tracker, set up via a single shell script (`setup_stack.sh`). No Docker or cloud infrastructure required for the full demo.
