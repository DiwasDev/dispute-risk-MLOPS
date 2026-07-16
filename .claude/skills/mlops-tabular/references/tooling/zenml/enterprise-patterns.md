# ZenML Enterprise Patterns

This reference covers production-grade ZenML patterns for regulated and enterprise environments: governance hooks, validation gates, environment-specific configs, Docker management, and multi-workspace architecture.

## Separation of Concerns

Enterprise ZenML projects split ownership between two teams:

```
governance/     # Platform team owns (hooks, validation, infrastructure)
src/            # Data scientists own (ML code, pipelines, steps)
```

Data scientists write pure Python ML code. The platform team enforces compliance automatically via hooks and shared validation steps. ML code never contains governance logic directly.

```python
# Data scientist's pipeline -- clean, no governance mixed in
@pipeline(model=Model(name="breast_cancer_classifier"))
def training_pipeline():
    data = load_data()
    model = train_model(data)
    metrics = evaluate_model(model, data)
```

```python
# run.py applies governance based on environment
if environment in ("staging", "production"):
    from governance.hooks import pipeline_governance_success_hook, pipeline_failure_hook
    training_pipeline.with_options(
        on_success=pipeline_governance_success_hook,
        on_failure=pipeline_failure_hook,
    )(**kwargs)
else:
    training_pipeline(**kwargs)  # Local dev: no hooks, fast iteration
```

## Governance Hooks

Hooks are functions that run automatically on pipeline or step success/failure. They are the primary mechanism for governance enforcement without touching ML code.

### Alerting Hooks

Send notifications to Slack or other alerters when pipelines succeed or fail:

```python
from zenml import get_step_context
from zenml.client import Client

def pipeline_success_hook() -> None:
    context = get_step_context()
    pipeline_name = context.pipeline_run.pipeline.name
    model_info = ""
    if context.model:
        model_info = f"\n- Model: {context.model.name} v{context.model.version}"

    client = Client()
    alerter = client.active_stack.alerter
    if alerter:
        alerter.post(message=f"Pipeline '{pipeline_name}' completed.{model_info}")

def pipeline_failure_hook(exception: BaseException) -> None:
    context = get_step_context()
    pipeline_name = context.pipeline_run.pipeline.name
    client = Client()
    alerter = client.active_stack.alerter
    if alerter:
        alerter.post(message=f"Pipeline '{pipeline_name}' FAILED: {exception}")
```

Key pattern: hooks should never crash the pipeline. Wrap hook logic in try/except and log warnings on failure.

### Compliance Hooks

Enforce model governance policies -- required tags, naming conventions, git traceability:

```python
def model_governance_hook() -> None:
    context = get_step_context()
    if not context.model:
        return

    model = context.model
    model_tags = [tag.name for tag in model_version.tags]

    # Enforce required tag prefixes
    required_prefixes = ["use_case:", "owner_team:"]
    missing = [p for p in required_prefixes if not any(t.startswith(p) for t in model_tags)]
    if missing:
        logger.warning(f"Missing required tag prefixes: {missing}")

    # Check git commit for reproducibility
    git_commit = os.getenv("GIT_COMMIT") or os.getenv("GITHUB_SHA")
    if not git_commit:
        logger.info("No git commit found. Set GIT_COMMIT for full compliance.")
```

### Monitoring Hooks

Send metrics to observability platforms (Datadog, Prometheus) after pipeline completion:

```python
def monitoring_success_hook() -> None:
    context = get_step_context()
    # Push pipeline duration, step count, model metrics to monitoring
```

### Applying Hooks

Hooks are applied at the pipeline level, not baked into step code:

```python
@pipeline(
    on_success=pipeline_success_hook,
    on_failure=pipeline_failure_hook,
)
def batch_inference_pipeline():
    ...
```

Or applied conditionally in `run.py` based on environment.

## Data Validation Steps

Platform-maintained steps that enforce data quality gates. Every training pipeline must include them.

```python
from governance.steps import validate_data_quality

@step
def validate_data_quality(
    dataset: pd.DataFrame,
    min_rows: int = 100,
    max_missing_fraction: float = 0.1,
) -> Annotated[pd.DataFrame, "validated_data"]:
    if len(dataset) < min_rows:
        raise ValueError(f"Dataset has {len(dataset)} rows, minimum is {min_rows}")

    missing_fraction = dataset.isnull().sum().sum() / (dataset.shape[0] * dataset.shape[1])
    if missing_fraction > max_missing_fraction:
        raise ValueError(f"{missing_fraction:.2%} missing values exceeds {max_missing_fraction:.2%}")

    return dataset
```

Usage in the pipeline:

```python
X_train, X_test, y_train, y_test = load_data()
X_train = validate_data_quality(X_train, min_rows=100)  # Gate
model = train_model(X_train, y_train)
```

If validation fails, the pipeline stops before training. No compute is wasted on bad data.

## Model Validation Gates

Enforce minimum performance thresholds before a model can be promoted:

```python
@step
def validate_model_performance(
    metrics: dict[str, float],
    min_accuracy: float = 0.7,
    min_precision: float = 0.7,
    min_recall: float = 0.7,
) -> Annotated[bool, "validation_passed"]:
    failures = []
    if metrics.get("accuracy", 0) < min_accuracy:
        failures.append(f"Accuracy {metrics['accuracy']:.3f} < {min_accuracy}")
    if metrics.get("precision", 0) < min_precision:
        failures.append(f"Precision {metrics['precision']:.3f} < {min_precision}")
    if metrics.get("recall", 0) < min_recall:
        failures.append(f"Recall {metrics['recall']:.3f} < {min_recall}")

    if failures:
        raise ValueError("Model validation failed:\n" + "\n".join(f"  - {f}" for f in failures))
    return True
```

