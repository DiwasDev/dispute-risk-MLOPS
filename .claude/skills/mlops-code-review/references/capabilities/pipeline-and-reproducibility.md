# Pipeline Quality and Reproducibility Review

For ML project structure and coding practices, see `../../mlops-tabular/references/capabilities/coding-practices.md`. This file extends that foundation with review checklists for pipeline quality and reproducibility.

The coding practices reference covers project structure, testing, CI/CD, and configuration management. This reference focuses on what a code reviewer should verify when reviewing pipeline code: whether preprocessing is properly bundled, whether experiments are reproducible, whether configuration is externalized, and whether the pipeline produces identical results when run twice with the same inputs. These are the mechanical requirements that separate a prototype from a production pipeline.

## sklearn.Pipeline Review

scikit-learn's `Pipeline` is the most important tool for enforcing preprocessing correctness. It bundles preprocessing steps with the model into a single object that applies transforms in order and prevents leakage by design.

### Is Preprocessing Bundled with the Model?

**What to look for**: Preprocessing steps (scaling, encoding, imputation) that happen outside the Pipeline object. If `StandardScaler` is applied to the data before it enters the Pipeline, the scaler is not serialized with the model. At serving time, the serving code must replicate the scaling -- a parity risk.

**Correct pattern**: All preprocessing steps are inside the Pipeline. The Pipeline is fit on training data and the fitted Pipeline is serialized. At serving time, the same Pipeline object handles both preprocessing and prediction.

**Common violation**: Preprocessing in a separate function that is called before `pipeline.fit(X, y)`. The Pipeline only contains the model. The preprocessing function must be replicated in serving code.

### Are All Transforms Inside the Pipeline?

**What to look for**: Feature engineering or transformation steps that happen before data enters the Pipeline. Common examples: log transformations applied to raw data, feature crosses computed before Pipeline input, custom encodings applied as a preprocessing function.

**Review heuristic**: Trace the data path from raw input to `pipeline.fit(X, y)`. Every transformation applied to `X` before it enters the pipeline is a potential parity risk. Each must either be moved inside the Pipeline (as a custom transformer) or be guaranteed to be applied identically at serving time.

**Custom transformers**: For transformations that do not have a scikit-learn equivalent, write a custom transformer (inheriting from `BaseEstimator`, `TransformerMixin`) and include it in the Pipeline. This ensures the transform is serialized and applied automatically at prediction time.

### ColumnTransformer Usage

**What to look for**: Different transformations applied to different column types (numerical vs categorical) should use `ColumnTransformer` inside the Pipeline, not manual column selection outside it.

**Correct pattern**: `ColumnTransformer` with named transformers for each column group, composed into the Pipeline. Column names are explicit, not positional indices. The transformer handles column selection, transformation, and recombination.

**Common violation**: Manual `df[numerical_cols]` and `df[categorical_cols]` selection outside the Pipeline, with separate scalers and encoders applied independently. This scatters preprocessing logic across multiple code locations.

## Experiment Tracking Hygiene

Reproducibility requires that every experiment is fully described by its tracked metadata. A reviewer should verify that the four reproducibility elements are logged.

### The Four Reproducibility Elements

Every experiment run must log:

1. **Code version**: The exact git commit hash. Not the branch name (branches move), not "latest" (meaningless retroactively), but the full SHA.
2. **Data version**: A snapshot identifier for the training data. A hash of the data file, a timestamp of the data pull, a version tag in the data store, or a DVC hash. The data must be retrievable from this identifier.
3. **Configuration**: All hyperparameters, feature lists, preprocessing settings, and environment-specific overrides. The full configuration, not just the parameters that were changed from defaults.
4. **Environment**: Python version, library versions (ideally a complete pip freeze or lockfile), and system information (CPU/GPU, memory). Library version differences between runs can change model outputs.

**Review check**: If any of the four elements is missing from the experiment tracking code, the experiment is not reproducible. Flag it.

### Git Commit Hash Recording

**What to look for**: Explicit logging of the git commit hash at the start of every training run. This should be automatic, not manual.

**Pattern**: `subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()` at the start of training, logged to the experiment tracker. Or use the experiment tracking library's built-in git integration if available (MLflow logs git hash automatically when configured).

**Common violation**: No git hash logged. The team relies on "I think I ran it from the main branch" -- this is not reproducible.

### Dirty State Detection

**What to look for**: Check whether the working directory has uncommitted changes at training time. A model trained from a dirty git state cannot be reproduced from the commit hash alone.

**Pattern**: Check `git status --porcelain` at training start. If non-empty, log a warning and record that the state was dirty. Some teams block training on dirty state; at minimum, log it.

## Config Management Review

### Are Hyperparameters in Config Files?

**What to look for**: Hyperparameters hardcoded in Python source files. `learning_rate = 0.01` in `train.py` instead of loaded from a configuration file.

