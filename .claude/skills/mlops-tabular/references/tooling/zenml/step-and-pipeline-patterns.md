# ZenML Step and Pipeline Patterns

This reference covers how to write ZenML steps and pipelines for tabular ML projects. It is written for an AI coding agent generating ZenML code.

## The @step Decorator

Every unit of work is a Python function decorated with `@step`. Type hints on inputs and outputs are mandatory -- they control serialization, caching, and dashboard display.

```python
from zenml import step
import pandas as pd
from sklearn.base import ClassifierMixin

@step
def train_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    n_estimators: int = 100,
) -> ClassifierMixin:
    model = RandomForestClassifier(n_estimators=n_estimators)
    model.fit(X_train, y_train)
    return model
```

**Parameters vs artifacts**: If a step input comes from another step's output, it is an artifact. If it is a literal value passed directly (JSON-serializable), it is a parameter. ZenML handles them differently for caching and serialization.

### Named Outputs with Annotated

Always name outputs using `Annotated`. This gives artifacts stable names in the dashboard and makes them retrievable from the Model Control Plane.

```python
from typing import Annotated
import pandas as pd
from zenml import step

@step
def split_data(df: pd.DataFrame, ratio: float = 0.8) -> tuple[
    Annotated[pd.DataFrame, "train"],
    Annotated[pd.DataFrame, "test"],
]:
    idx = int(len(df) * ratio)
    return df.iloc[:idx], df.iloc[idx:]
```

### ArtifactConfig for Model Artifacts

Use `ArtifactConfig` when an artifact should be registered in the Model Control Plane as a model artifact (not just data). This is critical for the artifact to appear under the model version in the dashboard.

```python
from zenml import ArtifactConfig, step
from zenml.enums import ArtifactType

@step(enable_cache=False)
def train_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
) -> Annotated[
    ClassifierMixin,
    ArtifactConfig(name="sklearn_classifier", artifact_type=ArtifactType.MODEL),
]:
    model = RandomForestClassifier().fit(X_train, y_train)
    return model
```

The `is_model_artifact=True` shorthand also works: `ArtifactConfig(name="sklearn_classifier", is_model_artifact=True)`.

### Disabling Cache on Specific Steps

Steps that must always re-execute (training, evaluation) should set `enable_cache=False`:

```python
@step(enable_cache=False)
def evaluate_model(model: ClassifierMixin, X_test: pd.DataFrame, y_test: pd.Series) -> Annotated[dict, "metrics"]:
    ...
```

Cache-friendly steps (data loading with fixed paths, preprocessing with deterministic logic) can leave caching enabled for faster iteration.

### Logging Metadata

Use `log_metadata` inside steps to attach metrics to the model version in the Model Control Plane:

```python
from zenml import log_metadata, step

@step
def evaluate_model(model, X_test, y_test) -> Annotated[dict, "metrics"]:
    metrics = {"accuracy": 0.95, "f1": 0.90, "auc": 0.97}
    log_metadata(metadata=metrics, infer_model=True)
    return metrics
```

`infer_model=True` automatically attaches metadata to the pipeline's associated model version.

### Step Context

Access runtime information inside a step using `get_step_context()`:

```python
from zenml import get_step_context, step

@step
def predict(X: pd.DataFrame) -> pd.DataFrame:
    context = get_step_context()
    model = context.model.load_artifact("sklearn_classifier")
    scaler = context.model.load_artifact("scaler")
    # Use model and scaler...
```

The step context provides access to the current model version, pipeline run metadata, and artifacts from the Model Control Plane.

## The @pipeline Decorator

A pipeline is a function decorated with `@pipeline` that calls steps. The function body defines the DAG -- data flows through step return values.

```python
from zenml import Model, pipeline

@pipeline(
    model=Model(
        name="loan_default_predictor",
        description="predicts which loan applicants will default",
        tags=["classification", "sklearn", "loan-default"],
    ),
    enable_cache=False,
)
def training_pipeline(data_path: str = "data/loans_2015.csv"):
    df = load_data(path=data_path)
    X_train, X_test, y_train, y_test = preprocess(df=df)
    model = train_model(X_train=X_train, y_train=y_train)
    evaluate_model(model=model, X_test=X_test, y_test=y_test)
```

### The Model() Decorator

Attaching `Model()` to a pipeline registers every run under that model name in the Model Control Plane. Each run creates a new model version automatically.

Key `Model()` parameters:
- `name`: The model name in the registry (use snake_case, descriptive)
- `description`: Human-readable description
- `tags`: List of strings for filtering and governance (use `key:value` format for structured tags like `use_case:fraud`, `owner_team:ml-platform`)
- `version`: Pin to a specific version or stage (used in inference pipelines)

