# Coding Practices for ML Projects

ML code has unique challenges compared to traditional software: it depends on data that changes, produces artifacts (models, scalers, encoders) that must be versioned, and must be reproducible across environments. Good coding practices make the difference between an ML project that can be maintained and iterated on, and one that becomes an unmaintainable notebook graveyard. These practices apply to the productionizing, validating, refining, and sharing phases of the ML development lifecycle.

## ML Project Structure

A well-structured ML project separates concerns into distinct layers. The standard pattern for tabular ML projects uses four primary directories:

### Source Code (src/)

Contains all production logic: data loading, feature engineering, model training, evaluation, and prediction. Each concern lives in its own module. A data loader module handles reading and splitting data. A feature engineering module handles transformations and encoding. A model trainer module handles fitting. An evaluator module handles metrics computation. This separation means each module can be tested independently, swapped out, and versioned separately.

### Steps and Pipelines

Steps are the atomic units of an ML workflow -- each step performs one operation (load data, engineer features, train model, evaluate). Pipelines compose steps into a directed acyclic graph (DAG) that defines the execution order. This pattern enforces clear data contracts between stages: each step declares its inputs and outputs with type annotations, making dependencies explicit rather than implicit.

The key constraint: logic belongs inside steps, not at the pipeline level. Pipeline definitions should be declarative (which steps run in what order), not imperative (no if/else based on step outputs at the pipeline level). Conditional logic goes inside steps where runtime values are available as actual Python objects.

### Configuration (configs/)

All hyperparameters, file paths, feature lists, and environment settings belong in configuration files (YAML, TOML, or dataclass-based config objects), not hardcoded in source code. This enables:

- Running the same code with different parameters without editing source files.
- Tracking which configuration produced which results (experiment reproducibility).
- Environment-specific overrides (local development uses small data and few epochs; production uses full data).

Configuration should be hierarchical: base config with defaults, environment-specific overrides, and run-specific overrides. Use a configuration library (Pydantic, Hydra, or simple dataclasses) rather than raw dictionaries to get validation and type safety.

### Tests (tests/)

ML projects need three kinds of tests:

- **Unit tests**: Test individual functions -- does the feature engineering function produce the expected output for a known input? Does the evaluation function compute the correct metric?
- **Integration tests**: Test the pipeline end-to-end on a small synthetic dataset. Does data flow correctly from loading through prediction? Do artifact shapes match expectations?
- **Data tests**: Validate assumptions about incoming data -- column types, value ranges, missing rates, cardinality. These catch upstream data pipeline changes before they silently corrupt model training.

## Testing ML Code

Testing ML code is harder than testing traditional software because outputs are probabilistic and depend on data. Apply these principles:

- **Test preprocessing deterministically**: Given a fixed input DataFrame, preprocessing functions should produce an exact expected output. These tests are fully deterministic and should be fast.
- **Test model training with smoke tests**: Train on a tiny dataset (10-50 rows) for one epoch or one tree. Verify the model object is created, has the expected type, and can produce predictions. Do not assert specific metric values -- they are meaningless on tiny data.
- **Test evaluation functions with known inputs**: Create synthetic predictions and labels where you know the correct metric values. Verify the evaluation function computes them correctly.
- **Test data contracts**: If a step expects a DataFrame with columns ["age", "income", "risk_score"], write a test that passes a DataFrame missing a column and verifies the step fails with a clear error.
- **Use fixtures for reproducibility**: Pin random seeds in test fixtures. Use small, deterministic datasets stored as CSV files or generated programmatically.

## Type Hints and Linting

Type hints serve double duty in ML code: they document expected data shapes for humans and enable static analysis tools to catch errors before runtime.

- Annotate all function signatures with input and output types. For ML steps, use framework-specific annotation patterns (e.g., Annotated types for artifact naming).
- Use specific types rather than generic ones: pd.DataFrame rather than Any, ClassifierMixin rather than object.
- Configure a linter (ruff is the current standard -- fast, comprehensive, replaces flake8/isort/black) to enforce consistent style, catch unused imports, and flag common errors.
- Use a type checker (mypy or pyright) at least in non-strict mode to catch type mismatches.
- Format code automatically (ruff format or black) to eliminate style debates. Configure in pyproject.toml and run on save.

## CI/CD for ML

Continuous integration for ML projects must handle both code quality and model quality:

### Code Quality Pipeline (runs on every commit)

- Linting and formatting checks.
- Type checking.
- Unit and integration tests.
- Security scanning for dependencies (pip-audit or safety).

### Model Quality Pipeline (runs on model-related changes)

- Training pipeline execution on a small dataset to verify the pipeline runs end-to-end.
- Metric validation: trained model meets minimum performance thresholds on a held-out validation set.
- Data quality validation: input data meets schema and statistical expectations.
- Model artifact registration: if all checks pass, register the model version in a model registry with full metadata.

### Deployment Pipeline (triggered by model promotion)

