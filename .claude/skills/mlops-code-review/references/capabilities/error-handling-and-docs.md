# Error Handling and Documentation for ML Code

ML pipelines fail in ways that traditional software does not -- data arrives malformed, models produce degenerate predictions, feature distributions shift unexpectedly. How the code handles these failures determines whether the team spends hours debugging or minutes responding. Similarly, ML code is harder to understand than typical application code because it encodes domain knowledge, mathematical transformations, and data assumptions that are invisible without documentation. This reference covers error handling patterns and documentation standards for ML code review.

## Error Handling Principles

### Never Use Bare Except

A bare `except:` or `except Exception:` that swallows the error is the most dangerous pattern in ML code. When data loading fails silently, the pipeline continues with empty or partial data. When preprocessing fails silently, the model trains on corrupt features. When evaluation fails silently, a broken model gets promoted to production.

**Rule**: Catch specific exceptions. `except FileNotFoundError`, `except ValueError`, `except KeyError`. If you must catch a broad exception for logging, always re-raise it.

### Fail Fast in Pipelines

Bad data should cause errors at ingestion, not at evaluation. A missing column discovered during model scoring means the entire pipeline ran on corrupt data -- wasted compute, wasted time, and a debugging session that traces back through every step.

**Pattern**: Validate data at every pipeline boundary. When data enters the pipeline, validate schema. When data passes between steps, validate the contract. When the model receives features, validate shapes and dtypes. Each validation is a checkpoint that prevents corrupt data from propagating.

### Custom Exception Hierarchy

ML projects benefit from a structured exception hierarchy that communicates failure domain:

- `MLPipelineError` -- base class for all pipeline-related errors.
- `DataValidationError` -- schema violations, missing columns, out-of-range values, unexpected nulls.
- `DataLoadError` -- source unavailable, permission denied, format mismatch.
- `FeatureEngineeringError` -- transformation failures, unseen categories, numerical overflow.
- `ModelTrainingError` -- convergence failure, resource exhaustion, invalid hyperparameters.
- `ModelServingError` -- artifact loading failure, prediction timeout, input validation failure.
- `ArtifactError` -- missing artifact, version mismatch, corrupt serialization.

**Why this matters for code review**: When reviewing exception handling, the reviewer can verify that each catch block handles the right domain of errors. A `DataValidationError` should trigger data quality alerts. A `ModelTrainingError` should trigger retraining investigation. Generic `Exception` catches obscure this distinction.

### Logging Levels

Use logging levels consistently to enable filtering and alerting:

- **DEBUG**: Detailed information for development -- feature shapes, intermediate values, timing. Never in production logs.
- **INFO**: Pipeline progress -- step started, step completed, metrics computed. The normal flow.
- **WARNING**: Unexpected but recoverable situations -- unusual null rate detected, feature near boundary, model performance below threshold but above minimum.
- **ERROR**: Failure that prevents a step from completing -- missing data source, model loading failure, prediction timeout. Requires investigation.
- **CRITICAL**: System-level failure that affects the entire pipeline -- out of memory, storage full, dependency service completely unavailable. Requires immediate response.

**ML-specific logging**: Log the data characteristics at each pipeline boundary (row count, column count, null percentage, target distribution) at INFO level. This creates an audit trail for debugging without logging individual records.

## Documentation Standards

### Google-Style Docstrings

Adopt Google-style docstrings for consistency and readability. Every public function and class must have a docstring.

**Required sections**:
- **One-line summary**: What the function does, not how it does it.
- **Args**: Each parameter with its type and description. For ML functions, include expected shapes and value ranges.
- **Returns**: The return type and description. For DataFrames, describe expected columns.
- **Raises**: Which exceptions this function raises and under what conditions.

**Optional but valuable**:
- **Example**: A short usage example, especially for complex feature engineering functions.
- **Note**: Assumptions about data format, ordering requirements, or side effects.

### When Documentation Is Necessary vs Self-Documenting Code

**Code should be self-documenting for**: what it does (use clear function and variable names), control flow (use guard clauses and early returns), simple transformations (the code is the explanation).

**Documentation is necessary for**: why a particular approach was chosen over alternatives, business logic encoded in thresholds or rules, assumptions about data (expected ranges, distributions, missingness patterns), mathematical formulas implemented in code, non-obvious side effects.

**ML-specific documentation needs**: Feature engineering functions should document the feature's purpose (what signal it captures), expected input format, output format, and any training-time-only behavior (fitting statistics). Model evaluation functions should document metric interpretation and business thresholds.

### Comments

**Good comments explain why, not what**: `# Use median imputation because mean is sensitive to income outliers in this dataset` is useful. `# Impute missing values` is not -- the code already says that.

**Flag temporal assumptions**: `# Hardcoded as of 2024-Q3 fee schedule -- update when pricing changes` warns future maintainers.

**Mark known limitations**: `# TODO: This breaks for multi-label classification -- only supports binary` prevents silent misuse.

## README Template for ML Projects

An ML project README serves a different audience than a library README. It must answer: How do I set up the environment? How do I train the model? How do I evaluate it? How do I deploy it?

**Essential sections**:
1. Project overview (what problem, what model type, what data).
2. Environment setup (Python version, dependency installation, required environment variables).
3. Data access (where training data lives, how to refresh it, any access requirements).
4. Training (single command to train, configuration options, expected output).
5. Evaluation (how to run evaluation, what metrics to expect, baseline values).
6. Deployment (how to deploy, serving endpoint, health check).
7. Monitoring (where to find dashboards, what alerts exist, escalation path).

## When to Use This

- When reviewing error handling in any ML pipeline code.
- When reviewing code that lacks or has inconsistent documentation.
- When setting up documentation standards for a new ML project.
- When debugging a pipeline failure that was masked by silent error handling.
- When onboarding new team members who need to understand the codebase.

## Red Flags to Watch For

- Bare `except:` or `except Exception: pass` anywhere in the pipeline.
- No validation at pipeline step boundaries -- data flows unchecked from step to step.
- All exceptions caught at the top level with a generic error message, losing the specific failure context.
- No docstrings on public functions, or docstrings that only restate the function name.
- Comments that describe what the code does rather than why.
- Logging that uses `print()` instead of the `logging` module.
- No custom exceptions -- all errors raised as `ValueError` or `RuntimeError` with string messages.
- Error messages that include raw data values (potential PII exposure).
- Missing README or README that describes setup but not training, evaluation, or deployment.
- WARNING level used for normal operations, making real warnings invisible in the noise.
