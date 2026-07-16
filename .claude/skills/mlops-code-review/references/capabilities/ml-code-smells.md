# ML Code Smells

Traditional code smells (long methods, God classes, feature envy) apply to ML code, but ML systems have their own category of structural problems that indicate deeper architectural issues. These smells were first cataloged by Sculley et al. in "Hidden Technical Debt in Machine Learning Systems" (2015) and expanded by Chip Huyen and others. They are not bugs -- the system works. They are structural problems that make the system increasingly expensive to change, debug, and trust. Recognizing these smells during code review prevents them from compounding into intractable technical debt.

## Glue Code Smell

ML systems become glue between libraries. The actual ML logic -- model definition, loss function, training loop -- is a tiny fraction of the codebase. The majority is data transformation glue: reading from one format, converting to another, reshaping, cleaning, joining, and passing to the next library.

**Detection**: If more than 50% of the code is data transformation plumbing between pandas, scikit-learn, XGBoost, and serving infrastructure, the system has glue code debt. The model itself might be 20 lines. The glue around it is 2000 lines.

**Why it hurts**: Glue code is fragile, hard to test, and tightly coupled to library APIs. When scikit-learn updates its API, every glue connection must be updated. When the data format changes, glue code throughout the pipeline breaks.

**Fix**: Build clean abstractions around external libraries. Wrap the data loading, preprocessing, and model training in interfaces that isolate library-specific code. When the library changes, only the wrapper changes.

## Pipeline Jungle

A pipeline jungle is a tangled web of data preparation steps that has grown organically over time. New features are added by splicing in new processing steps. Old steps are modified with conditional logic. The pipeline becomes a directed graph that no one fully understands.

**Detection**: Look for preprocessing code with deeply nested conditionals, multiple code paths for different feature types, and steps that depend on the output of non-adjacent steps. If drawing the data flow requires more than a simple linear diagram, it may be a jungle.

**Why it hurts**: Pipeline jungles make it impossible to understand the full transformation applied to any single feature. Adding a new feature requires understanding the entire pipeline to find the right insertion point. Testing is nearly impossible because the interactions between steps are not documented.

**Fix**: Rebuild the pipeline as a DAG with explicit, typed connections between steps. Each step has a clear input contract and output contract. The DAG structure is visible in code or configuration, not implicit in execution order.

## Dead Experimental Codepaths

ML development involves rapid experimentation. Branches are tried, models are compared, features are tested. The experimental code that "lost" often stays in the codebase, sometimes behind feature flags, sometimes as commented-out blocks, sometimes as alternate code paths with unreachable conditions.

**Detection**: Search for `if False:`, `if config.use_experimental:` with no configuration that enables it, commented-out model definitions, functions with names like `train_v2`, `preprocess_old`, `features_backup`. Check git blame -- if code has not been touched in months but is not part of the active pipeline, it is dead.

**Why it hurts**: Dead code confuses new team members who do not know which path is active. It creates a maintenance burden -- linting, type checking, and refactoring must account for code that is never executed. It can be accidentally activated by configuration changes.

**Fix**: Delete dead code. Git preserves history. If the experiment is valuable, document the results and the approach in experiment tracking, not in dead code.

## Feature Store vs Ad-Hoc Feature Computation

When features are computed ad-hoc -- scattered across training scripts, serving code, and notebook experiments -- the same feature is inevitably computed differently in different contexts. This is a structural smell that leads directly to training-serving skew.

**Detection**: Search for the same feature logic (e.g., "days since last purchase") implemented in multiple files. Check whether training and serving code import the same feature computation functions or implement them independently.

**Why it hurts**: Duplicate feature computation guarantees skew. When the training code updates a feature calculation, the serving code is often forgotten. Different implementations of "the same" feature can produce subtly different results due to rounding, null handling, or library differences.

**Fix**: Centralize feature definitions in a feature module or feature store. Both training and serving import from the same source. If a full feature store is overkill, a shared `features.py` module that both pipelines import is the minimum.

## Abstraction Debt

No standard interface for models, no standard interface for data sources, no standard interface for evaluation. Each model is used through its library-specific API. Each data source is loaded with bespoke code. Each evaluation script computes different metrics in different ways.

**Detection**: If adding a new model type requires modifying the training script, evaluation script, and serving code (rather than just implementing an interface), abstraction debt is present. If comparing two models requires writing custom comparison code because they do not share a common API, abstraction debt is present.

**Why it hurts**: Without abstractions, every new model or data source is a special case. The cost of experimentation increases linearly with codebase size. A/B testing and model comparison become ad-hoc rather than systematic.

**Fix**: Define minimal interfaces -- `ModelInterface` with `fit`, `predict`, `save`, `load`. `DataSource` with `load`, `validate`. `Evaluator` with `compute_metrics`. Wrap existing models and sources to conform.

## Plain-Old-Data Type Smell

Using raw dictionaries for configuration, hyperparameters, metrics, and model metadata instead of typed objects. `config["learning_rate"]` instead of `config.learning_rate`. `results["accuracy"]` instead of `results.accuracy`.

