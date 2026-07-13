# ZenML Stack Setup

This reference covers how to set up ZenML stacks for tabular ML projects, from local development to cloud deployments.

## What Is a Stack?

A ZenML stack is a collection of infrastructure components that a pipeline runs on. Each component has a type (orchestrator, artifact store, experiment tracker, etc.) and a flavor (local, MLflow, S3, GCS, etc.).

The default stack ships with every ZenML installation:
- **Orchestrator**: `default` (local Python process)
- **Artifact Store**: `default` (local filesystem at `~/.zenml/local_stores/`)

This is enough to run pipelines locally. You add components as your requirements grow.

## Initial Setup

```bash
# Initialize ZenML in your project (sets the source root for imports)
zenml init

# Check the active stack
zenml stack describe
```

`zenml init` creates a `.zen` directory at the project root. This is critical for remote orchestrators -- without it, container-based steps may fail to resolve imports.

## Adding MLflow Experiment Tracking

MLflow is the most common experiment tracker for tabular ML projects. It tracks hyperparameters, metrics, and model artifacts across runs.

```bash
# Step 1: Install the MLflow integration
zenml integration install mlflow -y

# Step 2: Register an MLflow experiment tracker
zenml experiment-tracker register mlflow_tracker --flavor=mlflow

# Step 3: Register a new stack with the tracker
zenml stack register my_stack \
    -o default \
    -a default \
    -e mlflow_tracker

# Step 4: Activate the stack
zenml stack set my_stack
```

After this, steps with `experiment_tracker="mlflow_tracker"` in their decorator (or steps that call `mlflow.autolog()`) will automatically log to MLflow.

To view MLflow results:

```bash
mlflow ui --backend-store-uri $(zenml experiment-tracker describe --format json | python -c "import sys,json; print(json.load(sys.stdin)['tracking_uri'])")
```

## Adding Evidently Data Validation

Evidently generates data drift reports and data quality checks. Useful for monitoring pipelines.

```bash
# Install the Evidently integration
zenml integration install evidently -y

# Register the data validator
zenml data-validator register evidently_validator --flavor=evidently

# Update the stack to include it
zenml stack update my_stack --data-validator evidently_validator
```

## Integration Install Commands

ZenML integrations are bundles of Python packages for specific tools. Always install them through `zenml integration install` rather than raw pip -- this ensures compatible versions.

```bash
# Common integrations for tabular ML
zenml integration install mlflow -y          # Experiment tracking
zenml integration install evidently -y       # Data drift detection
zenml integration install sklearn -y         # Scikit-learn materializers
zenml integration install xgboost -y         # XGBoost materializers
zenml integration install lightgbm -y        # LightGBM materializers
zenml integration install feast -y           # Feature store
zenml integration install great_expectations -y  # Data validation

# Cloud orchestrators
zenml integration install gcp -y             # Vertex AI orchestrator
zenml integration install aws -y             # SageMaker orchestrator
zenml integration install azure -y           # AzureML orchestrator
zenml integration install kubernetes -y      # Kubernetes orchestrator

# Use uv for faster installs (when available)
zenml integration install mlflow --uv
```

## Stack Registration Patterns

### Local Development Stack (MLflow)

The simplest production-useful stack. Good for solo developers and learning.

```bash
zenml init
zenml integration install mlflow sklearn -y

zenml experiment-tracker register mlflow_tracker --flavor=mlflow

zenml stack register dev_stack \
    -o default \
    -a default \
    -e mlflow_tracker

zenml stack set dev_stack
```

### Local Stack with Drift Detection

Adds Evidently for data quality monitoring. Good for projects where input data changes over time.

```bash
zenml integration install mlflow sklearn evidently -y

zenml experiment-tracker register mlflow_tracker --flavor=mlflow
zenml data-validator register evidently_validator --flavor=evidently

zenml stack register full_local_stack \
    -o default \
    -a default \
    -e mlflow_tracker \
    --data-validator evidently_validator

zenml stack set full_local_stack
```

### GCP Stack (Vertex AI)

For production workloads on Google Cloud. Requires a GCP project and service account.

