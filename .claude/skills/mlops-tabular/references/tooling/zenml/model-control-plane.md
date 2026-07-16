# ZenML Model Control Plane

This reference covers ZenML's Model Control Plane (MCP) -- the versioned registry that tracks model versions, stages, metadata, and artifacts. It is the single source of truth for which model is in production.

## Core Concept

The Model Control Plane is a bookshelf. Every model you train gets a slot, labeled with:
- The model name (`loan_default_predictor`)
- A version number (auto-incremented: v1, v2, v3...)
- A stage label (`staging`, `production`, or none)
- Metadata (accuracy, AUC, training date, git commit)
- Artifact links (the trained model, scaler, preprocessing objects)

To update the production model: train a new version, verify it, move the stage label to `production`. To roll back: move the stage label back to an older version. No redeployment, no code changes.

## Registering a Model with a Pipeline

Attach a `Model()` to your pipeline. Each run automatically creates a new model version.

```python
from zenml import Model, pipeline

@pipeline(
    model=Model(
        name="loan_default_predictor",
        description="predicts which loan applicants will default",
        tags=["classification", "sklearn", "loan-default"],
    ),
)
def training_pipeline():
    ...
```

Every artifact produced by this pipeline is linked to the model version. Every metric logged with `infer_model=True` is attached to it.

### Tagging for Governance

Use structured tags for filtering and compliance:

```python
Model(
    name="breast_cancer_classifier",
    tags=[
        "classification",
        "sklearn",
        "use_case:breast_cancer",
        "owner_team:ml-platform",
    ],
)
```

Tags with `key:value` format are especially useful for governance hooks that enforce required metadata.

## Model Stages

ZenML has built-in stage labels: `staging`, `production`, `latest`, and `archived`. Only one version can hold a given stage at a time (except `archived`).

### Promoting a Model Version

```python
from zenml.client import Client

client = Client()
mv = client.get_model_version("loan_default_predictor", version=1)
mv.set_stage("production", force=True)
```

`force=True` removes the `production` label from any other version. Without it, ZenML raises an error if another version already holds that stage.

### Promoting from a CLI Entry Point

A common pattern in `run.py`:

```python
if args.promote:
    client = Client()
    mv = client.get_model_version("loan_default_predictor", args.version)
    mv.set_stage("production", force=True)
    print(f"promoted v{args.version} to production")
```

Usage: `python run.py --promote --version 3`

### Rollback

Rollback is just promotion of an older version:

```bash
# Something went wrong with v3, roll back to v2
python run.py --promote --version 2
```

The inference pipeline immediately picks up the change because it references the stage, not a version number.

## Loading Models by Stage

Inference pipelines should reference the model by stage, not by version number. This decouples deployment from code changes.

```python
from zenml import Model, pipeline
from zenml.enums import ModelStages

@pipeline(
    model=Model(
        name="loan_default_predictor",
        version=ModelStages.PRODUCTION,
    ),
    enable_cache=False,
)
def inference_pipeline(data_path: str = "data/new_data.csv"):
    data = load_data(path=data_path)
    predict(data=data)
```

Inside the predict step, load artifacts from the model version:

```python
from zenml import get_step_context, step

@step(enable_cache=False)
def predict(data: pd.DataFrame) -> pd.DataFrame:
    context = get_step_context()
    model = context.model.load_artifact("sklearn_classifier")
    # model is whatever version currently holds the "production" stage
    predictions = model.predict(data)
    return predictions
```

### Loading Specific Artifacts

The `load_artifact()` method retrieves artifacts by the name given in `ArtifactConfig` or `Annotated`:

```python
context = get_step_context()
model = context.model.load_artifact("sklearn_classifier")
scaler = context.model.load_artifact("scaler")
```

For artifacts not associated with the current pipeline's model, use the client directly:

```python
from zenml.client import Client

client = Client()
model_version = client.get_model_version(
    model_name_or_id="my_model",
    model_version_name_or_number_or_id=ModelStages.STAGING,
)
artifact = model_version.get_artifact("sklearn_classifier")
loaded_model = artifact.load()
```

