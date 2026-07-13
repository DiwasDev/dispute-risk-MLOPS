# ZenML Deployment Architectures

Reference for choosing and understanding ZenML deployment options. Use this when deciding how to deploy ZenML for a project or when configuring stacks against a specific deployment type.

## Deployment Options

### 1. Local (No Server)

The default when you `pip install zenml`. Everything runs on your machine: a local SQLite database stores pipeline metadata, artifacts land in a local directory, and no server process is needed. You interact purely through the CLI and Python SDK.

- **Command**: Just run `zenml init` and start defining pipelines.
- **Limitation**: No dashboard, no cloud orchestrators, no team sharing. Only local stack components work (local orchestrator, local artifact store).
- **Use when**: Learning ZenML, running tutorials, solo prototyping.

### 2. Local OSS Server

Run `zenml login --local` to spin up a FastAPI server on your machine. This gives you the ZenML dashboard and a client-server architecture, but still local.

- **What changes**: You get the ReactJS dashboard at localhost, and the client talks to the server over HTTP instead of directly reading SQLite.
- **Limitation**: Still single-machine. Remote orchestrators and cloud artifact stores will not work properly because the server is not network-accessible.
- **Use when**: Exploring the dashboard UI, testing server features before deploying remotely.

### 3. OSS Server (Self-Hosted, Remote)

Deploy the ZenML FastAPI server on your own infrastructure -- via Docker, Helm on Kubernetes, or HuggingFace Spaces. The server uses MySQL/PostgreSQL as its metadata store and is network-accessible.

**Components**:
- ZenML OSS Server (FastAPI)
- Metadata database (MySQL or PostgreSQL)
- OSS ReactJS Dashboard
- Secrets store (configurable)

**Deployment methods**:
- `docker run` or Docker Compose -- simplest for small teams.
- Helm chart on Kubernetes -- production-grade, scalable.
- HuggingFace Spaces -- quick demo/evaluation option.

**What this unlocks**: Remote orchestrators (Kubeflow, Airflow, SageMaker, Vertex AI), cloud artifact stores (S3, GCS, Azure Blob), team collaboration with shared stacks and pipeline history.

- **Use when**: Small-to-medium team, shared experiments, you want full control over infrastructure, no budget for Pro.

### 4. ZenML Pro SaaS

ZenML hosts the control plane, workspace server, dashboard, and metadata database. Your ML data artifacts stay in YOUR cloud (S3, GCS, etc.) -- only metadata flows to ZenML infrastructure.

**What ZenML hosts**: Control plane, Pro dashboard, workspace server, metadata DB, secrets store.
**What stays on your infra**: Artifact stores, orchestrators, model deployers, all actual ML data.

- **Advantage**: Zero server management. Sign up and go.
- **Trade-off**: Metadata (pipeline names, run info, metrics) is stored on ZenML infrastructure. Secrets/credentials for your cloud are managed by ZenML.
- **Use when**: You want managed infrastructure, fast onboarding, and metadata on ZenML's side is acceptable.

### 5. ZenML Pro Hybrid SaaS

ZenML hosts only the control plane (user management, auth, RBAC, workspace coordination). Everything else -- workspace servers, metadata DB, secrets, orchestrators, artifact stores -- runs on YOUR infrastructure.

- **Key property**: Workspaces communicate with the control plane through outbound-only connections. You can put them behind VPN/corporate firewalls.
- **Advantage**: Centralized user management without exposing data. All ML metadata and artifacts stay within your boundary.
- **Use when**: Enterprise with data sovereignty requirements, centralized MLOps team managing multiple business units, strict compliance needs.

### 6. ZenML Pro Self-Hosted

Everything runs on your infrastructure: control plane, workspaces, databases, secrets, dashboard. ZenML has zero access to your data. Air-gapped deployment is possible.

- **Use when**: Regulated industries, air-gapped environments, maximum security posture.
- **Setup**: Contact ZenML directly (`cloud@zenml.io`).

## Decision Framework

