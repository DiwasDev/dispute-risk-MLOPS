# Experiment Tracking & Reproducibility

## Why Experiments Must Be Tracked

A notebook proves an idea once; a pipeline delivers it every day. The gap between them is reproducibility -- the ability to take last week's result and get the same score again. Without tracking, teams lose knowledge: which hyperparameters produced the best model, which data snapshot was used, which preprocessing logic was applied. Experiment tracking is the institutional memory of an ML team.

Reproducibility requires fixing four things simultaneously -- like a recipe where all four ingredients must be exact:

1. **Data snapshot** -- never train on "today's data." Take a dated snapshot, name it descriptively (e.g., `customers_2025_q1`), and record which snapshot each experiment used.
2. **Library versions** -- pin exact versions (e.g., `scikit-learn==1.2.2`), not ranges. Rebuild the environment image only on purpose.
3. **Code version** -- the exact git commit hash, not "the latest." Tag production-deployed code.
4. **Configuration** -- paths, feature flags, seeds, thresholds, hyperparameters in a config file separate from code. Different configs yield different models without code changes.

If any of these four floats, results drift and debugging becomes guesswork. When all four are fixed, you can reproduce any past result.

## The Reproducibility Recipe

Think of reproducibility like a baking recipe. Same ingredients plus same instructions equals same cake.

**Ingredients** are data snapshots and library versions. Never train silently on "today's data." Take a dated snapshot, name it descriptively (e.g., customers_2025_q1), and record which snapshot each experiment used. Pin exact library versions in a requirements file or container image. Rebuild the image only on purpose so yesterday's run and today's run match.

**Instructions** are code and configuration. The code should be versioned in git. The configuration -- paths, feature flags, seeds, thresholds, hyperparameters -- should live in a small config file separate from code. Different configs yield different models without code changes, and each config is recorded as part of the experiment.

When all four are fixed, you can reproduce any past result. When any one floats, you cannot.

## What an Experiment Record Contains

Each tracked experiment run should record:

- **Run ID:** a unique identifier for this specific execution.
- **Git commit:** the exact code version used.
- **Data snapshot ID:** which version of the data was consumed.
- **Configuration:** all hyperparameters, feature flags, random seeds, thresholds, file paths.
- **Metrics:** every evaluation metric computed (precision, recall, F1, MAE, loss curves, etc.).
- **Artifact locations:** paths to the trained model file, fitted preprocessors, evaluation reports, plots.
- **Environment:** library versions, container image tag, hardware used.
- **Timestamp and duration:** when the run started, how long it took.

This record enables effortless retraining (rerun with the same config and data) and comparison (which of these 15 runs performed best, and why?).

## Hyperparameter Management

Hyperparameters should never be hardcoded inside training scripts. Extract them into a configuration file or configuration object that gets logged with every run. This practice provides three benefits:

**Traceability:** you can always answer "what learning rate produced this model?" by looking at the experiment record.

**Reproducibility:** re-running with the same config file produces the same model.

**Experiment velocity:** changing one parameter and re-running is trivial, and the tracking system records both runs for comparison.

Organize hyperparameters into logical groups: model architecture parameters (depth, width, regularization), training parameters (learning rate, batch size, epochs, early stopping patience), and data parameters (train/test split ratio, sampling strategy, feature list).

## Baselines: The Floor You Must Beat

Every project needs a baseline -- the simplest thing that sets a performance floor. Baselines serve as the reference point for all experiments.

For classification: predict the majority class, or use a simple rule (e.g., block if sender is blacklisted, else allow).

For regression: predict the mean or median value per category.

For ranking: use the existing heuristic score (e.g., keyword overlap plus freshness bonus).

The baseline should be the first tracked experiment. Keep it as the permanent reference run. Every subsequent experiment is measured against it. A model that cannot beat the baseline should not ship.

Build a baseline scoreboard: a small, persistent set of numbers tracked every run. Include one north-star metric, two or three guardrail metrics (error rate, latency), and the relevant model metrics (precision, recall, MAE). Update with every change and keep the first model as the reference run.

## Metrics Logging

Log metrics at multiple granularities:

**Summary metrics** are the final numbers: overall precision, recall, F1, MAE. These are what you compare across runs.

**Per-slice metrics** break performance down by important segments: by user cohort, by category, by time period. A model can have great overall precision but terrible precision for a minority segment. Slice metrics catch this.

