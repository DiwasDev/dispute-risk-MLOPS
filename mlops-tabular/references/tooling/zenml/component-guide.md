# ZenML Component Guide Reference

Reference for selecting and composing ZenML stack components. Use this to recommend the right stack configuration for a user's MLOps project based on their team size, cloud provider, and maturity level.

---

## 1. Stack Component Types

A ZenML **stack** is the configuration of infrastructure and tooling that defines where and how a pipeline executes. Every stack must contain at least an **orchestrator** and an **artifact store**. All other components are optional and added as the project matures.

### Mandatory Components

| Component | Role |
|-----------|------|
| **Orchestrator** | Coordinates step execution order and manages the pipeline DAG. Decides what runs, when, and where. |
| **Artifact Store** | Persists all step inputs and outputs between steps. Enables caching, versioning, and reproducibility. |

### Optional Components

| Component | Role |
|-----------|------|
| **Container Registry** | Stores Docker images that hold pipeline code and dependencies. Required when the orchestrator runs in a containerized environment (Kubernetes, Kubeflow, cloud-managed). |
| **Image Builder** | Builds container images for pipeline steps. Offloads Docker builds to cloud services when local Docker is unavailable or too slow. |
| **Experiment Tracker** | Logs metrics, parameters, and artifacts for each run so you can compare experiments across iterations. |
| **Model Registry** | Manages trained model versions, their metadata, stage transitions (staging/production), and deployment state. |
| **Data Validator** | Validates data quality and model performance by running statistical tests, drift detection, and integrity checks on pipeline data. |
| **Model Deployer** | Serves trained models as online prediction endpoints. Manages the lifecycle of model serving infrastructure. |
| **Deployer** | Deploys entire pipelines as long-running HTTP services for real-time, request-response execution (distinct from Model Deployer, which serves individual models). |
| **Step Operator** | Offloads individual steps to specialized compute environments (GPU instances, Spark clusters) while the orchestrator handles the rest of the DAG. |
| **Feature Store** | Centralizes feature engineering, storage, and serving so features are consistent between training and inference. |
| **Annotator** | Connects to data labeling platforms for creating and managing annotation workflows within pipelines. |
| **Alerter** | Sends notifications through messaging channels (Slack, Discord) when pipeline events occur (failures, drift detected, deployment complete). |
| **Log Store** | Collects, stores, and retrieves stdout/stderr and logging output from pipeline steps. Defaults to storing logs in the artifact store if not explicitly configured. |
| **Service Connector** | Abstracts cloud authentication so data scientists never handle raw credentials. One connector can authenticate multiple stack components to cloud resources. |

---

## 2. Available Flavors per Component

### Orchestrator
| Flavor | Integration | Best For |
|--------|------------|----------|
| Local | built-in | Development and testing on a single machine |
| Local Docker | built-in | Testing containerized pipelines locally |
| Kubernetes | `kubernetes` | Production workloads on any K8s cluster |
| Kubeflow | `kubeflow` | Teams already using Kubeflow Pipelines |
| Tekton | `tekton` | CI/CD-native pipeline orchestration on K8s |
| Airflow | `airflow` | Organizations with existing Airflow infrastructure |
| SageMaker | `aws` | AWS-native ML workflows with managed compute |
| Vertex AI | `gcp` | GCP-native ML workflows with managed compute |
| AzureML | `azure` | Azure-native ML workflows with managed compute |
| Databricks | `databricks` | Teams using Databricks for data and ML |
| Lightning | `lightning` | Lightning AI cloud-based training |
| SkyPilot | `skypilot` | Multi-cloud cost-optimized VM orchestration |
| HyperAI | `hyperai` | HyperAI cluster orchestration |

### Artifact Store
| Flavor | Integration | Best For |
|--------|------------|----------|
| Local | built-in | Development only (not shareable) |
| S3 | `s3` | AWS deployments |
| GCS | `gcp` | GCP deployments |
| Azure Blob | `azure` | Azure deployments |
| MinIO | built-in | Self-hosted S3-compatible storage |
| Alibaba OSS | `alibaba` | Alibaba Cloud deployments |

