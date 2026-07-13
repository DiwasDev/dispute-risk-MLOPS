# Six-Week MLOps Build Timeline

A practical timeline for building a production-grade MLOps system for tabular supervised learning, assuming a single engineer with existing labeled data. Scale up or down based on team size and complexity.

## Week 1: Problem Statement + Baseline

**Goal:** Clarity on what you're building and a floor to beat.

**Deliverables:**
- `problem_statement.md` with business context, ML formulation, primary metric, guardrails, and success criteria
- Baseline model (logistic regression or decision tree) with honest metrics
- No preprocessing tricks, no hyperparameter tuning -- just the simplest model on the data as-is

**Why this week matters:** The problem statement prevents building the wrong thing. The baseline prevents shipping a model that is worse than "predict the majority class." Everything after this week is measured against this baseline.

## Week 2: Reproducible Training Pipeline

**Goal:** Anyone can run the pipeline and get the same result.

**Deliverables:**
- Training pipeline with discrete steps: data loading, preprocessing, training, evaluation
- Experiment tracking (MLflow or equivalent) logging metrics, parameters, and artifacts per run
- Artifact store for trained models and fitted preprocessors
- Pinned library versions in pyproject.toml or requirements.txt

**Why this week matters:** Reproducibility is the foundation. Without it, you cannot compare experiments, debug regressions, or retrain reliably.

## Week 3: Data Validation + Feature Preprocessing + Parity

**Goal:** Bad data fails fast, and training and serving see the same features.

**Deliverables:**
- Schema validation on data ingestion (column presence, types, ranges, null rates)
- Feature preprocessing bundled in sklearn.Pipeline (scaling, encoding, imputation in one serializable object)
- Golden-set parity tests: 50-100 fixed examples with known outputs, verified on every pipeline run
- Data quality metrics logged per run (completeness, distribution stability, volume)

**Why this week matters:** Data quality issues are the most common root cause of model failures. Training-serving skew is the single most common silent failure in production ML. Both are addressed this week.

## Week 4: Evaluation Framework + Model Registry

**Goal:** You know exactly how good the model is, for every segment, with uncertainty quantified.

**Deliverables:**
- Slice-level evaluation (metrics broken down by business-relevant segments)
- Confidence intervals via bootstrapping (not just point estimates)
- Model registry with version tracking and promotion stages (staging, production, archived)
- Comparison framework: new model vs current production model on the same evaluation set

**Why this week matters:** Global metrics hide segment failures. A single number without uncertainty is not evidence. The registry enables rollback -- the most important safety feature in production ML.

## Week 5: Inference Pipeline + Shadow Testing

**Goal:** Predictions reach users safely.

**Deliverables:**
- Inference pipeline (batch or real-time) loading the production model from the registry
- Shadow deployment: new model runs alongside current model, predictions logged but not served
- Comparison report: prediction distributions, disagreement rates, eventual accuracy on labeled data
- Rollback procedure tested: can revert to previous model version in under 5 minutes

**Why this week matters:** Shadow testing catches problems before users see them. Tested rollback means you can ship with confidence -- if something goes wrong, recovery is fast.

## Week 6: Monitoring + Drift Detection

**Goal:** The system tells you when something is wrong, before users notice.

**Deliverables:**
- Feature distribution monitoring against training baselines
- Prediction distribution tracking (histogram shape over time)
- Drift detection with statistical tests (PSI, KS test) and actionable thresholds
- Alert routing: who gets notified, at what severity, with what context
- Dashboard showing all four monitoring layers: data health, model metrics, product metrics, business outcomes

**Why this week matters:** Models degrade silently. Without monitoring, you discover problems when a stakeholder calls to ask why outcomes are getting worse. Monitoring converts invisible degradation into early, actionable alerts.

## After Week 6: Iterate

The six-week system is Level 1-2 maturity. From here:

- **Automated retraining** (Level 3): add only when drift frequency or data velocity justifies it. Gate promotion on automated evaluation.
- **CI/CD for ML**: automated testing on pipeline changes, automated promotion with quality gates.
- **Advanced deployment**: canary rollouts, A/B testing for business impact measurement.
- **Team scaling**: runbooks, incident response playbooks, on-call rotation.

Do not build Level 3 infrastructure until Level 1-2 is stable and you have evidence that manual retraining is too slow. Premature automation adds complexity without proportional value.
