# Model Registry and Promotion

A model registry is the curated catalog of trusted models with clear lifecycle labels. It bridges the gap between experiment tracking (where many models are tried) and production serving (where exactly one model must be reliable). Without a registry, teams lose track of what is deployed, why, and how to roll back.

## Why a Registry Matters

- A winning notebook model is not a product. It needs repeatability, comparison, shipping, and rollback.
- Experiment tracking records every choice and result. The registry is the organized shelf of trusted, vetted models with clear lifecycle status.
- Together they enable reliable, upgradeable products. Separately, experiment tracking produces chaos and the registry has nothing to curate.

## Experiment Tracking: The Foundation

Before models reach the registry, experiment tracking captures everything about each attempt.

### What an Experiment Run Records

A run is a single attempt to train or evaluate a model with specific inputs and choices. Every run must record:

- **Identity**: Human-readable name (e.g., studyrec_lr0p05_q3_2025w37) plus a unique, unchanging machine ID.
- **Data snapshot**: Path to the exact dataset version and date.
- **Code version**: Git commit or version tag.
- **Configuration**: Full parameter file (hyperparameters, data parameters, feature flags) saved with the run.
- **Environment**: Random seed, library versions, hardware info.
- **Metrics**: Full metrics report with definitions. Not just the primary metric but all relevant metrics including slice-level breakdowns.
- **Artifacts**: Paths to model files, preprocessor objects, encoders, scalers, reports, and plots. Stored with stable paths and checksums.

### Lineage: From Prediction to Source

Lineage links every prediction back to the exact model version, data snapshot, code commit, and artifacts that produced it. Without lineage you guess; with lineage you trust. Lineage enables auditing, recreation of decisions, and debugging of production issues.

### Reproducibility

The gold standard for experiment tracking quality: can you reproduce a strong run on another machine using only the run record? If not, add fields until an exact match is guaranteed. Make this a habit for every project.

### Comparing Runs Honestly

- Sort by primary metric, filter by date or dataset snapshot.
- View metric deltas per slice, not just global improvements.
- Inspect parameters and artifacts before deciding.
- Choose models based on cost, stability, and slice safety, not only the highest metric.

## The Model Registry

### Core Concepts

A model registry is a curated catalog that stores:

- **Model versions**: Each registered model has numbered versions, each pointing to specific artifacts.
- **Tags and labels**: Semantic tags (e.g., "low-latency", "high-recall") and lifecycle stage labels.
- **Metadata**: Metrics, lineage pointers, approval records, training details, resource requirements.
- **Lifecycle stages**: The current state of each version in the promotion pipeline.

### Stage Management

Models progress through defined stages. A typical pipeline:

1. **Experimental**: Run is logged in experiment tracker. Not yet in the registry.
2. **Registered/Candidate**: Model passes offline evaluation criteria and is added to the registry. Metrics, lineage, and artifacts are locked.
3. **Staging**: Model is deployed to a staging environment for canary or shadow testing. Business metrics and guardrails are validated against production traffic.
4. **Production**: Model is serving live traffic. This is the single source of truth for what version is live.
5. **Archived**: Model is retired from active use but preserved for audit, comparison, or emergency rollback.

### Versioning and Tagging

- Every model version is immutable once registered. Changes create new versions.
- Use semantic version numbers or timestamps. Never overwrite a version.
- Tags are mutable metadata that can be updated (e.g., moving a "champion" tag from one version to another).
- Store artifact checksums to detect tampering or corruption.

## Promotion Workflows

### Promotion Criteria

Promotion from one stage to the next requires passing explicit, checkable criteria. Write criteria as simple statements that a system can enforce:

**Experimental to Registered:**
- Run is complete (not crashed or partial).
- All required metadata fields are populated.
- Metrics are computed on the standard test set.
- Artifacts are stored with valid checksums.

**Registered to Staging:**
- Offline metrics beat the current production baseline on primary metric.
- Slice-level metrics show no regression on critical segments.
- Golden input tests pass (training-serving parity confirmed).
- Data validation clean (no schema violations, drift within bounds).
- Model card is filled out.

**Staging to Production:**
- Canary or shadow testing shows no business metric regression.
- Guardrail metrics (latency, error rate) within SLA bounds.
- Prediction distribution is stable and matches offline expectations.
- Approval from designated reviewer (human gate for high-stakes models).

### Approval Processes

- Define who can approve promotion at each stage.
- For low-risk models (routine retrains with minor improvements), automated promotion with gate checks is appropriate.
- For high-risk models (new architectures, new features, new domains), require human approval after reviewing metrics, model card, and canary results.
- Log every approval decision with the approver identity and rationale.

### Quality Gates

Gates are binary: failure disables the promotion button. They are not suggestions.

- Promote only if data validation is clean and drift is within bounds.
- Golden input tests must pass.
- Canary slice must be healthy.
- Gates enforce discipline that subjective review cannot.

## Model Cards

Every registered model should have a model card that makes its behavior understandable:

- Use cases and intended scope.
- Training data coverage and known limitations.
- Key metrics by slice and resource footprint (latency, memory).
- Sensitive features and known failure patterns.
- Ethical and safety considerations.
- Owner contact and links to dashboards and runbooks.

Model cards are living documents updated when the model or its context changes.

## Rollback

Rollback is a first-class registry operation, not an emergency hack.

- Rollback promotes the last stable model version and its artifacts with one action.
- The rollback entry in the change log includes an explanation of why.
- After rollback, an investigation task is created. Rollback first, debug second.
- Speed and clarity protect users. The previous model must always be warm and ready.

## Governance and Compliance

### Audit Trail

The registry provides a complete audit trail:

- Who registered each version and when.
- What criteria were checked at each promotion.
- Who approved the promotion and their rationale.
- When each version was live in production and when it was retired.
- Full lineage from prediction back to training data.

### Retention and Archival

- Keep all production versions indefinitely for audit purposes.
- Archive experimental versions after a defined retention period.
- Ensure archived models can be restored if needed for comparison or emergency rollback.

### Multi-Model Coordination

- When multiple models serve different parts of a product, the registry tracks which combination of versions is deployed.
- Version the ensemble or pipeline as a whole, not just individual models.
- Coordinate rollbacks across dependent models.

## When to Use This

- **Starting any ML project**: Set up experiment tracking from the first training run. Add a registry before the first production deployment.
- **Preparing for production launch**: Ensure promotion criteria are written, gates are automated, and the rollback path is tested.
- **Routine model updates**: Use the promotion workflow to move from registered to staging to production with gate checks at each step.
- **After an incident**: Verify registry rollback works in under five minutes. Update promotion criteria if the incident revealed a gap.
- **Compliance or audit review**: The registry provides the complete record of what was deployed, when, and why.

## Red Flags to Watch For

- **No registry, just files on disk**: "The model is in /home/alice/best_model_v3_final.pkl" is not a registry. It is a liability.
- **Manual promotion without criteria**: If promotion is "someone copies the file to the production server," you have no safety net.
- **Mutable versions**: If a registered model version can be silently overwritten, you lose reproducibility and audit trail.
- **No model cards**: If nobody can explain what a production model does, its limits, and its failure modes, the team is flying blind.
- **Rollback not tested**: If you have never practiced rollback, it will fail when you need it most.
- **Missing lineage**: If you cannot trace a production prediction back to its training data and code, debugging and auditing are impossible.
- **Promotion without slice evaluation**: Global metric improvements that mask segment regressions will hurt users in those segments.
- **No human gate for high-risk models**: Fully automated promotion is fine for routine retrains but dangerous for novel model changes in high-stakes domains.