Thresholds differ by environment:
- Local: `min_accuracy=0.70` (lenient, for fast iteration)
- Staging: `min_accuracy=0.70` (same, but with SMOTE enabled)
- Production: `min_accuracy=0.80` (strict)

## Training Reports

Generate HTML reports for PR comments, audit trails, and model approval decisions:

```python
@step
def generate_training_report(
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    metrics: dict,
    min_accuracy: float = 0.7,
) -> Annotated[HTMLString, "training_report"]:
    # Generate markdown with data quality + model performance tables
    # Convert to HTML with styling for the ZenML dashboard
    return HTMLString(html_report)
```

Reports include:
- Data quality checks (row count, missing values, duplicates)
- Model performance vs thresholds (pass/fail for each metric)
- Overall decision (passed/failed)
- Next steps (merge PR to promote, or fix issues)

## Environment-Specific Configs

Create one YAML config per environment. Configs control parameters, thresholds, Docker settings, and resource allocation.

### Local Config (fast iteration)

```yaml
# configs/local.yaml
run_name: "training_local_{date}_{time}"
enable_cache: true
parameters:
  n_estimators: 70
  max_depth: 5
  min_accuracy: 0.70
  enable_resampling: false
  enable_governance: false    # Skip validation for speed
tags: ["local", "development"]
settings:
  docker:
    python_package_installer: uv
    required_integrations: [sklearn]
  resources:
    cpu_count: 2
    memory: 4GB
```

### Staging Config (production-like)

```yaml
# configs/staging.yaml
run_name: "training_staging_{date}_{time}"
enable_cache: false
parameters:
  n_estimators: 50
  max_depth: 5
  min_accuracy: 0.70
  enable_resampling: true
  enable_governance: true
tags: ["staging", "pre-release"]
settings:
  docker:
    python_package_installer: uv
    required_integrations: [sklearn]
  orchestrator:
    synchronous: false
  resources:
    cpu_count: 2
    memory: 4GB
```

### Production Config (strict thresholds)

```yaml
# configs/production.yaml
run_name: "training_production_{date}_{time}"
enable_cache: false
parameters:
  n_estimators: 100
  max_depth: 10
  min_accuracy: 0.80
  enable_resampling: true
  enable_governance: true
tags: ["production", "release"]
settings:
  docker:
    python_package_installer: uv
    required_integrations: [sklearn]
  resources:
    cpu_count: 4
    memory: 8GB
```

## Docker Settings Management

The platform team provides pre-configured Docker settings. Data scientists import them instead of writing their own.

```python
# governance/docker/docker_settings.py
from zenml.config import DockerSettings

STANDARD_DOCKER_SETTINGS = DockerSettings(
    python_package_installer="uv",
    required_integrations=["sklearn"],
    requirements=["pandas>=2.0"],
)

GPU_DOCKER_SETTINGS = DockerSettings(
    parent_image="pytorch/pytorch:2.2.0-cuda11.8-cudnn8-runtime",
    python_package_installer="uv",
    requirements=["transformers", "accelerate"],
)
```

Usage by data scientists:

```python
from governance.docker import STANDARD_DOCKER_SETTINGS

@pipeline(settings={"docker": STANDARD_DOCKER_SETTINGS})
def training_pipeline():
    ...
```

Docker settings can also live in YAML configs under the `settings.docker` key.

## 2-Workspace Architecture

For enterprises needing version upgrade isolation and clear audit boundaries.

```
Organization: Enterprise MLOps
├── Workspace: enterprise-dev-staging
│   ├── Stack: dev-stack (local orchestrator, fast iteration)
│   ├── Stack: staging-stack (Vertex AI, production-like)
│   └── Model versions: none -> staging stages
│
└── Workspace: enterprise-production
    ├── Stack: gcp-stack (Vertex AI, production)
    └── Imported model versions: production stage only
```

**Why 2 workspaces (not 1, not 3)?**
- ZenML version upgrades in dev-staging do not affect production
- Training lineage is fully preserved in dev-staging
- Only one lineage break at the staging-to-production boundary
- Three workspaces would create two lineage breaks with more complexity

### Cross-Workspace Promotion

Models trained in dev-staging are exported and imported to production:

```bash
# Train and validate in dev-staging
zenml login enterprise-dev-staging
python run.py --pipeline training --config configs/staging.yaml

# Promote to production workspace
python scripts/promote_cross_workspace.py \
    --model breast_cancer_classifier \
    --source-workspace enterprise-dev-staging \
    --dest-workspace enterprise-production
```

Metadata (git commit, accuracy, training environment) is preserved across the workspace boundary for regulatory compliance.

## GitOps Workflows

Git events trigger ML workflows through GitHub Actions:

```
PR to staging branch   -> Auto-train model in staging environment
GitHub Release created -> Promote model to production
Cron schedule (daily)  -> Run batch inference pipeline
```

```yaml
# .github/workflows/train-staging.yml
on:
  pull_request:
    branches: [staging]
jobs:
  train:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python run.py --pipeline training --config configs/staging.yaml
```

## Decision Guidance

- **Separate governance from ML code.** Platform team owns `governance/`, data scientists own `src/`. Never mix.
- **Apply hooks conditionally by environment.** Local dev should be fast with no hooks. Staging and production get full governance.
- **Use data validation gates early in the pipeline.** Fail fast on bad data before wasting compute on training.
- **Set different thresholds per environment.** Lenient locally, strict in production.
- **Generate training reports for every staging/production run.** They serve as audit trail and PR review material.
- **Use 2 workspaces for enterprise deployments.** One for dev-staging (full lineage), one for production (inference lineage).
- **Platform-managed Docker settings** ensure data scientists get consistent, secure environments without writing Dockerfiles.