### Container Registry
| Flavor | Integration |
|--------|------------|
| Default (generic) | built-in |
| DockerHub | built-in |
| AWS ECR | `aws` |
| GCP GCR/Artifact Registry | `gcp` |
| Azure ACR | `azure` |
| GitHub Container Registry | `github` |

### Image Builder
| Flavor | Integration |
|--------|------------|
| Local | built-in |
| AWS CodeBuild | `aws` |
| GCP Cloud Build | `gcp` |
| Kaniko | `kaniko` |

### Experiment Tracker
| Flavor | Integration | Notes |
|--------|------------|-------|
| MLflow | `mlflow` | Open-source, self-hostable, most common choice |
| Weights & Biases | `wandb` | SaaS-first, strong visualization and collaboration |
| Comet | `comet` | SaaS with good comparison features |
| Neptune | `neptune` | SaaS with metadata management focus |
| Vertex AI | `gcp` | GCP-native experiment tracking |

### Data Validator
| Flavor | Integration | Notes |
|--------|------------|-------|
| Great Expectations | `great_expectations` | Rule-based data quality with expectation suites |
| Evidently | `evidently` | Data and model drift detection with reports |
| Deepchecks | `deepchecks` | Comprehensive data and model validation checks |
| WhyLabs/whylogs | `whylogs` | Statistical profiling and drift monitoring |

### Model Deployer
| Flavor | Integration | Notes |
|--------|------------|-------|
| MLflow | `mlflow` | Simple local/Docker model serving |
| Seldon Core | `seldon` | Production K8s model serving with advanced routing |
| BentoML | `bentoml` | Framework-agnostic model packaging and serving |
| Hugging Face | `huggingface` | Deploy to HF Inference Endpoints |
| Databricks | `databricks` | Databricks model serving endpoints |
| vLLM | `vllm` | High-throughput LLM serving |

### Deployer (Pipeline-as-a-Service)
| Flavor | Integration | Notes |
|--------|------------|-------|
| Local | built-in | Background process on local machine (dev only) |
| Docker | built-in | Local Docker container deployment |
| Kubernetes | `kubernetes` | Deploy pipeline HTTP services to any K8s cluster |
| GCP Cloud Run | `gcp` | Serverless pipeline deployment on GCP |
| AWS App Runner | `aws` | Serverless pipeline deployment on AWS |
| Hugging Face | `huggingface` | Deploy as HF Spaces Docker Spaces |

### Step Operator
| Flavor | Integration | Notes |
|--------|------------|-------|
| SageMaker | `aws` | Run individual steps on SageMaker training jobs |
| Vertex AI | `gcp` | Run individual steps on Vertex AI custom jobs |
| AzureML | `azure` | Run individual steps on AzureML compute |
| Kubernetes | `kubernetes` | Run steps as K8s jobs with custom resources |
| Spark on Kubernetes | `spark` | Run Spark jobs for distributed data processing |
| Modal | `modal` | Serverless GPU compute for individual steps |
| Run:AI | `runai` | GPU cluster management for ML workloads |

### Model Registry
| Flavor | Integration |
|--------|------------|
| MLflow | `mlflow` |

### Feature Store
| Flavor | Integration |
|--------|------------|
| Feast | `feast` |

### Annotator
| Flavor | Integration |
|--------|------------|
| Label Studio | `label_studio` |
| Pigeon | `pigeon` |
| Prodigy | `prodigy` |
| Argilla | `argilla` |

### Alerter
| Flavor | Integration |
|--------|------------|
| Slack | `slack` |
| Discord | `discord` |

### Log Store
| Flavor | Integration | Notes |
|--------|------------|-------|
| Artifact | built-in | Default; stores logs in the artifact store |
| Datadog | `datadog` | Route logs to Datadog for centralized observability |
| OpenTelemetry | `otel` | Route logs via OTLP to any OTEL-compatible backend (Jaeger, Grafana Tempo, Honeycomb, etc.) |

### Service Connector Types
| Type | Resources Provided |
|------|-------------------|
| AWS | S3 buckets, EKS clusters, ECR registries, generic AWS resources |
| GCP | GCS buckets, GKE clusters, GCR/Artifact Registry, generic GCP resources |
| Azure | Blob containers, AKS clusters, ACR registries, generic Azure resources |
| Kubernetes | Any Kubernetes cluster (cloud or on-prem) |
| Docker | Any Docker registry |
| HyperAI | HyperAI cluster resources |