```bash
zenml integration install gcp mlflow -y

# Use service connectors for authentication (recommended over manual credentials)
zenml service-connector register gcp_connector \
    --type gcp \
    --auth-method service-account \
    --project-id=my-gcp-project \
    --service-account-json=@service-account.json

zenml artifact-store register gcs_store \
    --flavor=gcp \
    --path=gs://my-zenml-bucket \
    --connector gcp_connector

zenml orchestrator register vertex_orchestrator \
    --flavor=vertex \
    --project=my-gcp-project \
    --location=us-central1 \
    --connector gcp_connector

zenml container-registry register gcr_registry \
    --flavor=gcp \
    --uri=gcr.io/my-gcp-project \
    --connector gcp_connector

zenml stack register gcp_stack \
    -o vertex_orchestrator \
    -a gcs_store \
    -c gcr_registry \
    -e mlflow_tracker

zenml stack set gcp_stack
```

### AWS Stack (SageMaker)

For production workloads on AWS. Requires an AWS account and IAM role.

```bash
zenml integration install aws mlflow -y

zenml service-connector register aws_connector \
    --type aws \
    --auth-method iam-role \
    --role-arn=arn:aws:iam::123456789:role/zenml-role

zenml artifact-store register s3_store \
    --flavor=s3 \
    --path=s3://my-zenml-bucket \
    --connector aws_connector

zenml orchestrator register sagemaker_orchestrator \
    --flavor=sagemaker \
    --execution-role=arn:aws:iam::123456789:role/sagemaker-role \
    --connector aws_connector

zenml container-registry register ecr_registry \
    --flavor=aws \
    --uri=123456789.dkr.ecr.us-east-1.amazonaws.com \
    --connector aws_connector

zenml stack register aws_stack \
    -o sagemaker_orchestrator \
    -a s3_store \
    -c ecr_registry \
    -e mlflow_tracker
```

## Common Stack Configurations Summary

| Use Case | Orchestrator | Artifact Store | Extras |
|----------|-------------|----------------|--------|
| Local dev | default | default | MLflow tracker |
| Local + monitoring | default | default | MLflow + Evidently |
| GCP production | Vertex AI | GCS | MLflow + GCR |
| AWS production | SageMaker | S3 | MLflow + ECR |
| Kubernetes | Kubernetes | S3/GCS/Azure | MLflow + registry |

## Decision Guidance

- **Start with the default stack.** Add components as you need them. Do not over-engineer the stack before you have a working pipeline.
- **Use service connectors** for cloud authentication. They are more secure and portable than passing credentials directly.
- **One stack per environment.** Register separate stacks for dev, staging, and production. Switch between them with `zenml stack set`.
- **Install integrations before registering components.** The flavor won't be recognized if the integration isn't installed.
- **Use `zenml stack describe`** to verify your stack configuration before running pipelines.
- **Remote orchestrators require a container registry** and cloud artifact store. The default local artifact store only works with the default local orchestrator.

## Troubleshooting

**"StackComponentNotRegistered" error**: You haven't activated the right stack. Run `zenml stack set <stack-name>`.

**"Integration not installed" error**: Run `zenml integration install <name> -y` before registering the component.

**"Cannot connect to artifact store"**: Check your service connector configuration. Run `zenml service-connector verify <name>` to test the connection.

**Steps fail with import errors on remote orchestrators**: Run `zenml init` at the project root. Without the `.zen` directory, containers cannot resolve your project's Python imports.

## Multi-Component Stack Registration

Production stacks typically need more than an orchestrator, artifact store, and experiment tracker. Below are common additional components and how to register them.

### Registering Individual Components

```bash
# Experiment tracker (MLflow)
zenml experiment-tracker register mlflow_tracker --flavor=mlflow

# Data validator (Evidently)
zenml data-validator register evidently_validator --flavor=evidently

# Model registry (MLflow)
zenml model-registry register mlflow_registry --flavor=mlflow

# Model deployer (MLflow local serving)
zenml model-deployer register mlflow_deployer --flavor=mlflow

# Alerter (Slack)
zenml alerter register slack_alerter \
    --flavor=slack \
    --slack_token=xoxb-your-bot-token \
    --default_slack_channel_id=C01234ABCDE

# Annotator (Label Studio)
zenml annotator register label_studio \
    --flavor=label_studio \
    --url=http://localhost:8080 \
    --api_key=your-api-key

# Feature store (Feast)
zenml feature-store register feast_store \
    --flavor=feast \
    --feast_repo=./feature_repo
```