| Scenario | Recommended Deployment | Why |
|---|---|---|
| Solo developer learning ZenML | **Local (no server)** | Zero setup. `pip install zenml` and go. |
| Solo dev wanting the dashboard | **Local OSS Server** | `zenml login --local` gives you the UI without deploying anything. |
| Small team, shared experiments | **OSS Server (Docker/Helm)** | Free, full-featured, team can share stacks and view pipeline history. |
| Company, quick start, metadata on ZenML is OK | **Pro SaaS** | No infrastructure to manage. Sign up, connect your cloud, run pipelines. |
| Company, data sovereignty matters | **Pro Hybrid** | Control plane managed by ZenML, but all data/metadata stays on your infra. |
| Enterprise, air-gapped or regulated | **Pro Self-Hosted** | Full control. No data leaves your network. |

**Rule of thumb**: Start local, move to OSS Server when you need team collaboration or cloud orchestrators, move to Pro when you need RBAC/projects/audit or want managed infrastructure.

## How Deployment Affects Stacks

Your deployment type determines which stack components are usable:

**Local (no server)**:
- Orchestrator: `local` only
- Artifact store: `local` only
- No experiment trackers, model deployers, or step operators that require network access from a server

**OSS Server (remote)**:
- Orchestrator: `local`, `kubeflow`, `airflow`, `sagemaker`, `vertex`, `tekton`, `kubernetes`
- Artifact store: `local`, `s3`, `gcs`, `azure`
- Full stack component catalog available
- Team members share stacks and see each other's runs

**Pro (any variant)**:
- Everything OSS Server supports, plus:
- RBAC: role-based access control on stacks, pipelines, models
- Projects and workspaces for multi-team isolation
- Pipeline run snapshots and advanced lineage tracking
- Model Control Plane features (model stages, promotion workflows)
- Audit logging and compliance features

**Practical implication**: If you define a stack with a SageMaker orchestrator and S3 artifact store, it will not work against a local-only deployment. You need at minimum a remote OSS Server deployment, and the server needs network access (or service connectors) to reach those cloud resources.

## Service Connectors

Service Connectors are ZenML's abstraction for authenticating with external infrastructure. They decouple credentials from stack components so you configure auth once and reuse it across multiple components.

### Available Connector Types

| Connector | Resource Types | Auth Methods |
|---|---|---|
| **AWS** (`aws`) | S3 buckets, EKS clusters, ECR registries, generic AWS | implicit, secret-key, STS token, IAM role, session token, federation token |
| **GCP** (`gcp`) | GCS buckets, GKE clusters, GAR registries, generic GCP | implicit, user-account, service-account, OAuth2 token, impersonation |
| **Azure** (`azure`) | Blob containers, AKS clusters, ACR registries, generic Azure | implicit, service-principal, access-token |
| **Kubernetes** (`kubernetes`) | Kubernetes clusters | password, token |
| **Docker** (`docker`) | Docker registries | password |

### How They Work

1. **Register** a connector with credentials: `zenml service-connector register my-aws --type aws --auth-method secret-key --aws_access_key_id=... --aws_secret_access_key=...`
2. **Connect** a stack component to it: `zenml artifact-store connect my-s3-store --connector my-aws`
3. ZenML handles credential injection at runtime -- your pipeline code never sees raw credentials.

Connectors support **auto-configuration** (detect local cloud CLI credentials) and can generate **short-lived scoped tokens** for tighter security (e.g., STS tokens scoped to a specific S3 bucket).

### When to Use Service Connectors

- Any time a stack component needs to access cloud resources (S3, GCS, EKS, ECR, etc.)
- When you want to avoid baking credentials into stack component configs
- When multiple components need the same cloud credentials (register once, connect many)
- When running on a remote ZenML server -- connectors let the server broker auth for pipeline runs

### When You Do NOT Need Them

- Purely local development with local stack components
- If your orchestrator environment already has implicit credentials (e.g., an IAM role on an EC2 instance) and you set `auth-method: implicit`

## Data Location Summary

| Deployment | ML Metadata Location | ML Data/Artifacts Location | Secrets Location |
|---|---|---|---|
| Local | Local SQLite | Local filesystem | Local |
| OSS Server | Server's MySQL/PostgreSQL | Customer artifact store | Server's secret store |
| Pro SaaS | ZenML-hosted DB | Customer cloud | ZenML-managed |
| Pro Hybrid | Customer DB | Customer cloud | Customer-managed |
| Pro Self-Hosted | Customer DB | Customer cloud | Customer-managed |

In every deployment variant, actual ML data artifacts (datasets, trained models, logs) remain on customer infrastructure. The distinction is where metadata and secrets live.