---

## 3. Stack Composition Rules

### What is mandatory
Every stack requires exactly one **orchestrator** and one **artifact store**. The default stack uses local flavors of both, which is sufficient for single-machine development.

### When a container registry becomes required
Any orchestrator that runs steps in containers needs a container registry. This includes: Kubernetes, Kubeflow, Tekton, SageMaker, Vertex AI, AzureML, Airflow (remote), Databricks, and SkyPilot. The local and local-docker orchestrators do not require one.

### How components connect
- The **orchestrator** reads from and writes to the **artifact store** for every step.
- The **orchestrator** pulls images from the **container registry** (if containerized).
- The **image builder** pushes images to the **container registry**.
- The **step operator** overrides compute for specific steps; the orchestrator still manages the DAG.
- The **experiment tracker** is called within step code to log metrics.
- The **data validator** is called within step code to validate data.
- **Service connectors** provide credentials to any component that needs cloud access (artifact store, container registry, orchestrator, step operator, etc.).

### Authentication pattern
Rather than configuring credentials on each component individually, register a **service connector** for your cloud provider and link it to multiple components. This centralizes credential management and supports automatic token rotation.

---

## 4. Stack Patterns -- Decision Matrix

### Local Development Stack
| Component | Flavor | Notes |
|-----------|--------|-------|
| Orchestrator | Local | Runs in a Python thread |
| Artifact Store | Local | Stores artifacts on local filesystem |
| Others | None | Keep it simple for prototyping |

**Use when:** Prototyping, learning ZenML, running quick experiments. No cloud access needed.

### Small Team Cloud Stack (AWS example)
| Component | Flavor | Notes |
|-----------|--------|-------|
| Orchestrator | SageMaker or Kubernetes | Managed compute |
| Artifact Store | S3 | Shared, durable storage |
| Container Registry | AWS ECR | Required for containerized orchestration |
| Experiment Tracker | MLflow or W&B | Compare runs across the team |
| Service Connector | AWS | Centralizes IAM authentication |

**GCP equivalent:** Vertex AI orchestrator + GCS artifact store + GCP Artifact Registry + Vertex AI or W&B experiment tracker + GCP service connector.

**Azure equivalent:** AzureML orchestrator + Azure Blob artifact store + Azure ACR + MLflow or W&B experiment tracker + Azure service connector.

**Use when:** Small team (2-10 people) moving from local experiments to shared cloud infrastructure. Need reproducibility and collaboration but not full governance.

### Production Stack
| Component | Flavor | Notes |
|-----------|--------|-------|
| Orchestrator | Kubernetes or Kubeflow | Full control over scheduling and resources |
| Artifact Store | S3 / GCS / Azure Blob | Cloud-native durable storage |
| Container Registry | ECR / GCR / ACR | Cloud-native registry |
| Image Builder | Cloud Build / CodeBuild | Offload builds from local machines |
| Experiment Tracker | MLflow / W&B | Track all production experiments |
| Data Validator | Evidently or Great Expectations | Catch data drift before it damages models |
| Model Deployer | Seldon / BentoML | Serve models with production-grade infra |
| Alerter | Slack | Notify team of pipeline failures or drift |
| Log Store | Datadog or OpenTelemetry | Centralized observability |
| Service Connector | Cloud-specific | Role-based access, no raw credentials |

**Use when:** Running models in production, serving real traffic, need monitoring and alerting, must meet reliability requirements.

### Enterprise Stack
Everything in Production Stack, plus:

| Component | Flavor | Notes |
|-----------|--------|-------|
| Step Operator | SageMaker / Vertex AI | GPU workloads for training steps |
| Model Registry | MLflow | Track model versions and stage transitions |
| Feature Store | Feast | Consistent features across training and serving |
| Annotator | Label Studio / Argilla | In-pipeline data labeling workflows |
| Deployer | Kubernetes / Cloud Run | Serve entire pipelines as HTTP endpoints |

**Use when:** Large organization, multiple teams, need governance, audit trails, feature reuse, and full lifecycle management.

---

## 5. When to Add Each Component -- Decision Guidance