**Why it matters**: Hardcoded hyperparameters mean changing them requires a code change. Code changes require review, CI, and deployment. This slows experimentation and makes it harder to track which parameters produced which results.

**Correct pattern**: Hyperparameters in YAML, TOML, or a Pydantic config object. The training script loads the configuration at runtime. Different experiments use different config files with the same code.

### Configuration Completeness

**What to look for**: Partial externalization -- some parameters in config, others hardcoded. A config file that sets `learning_rate` and `n_estimators` but hardcodes `max_depth=6` in the source code. The hardcoded value is invisible to experiment tracking.

**Review heuristic**: Search the training code for literal numbers that represent hyperparameters. Any literal that affects model behavior (threshold, tree depth, regularization strength, batch size) should be in the configuration.

### Environment-Specific Overrides

**What to look for**: Configuration that handles environment differences (local vs staging vs production) through code branches (`if env == "prod"`) instead of configuration hierarchy.

**Correct pattern**: Base config with defaults, environment-specific config files that override specific values, CLI or environment variable overrides for ad-hoc runs. No if/else for environment in source code.

## Random Seed Management

### Comprehensive Seeding

**What to look for**: Random seed set for the model but not for data splitting, shuffling, or initialization. Partial seeding creates partial reproducibility -- some parts of the pipeline are deterministic, others are not.

**What must be seeded**: numpy random state, Python random module, data splitting (random_state parameter), model initialization (random_state or seed parameter), any stochastic preprocessing (random oversampling, data augmentation).

**Pattern**: Define a single seed value in configuration. Pass it explicitly to every component that uses randomness. Do not rely on global seed setting (`np.random.seed()`) -- it is fragile and does not work across libraries.

### Seed Propagation

**What to look for**: A seed defined at the top level but not propagated to all pipeline steps. The training script sets `SEED = 42` but passes it only to the model, not to `train_test_split` or `StratifiedKFold`.

**Review heuristic**: Search for all uses of `random_state`, `seed`, `random`, and `shuffle` in the pipeline. Each must either use the configured seed or explicitly document why randomness is intentional.

## Data Versioning Review

**What to look for**: Training data referenced by mutable paths (`/data/latest/train.csv`) instead of versioned snapshots. If the data at that path changes, rerunning the pipeline produces a different model from the "same" code and configuration.

**Correct patterns**: Immutable data snapshots with date or hash in the path (`/data/2024-01-15/train.csv`). DVC-tracked data files with version hashes. Data stored in a versioned data lake with partition keys. The experiment tracker records which data version was used.

**Common violation**: Data loaded from a database query with no snapshot mechanism. The query returns different results tomorrow. Without a data snapshot, the experiment is unreproducible.

## Artifact Naming Conventions

**What to look for**: Model artifacts saved with generic names (`model.pkl`, `scaler.joblib`) that overwrite previous versions.

**Correct pattern**: Artifact names include version information: model name, timestamp, git hash, or experiment ID. `model_v3_2024-01-15_abc1234.pkl` or organized by experiment ID in a directory structure. The model registry maps human-readable versions to artifact paths.

**Metadata alongside artifacts**: Every saved artifact should have accompanying metadata (JSON or YAML) recording the configuration, training data version, metrics, and code version that produced it.

## Pipeline Idempotency Checks

**What to look for**: Pipeline runs that produce different results when run twice with identical inputs and configuration.

**Sources of non-idempotency**: Unseeded randomness, data loaded from mutable sources, timestamps embedded in computations, API calls to external services, hardware-dependent numerical precision (GPU vs CPU).

**Review check**: Is there a test that runs the pipeline twice with the same seed and asserts identical outputs? If not, non-determinism may exist and go undetected.

**Acceptable non-determinism**: Some ML operations are inherently non-deterministic (GPU training, certain optimizers). Document these cases explicitly. For everything else, enforce determinism.

## When to Use This

- When reviewing ML pipeline code for production readiness.
- When investigating why an experiment cannot be reproduced.
- When setting up a new ML project's pipeline infrastructure.
- When reviewing artifact management and experiment tracking code.
- When auditing an existing pipeline for reproducibility gaps.

## Red Flags to Watch For

- Preprocessing steps outside the sklearn.Pipeline that must be replicated at serving time.
- No git commit hash logged in experiment tracking.
- Hyperparameters hardcoded in source files instead of loaded from configuration.
- Random seed set for the model but not for data splitting or shuffling.
- Training data referenced by mutable paths with no versioning.
- Model artifacts saved with generic names that overwrite previous versions.
- No test that verifies pipeline idempotency (same input, same output).
- Experiment tracking missing any of the four reproducibility elements.
- Configuration partially externalized -- some parameters in config, others hardcoded.
- No dirty-state check at training time -- models trained from uncommitted code.