- Staging deployment with shadow or canary evaluation.
- Production rollout with monitoring and automatic rollback triggers.

The key principle: separate code deployment from model deployment. Code changes go through the standard code review and CI pipeline. Model changes go through model-specific validation gates.

## Docker Containerization

Containers solve the "works on my machine" problem that plagues ML projects:

- Package the training environment (Python version, all dependencies, system libraries for numerical computing) into a Docker image.
- Use multi-stage builds: a build stage with compilation tools, a runtime stage with only what is needed to run.
- Pin all dependency versions. A requirements file without pinned versions is a ticking time bomb -- a minor library update can change model outputs silently.
- Separate base images for different workload types: a lightweight CPU image for preprocessing and evaluation, a GPU image for training.
- Never put data or model artifacts in the Docker image. They should be loaded at runtime from external storage.

## Pre-Commit Hooks

Pre-commit hooks catch problems before they enter the repository:

- **Formatting**: Run ruff format or black to ensure consistent style.
- **Linting**: Run ruff check to catch errors and anti-patterns.
- **Type checking**: Run mypy on changed files.
- **Secret detection**: Prevent accidental commits of API keys, credentials, or tokens.
- **Large file detection**: Prevent accidental commits of data files or model artifacts.
- **Notebook cleaning**: Strip output from Jupyter notebooks before committing (nbstripout).

Configure pre-commit hooks in a .pre-commit-config.yaml file. All team members run the same hooks, enforcing consistency without manual effort.

## Configuration Externalization

Hardcoded values in ML code create three problems: they cannot be changed without code changes, they are not tracked across experiments, and they differ silently between environments.

Externalize everything that might change:

- Model hyperparameters (learning rate, number of trees, max depth).
- Data paths and connection strings.
- Feature lists and preprocessing parameters.
- Evaluation thresholds (minimum accuracy to pass validation).
- Environment-specific settings (local vs. staging vs. production stack names, resource allocations).

The configuration hierarchy should be: defaults in code (for development convenience), overrides in config files (for experiment tracking), overrides via environment variables (for deployment automation), and overrides via CLI arguments (for ad-hoc runs).

## Package Management with uv

Modern ML projects benefit from fast, reproducible dependency management. uv is the current recommended tool for Python package management:

- Faster than pip by an order of magnitude for dependency resolution and installation.
- Generates lockfiles for fully reproducible environments.
- Handles virtual environment creation and management.
- Compatible with existing requirements.txt and pyproject.toml formats.

Use pyproject.toml as the single source of truth for project metadata, dependencies, and tool configuration (ruff, mypy, pytest settings all live here).

## Documentation

ML project documentation serves different audiences:

- **README**: Quick start for new team members. How to set up the environment, run training, run evaluation, and deploy.
- **Architecture documentation**: How the pipeline is structured, what each step does, how data flows, what artifacts are produced.
- **Experiment documentation**: What was tried, what worked, what did not, and why. This prevents repeating failed experiments.
- **API documentation**: Docstrings on all public functions and classes, auto-generated into browsable docs.

Write docstrings on every function, especially ML steps. Each docstring should explain what the function does, what its inputs and outputs are, and any assumptions about data format or value ranges.

## When to Use This

- When transitioning from a prototype notebook to production code. Apply the project structure pattern and extract code into modules.
- When setting up a new ML project from scratch. Configure the full toolchain (linting, testing, CI, Docker) before writing the first model.
- When joining an existing ML project that lacks structure. Incrementally introduce testing, type hints, and configuration externalization.
- When a model retraining pipeline is fragile or unreproducible. Add containerization and configuration management to stabilize it.
- When onboarding new team members. Good coding practices reduce the time to understand and contribute to the project.

## Red Flags to Watch For

- **No tests at all**: An ML pipeline without tests will break silently when data or dependencies change. Even smoke tests are better than nothing.
- **Hardcoded paths and parameters**: If changing a hyperparameter requires editing source code, experimentation is slower and less traceable.
- **No version pinning**: Unpinned dependencies mean the training environment changes over time without anyone noticing. Model outputs become irreproducible.
- **Notebook as production artifact**: If a Jupyter notebook is being executed on a schedule or as part of a pipeline, it needs to be refactored into proper Python modules.
- **No CI pipeline**: Manual testing before merge is unreliable. Automated checks on every commit catch regressions early.
- **Configuration scattered across files**: If hyperparameters live in five different Python files, changing them requires modifying multiple files and hoping nothing is missed.
- **No separation between ML code and infrastructure code**: When model training logic is interleaved with deployment, monitoring, or alerting code, both become harder to change. Keep them in separate directories with clear boundaries.
- **Skipping Docker for "simple" projects**: Even simple projects benefit from containerized environments. The cost of setting up Docker is low; the cost of debugging environment mismatches is high.
- **No experiment tracking**: If there is no record of which parameters produced which metrics, the team will repeat failed experiments and lose track of what worked.