**Training curves** track loss and validation metrics across epochs or iterations. They reveal overfitting (training loss drops while validation loss rises), underfitting (both stay high), and training instability.

**Evaluation artifacts** like confusion matrices, precision-recall curves, calibration plots, and error distributions provide deeper insight than single numbers. Save them as artifacts attached to the run.

## The Experiment Lifecycle

A disciplined experiment workflow follows this pattern:

1. **Hypothesis:** state what you expect to improve and why. "Adding the heuristic score as a feature should improve recall because it captures domain knowledge."
2. **Configure:** create or modify the config file with the change. Change one thing at a time.
3. **Run:** execute the pipeline. The tracking system automatically records the run.
4. **Compare:** look at the new run's metrics against the baseline and the previous best run. Check both the north-star metric and guardrails.
5. **Decide:** if the run improves the north-star without breaking guardrails, it becomes the new candidate. If not, record why and move on.
6. **Promote or park:** winning experiments get promoted toward production (validation with golden set, A/B test). Losing experiments stay in the tracking log as knowledge for the team.

## Artifacts and the Artifact Store

Artifacts are the files output by one pipeline step for the next: cleaned datasets, fitted encoders and scalers, feature statistics, trained models, evaluation reports and plots. Store them in a central location with predictable paths (not scattered across notebook outputs).

An artifact store provides reproducibility without searching through notebooks. When you need to debug a production model, you can pull the exact preprocessing artifacts and model file that produced it.

## The Model Registry

A model registry is where trained models get labeled with lifecycle stages: staging, production, archived. Think of it as an app store for models.

**Promotion rules:** a model moves from staging to production only when metrics and checks pass. This includes offline metric improvement over the current production model, golden-set parity between training and serving, and guardrail metrics within bounds.

**Demotion rules:** if monitoring detects problems (drift, skew, metric degradation), the model can be demoted and the previous version restored.

**Lineage:** the registry records which experiment run produced each model, linking back to the exact code, data, config, and metrics.

## Pipeline Structure for Reproducibility

The minimum viable pipeline has these stages, each producing artifacts for the next:

1. **Data intake:** read from a known path or table. Record the data snapshot ID.
2. **Validation:** check schema and value ranges. Fail fast if data is malformed.
3. **Transformation:** build features. Save fitted transformers as artifacts.
4. **Training:** train the model. Save the model file as an artifact.
5. **Evaluation:** produce a metrics report. Compare to baseline.
6. **Packaging:** bundle the model and preprocessing artifacts for serving.

Each step is a discrete unit. If step 4 fails, you can fix it and rerun from step 4 using the artifacts from steps 1-3, rather than rerunning everything.

## Versioning Everything That Matters

Version code (git), data snapshots (named and dated), configuration (stored with each run), models (registry), and the environment (container image tag or pinned requirements).

Drift occurs if any of these floats. Versioned together, they answer the question: "which exact code and data produced this prediction?"

## Testing for ML Pipelines

- **Unit tests:** schema checks, range checks on individual features, transformation logic correctness.
- **Flow tests:** a tiny end-to-end mini job on a small data sample. If the mini job passes, you have confidence the full job will succeed. If it fails, you catch the error before wasting compute.
- **Parity tests:** golden-set scoring that confirms training and serving produce identical outputs.

## When to Use This

- You are starting a new ML project and need to set up infrastructure before training your first model.
- You have multiple team members running experiments and results are getting lost or confused.
- You need to debug why a retrained model performs differently from the previous version.
- You are preparing to hand off a model to a production team and need to document what was done.
- You are transitioning from notebook-based experimentation to a structured pipeline.

## Red Flags to Watch For

- Experiments are run in notebooks with no record of hyperparameters or data versions used.
- The team cannot reproduce last month's best model because the data or code has changed.
- Hyperparameters are hardcoded in training scripts rather than externalized in config files.
- There is no baseline to compare against -- the team does not know if a new model is actually better.
- Model files are saved locally with no registry or lifecycle management.
- Preprocessing artifacts (scalers, encoders) are not saved, so serving must recompute them.
- The team relies on "just rerun the notebook" for reproducibility but different team members get different results.
- No mini end-to-end test exists, so pipeline failures are only discovered after expensive full runs.
- Configuration changes are made in code commits rather than in tracked config files, making it hard to isolate the effect of a single change.