### Assembling a Full Stack

Register a stack with all components using their short flags:

```bash
zenml stack register full_stack \
    -o default \
    -a default \
    -e mlflow_tracker \
    -dv evidently_validator \
    -r mlflow_registry \
    -d mlflow_deployer \
    --alerter slack_alerter

zenml stack set full_stack
```

You can also update an existing stack to add components incrementally:

```bash
zenml stack update my_stack --alerter slack_alerter
zenml stack update my_stack --data-validator evidently_validator
zenml stack update my_stack --model-registry mlflow_registry
```

## Batch Integration Installs

Install multiple integrations in a single command to keep versions compatible:

```bash
# Full local dev setup
zenml integration install sklearn mlflow evidently -y

# Cloud orchestration with experiment tracking
zenml integration install kubeflow mlflow -y

# AWS ecosystem
zenml integration install aws s3 mlflow -y

# GCP ecosystem
zenml integration install gcp mlflow -y

# Azure ecosystem
zenml integration install azure mlflow -y

# Data validation stack
zenml integration install evidently great_expectations -y

# Full tabular ML stack (common starting point)
zenml integration install sklearn xgboost lightgbm mlflow evidently -y
```

## Environment-Specific Stack Patterns

Use separate stacks for each environment. This isolates experiments from production and prevents accidental writes to production artifact stores.

### Dev Stack (Local Everything)

For individual development and experimentation. Everything runs on localhost, no cloud credentials needed.

```bash
zenml integration install sklearn mlflow evidently -y

zenml experiment-tracker register dev_mlflow --flavor=mlflow
zenml data-validator register dev_evidently --flavor=evidently

zenml stack register dev_stack \
    -o default \
    -a default \
    -e dev_mlflow \
    -dv dev_evidently

zenml stack set dev_stack
```

Characteristics: fast iteration, no cost, no authentication setup. Artifacts stored in `~/.zenml/local_stores/`. Good for feature engineering experiments, hyperparameter tuning, and pipeline debugging.

### Staging Stack (Cloud Orchestrator + Cloud Storage)

For testing pipelines in a production-like environment before promoting to production. Uses cloud infrastructure but with separate resources from production.

```bash
zenml integration install gcp mlflow evidently -y

# Service connector for staging GCP project
zenml service-connector register staging_gcp \
    --type gcp \
    --auth-method service-account \
    --project-id=my-project-staging \
    --service-account-json=@staging-sa.json

zenml artifact-store register staging_gcs \
    --flavor=gcp \
    --path=gs://my-zenml-staging-bucket \
    --connector staging_gcp

zenml orchestrator register staging_vertex \
    --flavor=vertex \
    --project=my-project-staging \
    --location=us-central1 \
    --connector staging_gcp

zenml container-registry register staging_gcr \
    --flavor=gcp \
    --uri=gcr.io/my-project-staging \
    --connector staging_gcp

zenml experiment-tracker register staging_mlflow --flavor=mlflow
zenml data-validator register staging_evidently --flavor=evidently

zenml stack register staging_stack \
    -o staging_vertex \
    -a staging_gcs \
    -c staging_gcr \
    -e staging_mlflow \
    -dv staging_evidently

zenml stack set staging_stack
```

Characteristics: tests that pipelines run on cloud infrastructure, validates container builds, catches environment-specific bugs. Uses a separate GCP project or at minimum separate buckets and namespaces from production.

### Production Stack (Full Stack with Monitoring and Alerting)

The complete production stack includes every component needed for reliable, monitored ML operations.