**Detection**: Functions that accept `dict` parameters and access string keys. Configuration loaded from YAML into a raw dictionary and passed through the pipeline as `dict`. Metric results stored as `dict[str, float]` without structure.

**Why it hurts**: No IDE autocomplete. No type checking. No validation. A typo in a key name (`config["learnin_rate"]`) is a silent KeyError at runtime, not a caught error at development time. In ML, where configuration determines model behavior, this is particularly dangerous.

**Fix**: Use dataclasses, Pydantic models, or NamedTuples for all structured data. `TrainingConfig`, `ModelMetrics`, `DataSchema`. Convert from raw dictionaries at the boundary (YAML parsing) and use typed objects internally.

## Multi-System Orchestration Smell

Training happens in Jupyter notebooks. The model is saved to a shared drive. The serving team picks it up and deploys it manually. Feature engineering is done in SQL in one system and replicated in Python in another. The ML system spans multiple codebases, languages, and teams with no shared source of truth.

**Detection**: If the answer to "where is the training code?" is "in a notebook on someone's laptop" or "in a different repo," this smell is present. If serving code reimplements preprocessing logic from the training codebase, it is present. If deployment requires manual steps documented in a wiki, it is present.

**Why it hurts**: No single source of truth means no single point of validation. Changes in one system are not automatically reflected in others. Debugging requires coordinating across systems, teams, and potentially languages.

**Fix**: Consolidate into a single repository (or at minimum, a monorepo with shared libraries). The training pipeline and serving pipeline should import the same preprocessing code. Deployment should be automated and triggered from the same repository that contains the training code.

## Undeclared Consumers

Downstream systems depend on the model's output format, prediction distribution, or feature importance without a formal contract. When the model is retrained and its outputs shift slightly, downstream systems break or produce incorrect results.

**Detection**: Check whether any system other than the primary application consumes model predictions. Dashboard queries that filter on model scores. Alert systems that threshold on prediction confidence. Analytics pipelines that aggregate model outputs. Each is an undeclared consumer.

**Why it hurts**: The model team does not know that retraining will break the analytics dashboard. The dashboard team does not know that model output distributions can shift between versions. The breakage is discovered days or weeks later.

**Fix**: Document all consumers of model outputs. Define a model output contract (prediction format, expected value range, distribution characteristics). Version the contract. Notify consumers when the model is retrained and validate the output against the contract before deployment.

## Correction Cascades

Model A's output is used as a feature for Model B. When Model A is retrained and its predictions shift, Model B's performance degrades because its input distribution has changed. This creates a cascade where improving one model silently degrades another.

**Detection**: Look for features derived from model predictions. If a feature is named `risk_score_from_model_a` or `predicted_churn_probability`, it creates a dependency between models. Trace the dependency graph -- if it has cycles or deep chains, correction cascades are likely.

**Why it hurts**: Cascades make it impossible to reason about model changes in isolation. Retraining Model A requires retraining and re-evaluating every downstream model. The debugging surface expands exponentially with cascade depth.

**Fix**: Minimize model-to-model dependencies. If they are necessary, pin the upstream model version that downstream models were trained with. Retrain downstream models explicitly when the upstream model changes. Monitor the interface between models (prediction distribution of Model A as seen by Model B) for drift.

## Feedback Loop Smell

The model's predictions influence the data it will be trained on in the future. A recommendation model that promotes certain items causes those items to get more engagement, which reinforces the model's preference for those items. The model converges on a narrow subset of the output space.

**Detection**: Trace whether model predictions influence future training data. If the model decides what data is collected (recommendations, content ranking, ad selection), a direct feedback loop exists. If the model influences user behavior that is then measured as labels, an indirect feedback loop exists.

**Why it hurts**: Feedback loops cause models to become increasingly confident and increasingly narrow. Exploration decreases. Minority segments get less data and worse predictions, which reduces their engagement, which reduces their data further.

**Fix**: Add randomization (explore/exploit strategies). Monitor output diversity over time. Retrain on data that includes counterfactual examples. Alert when the prediction distribution narrows significantly.

## When to Use This

- During architectural review of an ML system -- look for structural smells before they compound.
- When a codebase feels "hard to change" despite being relatively small.
- When debugging takes disproportionately long because of unclear data flow.
- When adding a new feature or model type requires changes in many files.
- When production incidents trace back to subtle interactions between components.

## Red Flags to Watch For

- More than 50% of code is data transformation glue between libraries.
- Preprocessing logic duplicated between training and serving codebases.
- Feature computation code that exists in more than one file.
- Configuration and hyperparameters stored in raw dictionaries throughout the pipeline.
- Functions named `train_v2`, `preprocess_old`, or dead code behind unreachable conditions.
- Model predictions used as features for other models without explicit versioning.
- No standard interface for models -- each model type has bespoke training and evaluation code.
- Deployment requires manual steps or copying artifacts between systems.
- No documentation of which systems consume model outputs.
- Pipeline DAG that cannot be drawn from reading the code.