Use these rules to advise users on what to add and when:

- **Experiment Tracker**: Add when you need to compare metrics across runs, or when more than one person is iterating on the same model. Without one, you lose the ability to answer "which run was best and why."

- **Data Validator**: Add when data quality affects model performance and you cannot afford silent failures. Critical for production pipelines where input data comes from external sources that may change schema or distribution over time.

- **Model Deployer**: Add when you need to serve predictions via an API endpoint. If you only need batch predictions written to a file or database, you do not need this.

- **Deployer (Pipeline-as-a-Service)**: Add when you need to expose an entire pipeline (not just a model) as an HTTP endpoint for real-time, on-demand execution. Distinct from a model deployer.

- **Step Operator**: Add when specific steps need specialized hardware (GPUs, high-memory instances) but your orchestrator runs on standard compute. Avoids over-provisioning the entire pipeline.

- **Container Registry**: Add as soon as you move away from the local orchestrator to any remote or containerized orchestrator. Not optional in cloud stacks.

- **Image Builder**: Add when local Docker builds are too slow, unreliable, or when your CI/CD environment does not have Docker available. Cloud image builders parallelize and cache builds.

- **Feature Store**: Add when multiple models or teams reuse the same features, or when you need point-in-time correctness for feature lookups during training and serving.

- **Model Registry**: Add when you need formal stage transitions (staging to production), model approval workflows, or an auditable record of which model version is deployed.

- **Alerter**: Add when pipeline failures or data quality issues need immediate human attention. Essential for production stacks.

- **Log Store**: The default artifact-based log store works for most cases. Switch to Datadog or OpenTelemetry when you need centralized log aggregation, search across runs, or integration with existing observability tooling.

- **Annotator**: Add when your pipeline includes a human-in-the-loop labeling step, such as active learning workflows or data quality review.

- **Service Connector**: Add as soon as any component needs cloud credentials. Should be the first thing configured when setting up a cloud stack. Without it, every team member manages their own credentials, which is a security risk.

---

## 6. Service Connectors -- Authentication Abstraction

Service connectors solve the problem of credential management across stack components. Instead of configuring AWS keys on your S3 artifact store, ECR container registry, and SageMaker orchestrator separately, you register one AWS service connector and link all three components to it.

### How they work
1. An infrastructure admin registers a service connector with cloud credentials (IAM role, service account key, service principal).
2. The connector is linked to stack components that need access to cloud resources.
3. When a pipeline runs, ZenML uses the connector to generate short-lived credentials for each component.
4. Data scientists never see or handle raw credentials.

### Supported authentication methods by provider

**AWS**: Implicit (environment), secret key, STS token, IAM role, session token, federation token.

**GCP**: Implicit (environment), user account, service account, OAuth2 token, impersonation.

**Azure**: Implicit (environment), service principal, access token.

**Kubernetes**: Password, token (for any K8s cluster regardless of cloud provider).

**Docker**: Password (for any Docker registry).

### Recommended workflow
- Limit service connector creation to infrastructure/platform engineers who have direct cloud access.
- Create separate connectors for development/staging and production environments.
- Use ZenML Pro role-based access control to restrict which users can use which connectors.
- This separation prevents accidental use of production resources during development and makes credential revocation straightforward if a connector is compromised.

### CLI quick reference
```bash
# List available connector types
zenml service-connector list-types

# Register an AWS connector
zenml service-connector register aws-prod --type aws --auth-method iam-role --role_arn=arn:aws:iam::123456789:role/zenml

# Connect an artifact store to the connector
zenml artifact-store connect my-s3-store --connector aws-prod

# Verify the connector works
zenml service-connector verify aws-prod
```

---

## Quick Reference: Minimum Viable Stacks

| Goal | Minimum Components |
|------|--------------------|
| Learn ZenML | Local orchestrator + local artifact store (default stack) |
| Run on cloud compute | Cloud orchestrator + cloud artifact store + container registry + service connector |
| Track experiments | Above + experiment tracker |
| Monitor data quality | Above + data validator |
| Serve model predictions | Above + model deployer |
| Serve pipelines as APIs | Above + deployer |
| Full production MLOps | All of the above + alerter + image builder + log store |