### Pipeline Composition: Passing Data Between Steps

Data flows via return values. Never pass file paths between steps -- this is the Artifact Golden Rule.

```python
# WRONG: breaks on remote orchestrators
@step
def preprocess(path: str) -> str:
    df = pd.read_csv(path)
    df.to_csv("/tmp/processed.csv")
    return "/tmp/processed.csv"  # Next step can't access /tmp on another pod

# CORRECT: data flows as artifacts
@step
def preprocess(path: str) -> pd.DataFrame:
    return pd.read_csv(path)

@step
def train(data: pd.DataFrame) -> ClassifierMixin:
    ...  # ZenML loads data from artifact store automatically
```

The first step in a pipeline bridges external data (files, databases, APIs) into the artifact world. All downstream steps receive artifacts.

### Step Invocation IDs

When calling the same step function multiple times in one pipeline, ZenML auto-suffixes the name. Override with the `id` parameter:

```python
champion_preds = predict_with_model(data=X, model_stage="staging", id="champion_predict")
challenger_preds = predict_with_model(data=X, model_stage="challenger", id="challenger_predict")
```

### No Pipeline-Level Conditionals on Artifacts

ZenML compiles the pipeline to a DAG before execution. Step outputs are artifact references, not Python values. You cannot use `if` on a step output at the pipeline level.

```python
# WRONG: step output is not a boolean at compile time
@pipeline
def my_pipeline():
    needs_smote = check_imbalance(data)
    if needs_smote:  # FAILS
        apply_smote()

# CORRECT: put conditional logic inside the step
@step
def check_and_apply_smote(X_train, y_train, enable_resampling: bool = False) -> tuple[pd.DataFrame, pd.Series]:
    if not enable_resampling:
        return X_train, y_train
    if minority_ratio < threshold:
        return smote.fit_resample(X_train, y_train)
    return X_train, y_train
```

## Caching Behavior

ZenML caches step outputs by default. A step is re-used from cache when its inputs (artifacts + parameters), source code, and environment are identical.

**Decision guidance:**
- Disable cache on training steps (`enable_cache=False` on the step) to ensure fresh model training
- Disable cache on evaluation steps to ensure metrics reflect the current model
- Leave cache enabled on data loading and preprocessing for faster iteration
- Disable cache at the pipeline level (`enable_cache=False` on `@pipeline`) for staging/production runs
- Enable cache at the pipeline level for local development

## YAML Configuration

Separate environment-specific settings from pipeline code. Create one YAML config per environment.

```yaml
# configs/local.yaml
run_name: "training_local_{date}_{time}"
enable_cache: true
parameters:
  test_size: 0.2
  n_estimators: 70
  max_depth: 5
  min_accuracy: 0.70
tags:
  - "local"
  - "development"
settings:
  docker:
    python_package_installer: uv
    required_integrations:
      - sklearn
```

```yaml
# configs/production.yaml
run_name: "training_production_{date}_{time}"
enable_cache: false
parameters:
  n_estimators: 100
  max_depth: 10
  min_accuracy: 0.80
tags:
  - "production"
  - "release"
settings:
  docker:
    python_package_installer: uv
    required_integrations:
      - sklearn
  resources:
    cpu_count: 4
    memory: 8GB
```

Apply configs at runtime:

```python
training_pipeline.with_options(config_path="configs/local.yaml")()
```

**Configuration precedence** (highest to lowest): Runtime Python code > Step-level YAML > Pipeline-level YAML > Defaults.

Prefer `with_options()` (returns a copy) over `configure()` (mutates in place).

## Project Structure

Every ZenML pipeline project should follow this layout:

```
project/
├── steps/                  # One file per step
│   ├── load_data.py
│   ├── preprocess.py
│   ├── train.py
│   └── evaluate.py
├── pipelines/
│   └── training_pipeline.py
├── configs/
│   ├── local.yaml
│   ├── staging.yaml
│   └── production.yaml
├── run.py                  # CLI entry point (argparse, not click)
└── pyproject.toml
```

Key rules:
- One step per file in `steps/`
- Separate pipeline definition from execution
- `run.py` uses `argparse` (click conflicts with ZenML's own click dependency)
- Run `zenml init` at project root to set the source root for container imports

## run.py Pattern

```python
import argparse
from pipelines.training_pipeline import training_pipeline

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/local.yaml")
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()

    pipeline_instance = training_pipeline.with_options(
        config_path=args.config,
        enable_cache=not args.no_cache,
    )
    pipeline_instance()

if __name__ == "__main__":
    main()
```