## Logging Metadata to Model Versions

Attach metrics and metadata to model versions for tracking and governance:

```python
from zenml import log_metadata, step

@step
def evaluate_model(model, X_test, y_test) -> dict:
    metrics = {"accuracy": 0.95, "f1": 0.90, "auc": 0.97}
    log_metadata(metadata=metrics, infer_model=True)
    return metrics
```

You can also log metadata from outside a step using the step context explicitly:

```python
@step
def log_environment_metadata(environment: str) -> str:
    log_metadata(
        metadata={"environment": environment},
        infer_model=True,
    )
    return f"environment: {environment}"
```

This enables filtering model versions by training environment (local, staging, production).

## Champion/Challenger Pattern

Before promoting a new model, compare it against the current champion (staging or production model) using side-by-side inference.

### Pipeline Structure

```python
@pipeline(
    model=Model(name=MODEL_NAME, version=ModelStages.LATEST),
    enable_cache=False,
)
def champion_challenger_pipeline():
    inference_data = load_inference_data()

    champion_preds = predict_with_model(
        data=inference_data, model_stage="staging", id="champion_predict"
    )
    challenger_preds = predict_with_model(
        data=inference_data, model_stage="challenger", id="challenger_predict"
    )

    comparison = compare_predictions(champion_preds, challenger_preds, inference_data)
    report = generate_comparison_report(comparison)
    return report
```

### Loading Champion vs Challenger

The predict step loads different model versions based on the `model_stage` parameter:

```python
@step
def predict_with_model(data: pd.DataFrame, model_stage: str) -> pd.DataFrame:
    from zenml.client import Client

    client = Client()

    if model_stage == "staging":
        # Champion: the model currently in staging
        model_version = client.get_model_version(
            model_name_or_id=MODEL_NAME,
            model_version_name_or_number_or_id=ModelStages.STAGING,
        )
    else:
        # Challenger: latest model trained in staging environment
        model_version = find_latest_staging_trained_model(client)

    model = model_version.get_artifact("sklearn_classifier").load()
    predictions = model.predict(data)
    return pd.DataFrame({"prediction": predictions, "model_stage": model_stage})
```

### Comparison Metrics

Compare predictions from both models to quantify risk:

```python
comparison = {
    "agreement_rate": (champion_preds == challenger_preds).mean(),
    "avg_probability_diff": abs(champion_probs - challenger_probs).mean(),
    "max_probability_diff": abs(champion_probs - challenger_probs).max(),
}
```

**Decision thresholds:**
- Agreement >= 95% and avg probability diff < 0.05: safe to promote
- Agreement >= 85%: review disagreement cases before promoting
- Agreement < 85%: investigate root cause before considering promotion

## Cross-Workspace Promotion (Enterprise)

For regulated environments, models train in a dev-staging workspace and are promoted to a separate production workspace. This provides ZenML version upgrade isolation.

```
dev-staging workspace: training runs, full lineage, staging promotion
production workspace: imported model versions, inference runs
```

Promotion is done via a script that exports the model artifact and metadata from one workspace and imports it into the other:

```bash
python scripts/promote_cross_workspace.py \
    --model breast_cancer_classifier \
    --source-workspace enterprise-dev-staging \
    --dest-workspace enterprise-production
```

Metadata (git commit, accuracy, training environment) is preserved across the boundary for audit trails.

## Decision Guidance

- **Always attach `Model()` to training pipelines.** Without it, you cannot track versions or promote models.
- **Always use `ModelStages.PRODUCTION` in inference pipelines.** Never hardcode a version number.
- **Log metrics with `infer_model=True`** in every evaluation step. This is what makes the Model Control Plane useful for comparison and governance.
- **Use `ArtifactConfig(name=..., is_model_artifact=True)`** on trained model outputs so they are retrievable by name from the model version.
- **Name artifacts consistently** across pipeline versions. If you change the artifact name, existing model versions will not have the new name.
- **Use `force=True` on `set_stage()`** when promoting. Without it, you get an error if another version already holds the stage.
- **Implement champion/challenger comparison** before production promotion for any model where prediction drift matters.