```bash
zenml integration install gcp mlflow evidently -y

# Service connector for production GCP project
zenml service-connector register prod_gcp \
    --type gcp \
    --auth-method service-account \
    --project-id=my-project-prod \
    --service-account-json=@prod-sa.json

zenml artifact-store register prod_gcs \
    --flavor=gcp \
    --path=gs://my-zenml-prod-bucket \
    --connector prod_gcp

zenml orchestrator register prod_vertex \
    --flavor=vertex \
    --project=my-project-prod \
    --location=us-central1 \
    --connector prod_gcp

zenml container-registry register prod_gcr \
    --flavor=gcp \
    --uri=gcr.io/my-project-prod \
    --connector prod_gcp

zenml experiment-tracker register prod_mlflow --flavor=mlflow
zenml data-validator register prod_evidently --flavor=evidently
zenml model-registry register prod_registry --flavor=mlflow
zenml model-deployer register prod_deployer --flavor=mlflow

zenml alerter register prod_slack \
    --flavor=slack \
    --slack_token=xoxb-prod-bot-token \
    --default_slack_channel_id=C0PROD_ALERTS

zenml stack register prod_stack \
    -o prod_vertex \
    -a prod_gcs \
    -c prod_gcr \
    -e prod_mlflow \
    -dv prod_evidently \
    -r prod_registry \
    -d prod_deployer \
    --alerter prod_slack

zenml stack set prod_stack
```

Characteristics: full monitoring via Evidently, alerting via Slack, model registry for promotion workflows, model deployer for serving. All components point to production-grade infrastructure with appropriate IAM roles and network policies.

## Service Connector Setup

Service connectors manage authentication between ZenML and cloud providers. They are more secure than passing credentials directly and can be shared across components.

### AWS Service Connector

```bash
# Option 1: IAM role (recommended for production)
zenml service-connector register aws_connector \
    --type aws \
    --auth-method iam-role \
    --role-arn=arn:aws:iam::123456789012:role/zenml-connector-role \
    --region=us-east-1

# Option 2: Session token (for development)
zenml service-connector register aws_dev_connector \
    --type aws \
    --auth-method session-token \
    --aws_access_key_id=AKIA... \
    --aws_secret_access_key=... \
    --region=us-east-1

# Option 3: Implicit authentication (uses local AWS config)
zenml service-connector register aws_local_connector \
    --type aws \
    --auth-method implicit

# Verify the connector works
zenml service-connector verify aws_connector

# Use the connector with components
zenml artifact-store register s3_store \
    --flavor=s3 \
    --path=s3://my-bucket/zenml \
    --connector aws_connector

zenml orchestrator register sagemaker_orch \
    --flavor=sagemaker \
    --execution-role=arn:aws:iam::123456789012:role/sagemaker-exec \
    --connector aws_connector

zenml container-registry register ecr_registry \
    --flavor=aws \
    --uri=123456789012.dkr.ecr.us-east-1.amazonaws.com \
    --connector aws_connector
```

### GCP Service Connector

```bash
# Option 1: Service account JSON key (common for CI/CD)
zenml service-connector register gcp_connector \
    --type gcp \
    --auth-method service-account \
    --project-id=my-gcp-project \
    --service-account-json=@path/to/service-account.json

# Option 2: External account (workload identity federation)
zenml service-connector register gcp_wif_connector \
    --type gcp \
    --auth-method external-account \
    --project-id=my-gcp-project \
    --external-account-json=@path/to/external-account.json

# Option 3: Implicit authentication (uses local gcloud config)
zenml service-connector register gcp_local_connector \
    --type gcp \
    --auth-method implicit

# Verify the connector works
zenml service-connector verify gcp_connector

# Use the connector with components
zenml artifact-store register gcs_store \
    --flavor=gcp \
    --path=gs://my-bucket/zenml \
    --connector gcp_connector

zenml orchestrator register vertex_orch \
    --flavor=vertex \
    --project=my-gcp-project \
    --location=us-central1 \
    --connector gcp_connector

zenml container-registry register gcr_registry \
    --flavor=gcp \
    --uri=gcr.io/my-gcp-project \
    --connector gcp_connector
```

### Service Connector Best Practices

- **Use one connector per environment.** A `dev_aws_connector` and `prod_aws_connector` with different IAM roles and permissions.
- **Use IAM roles or workload identity in production.** Avoid long-lived access keys. Session tokens and service account keys are acceptable for development but should be rotated.
- **Always verify after registration.** `zenml service-connector verify <name>` confirms the credentials work and the connector can reach the target services.
- **Scope connectors narrowly.** A connector for artifact storage does not need permissions to manage Kubernetes clusters. Use separate connectors with minimal IAM policies when security requirements demand it.
- **List available connectors** to audit what is configured: `zenml service-connector list`.
