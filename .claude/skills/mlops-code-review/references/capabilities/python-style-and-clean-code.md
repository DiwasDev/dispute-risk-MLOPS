# Python Style and Clean Code for ML

Clean code in ML projects is not an aesthetic preference -- it is a survival mechanism. ML codebases accumulate complexity faster than traditional software because they interleave data transformations, model logic, configuration, and infrastructure. A function with unclear naming or tangled responsibilities becomes a bug factory when data distributions shift or preprocessing requirements change. These conventions, drawn from PEP 8, PEP 20, the Google Python Style Guide, and Clean Code principles adapted for Python, provide the foundation for reviewable, maintainable ML code.

## Naming Conventions

Naming is the single most impactful readability practice. In ML code, where variables represent mathematical concepts, data structures, and pipeline stages, precise naming eliminates entire categories of confusion.

**Functions and variables**: snake_case. `compute_feature_importance`, `train_test_ratio`, `scaled_features`. Never abbreviate unless the abbreviation is universal (`df` for DataFrame is acceptable in local scope, `x` and `y` for features and labels in ML context).

**Classes**: PascalCase. `FeatureEncoder`, `ModelTrainer`, `DataValidator`. The class name should describe what the object is, not what it does -- `FeatureEncoder` not `EncodeFeatures`.

**Constants**: UPPER_SNAKE_CASE. `MAX_TRAINING_EPOCHS`, `DEFAULT_LEARNING_RATE`, `FEATURE_COLUMNS`. Constants belong at module level or in configuration, never buried inside functions.

**Private members**: Single leading underscore. `_fitted_scaler`, `_validate_schema`. Double underscores are for name mangling to avoid subclass collisions, not for "making things private."

**Boolean variables and functions**: Name them as yes/no questions. `is_trained`, `has_missing_values`, `should_retrain`. Never `flag`, `check`, `status` without qualification.

**ML-specific naming**: Be explicit about data state. `raw_features` vs `scaled_features` vs `encoded_features`. `train_df` vs `val_df` vs `test_df`. Never just `data` or `features` when the transformation state matters -- and in ML, it always matters.

## Function Design

Functions are the primary unit of code review. A well-designed function is easy to understand, test, and replace.

**Length**: Target 20 lines of logic maximum. If a function exceeds this, it is doing too much. ML code is particularly prone to long functions because data loading, cleaning, transformation, and validation tend to accumulate in one place. Split aggressively.

**Single responsibility**: Each function does one thing. `load_data` loads data. `validate_schema` validates the schema. `encode_categoricals` encodes categoricals. A function named `load_and_preprocess_data` is a code smell -- it will grow unbounded as preprocessing requirements change.

**Arguments**: Limit to 4-5 parameters. When a function needs more, group related parameters into a dataclass or configuration object. A function with 8 parameters for hyperparameters is begging for a `TrainingConfig` object.

**Return values**: Return one thing. If a function returns a tuple of 4 items, it is doing too much or needs a named return type (dataclass, NamedTuple).

**Pure functions**: Prefer pure functions (no side effects, output depends only on input) for all data transformation logic. Pure functions are trivially testable and composable. Side effects (saving files, logging metrics, updating state) should be pushed to the edges of the pipeline.

## PEP 20 Principles Operationalized

The Zen of Python is not philosophy -- it is a decision framework for code review.

**Explicit is better than implicit**: Do not rely on default behavior that readers must know. If a scaler defaults to `with_mean=True`, write it explicitly when the choice matters. If a train/test split defaults to `shuffle=True`, write `shuffle=True` when shuffle is intentional for non-time-series data, and `shuffle=False` when temporal ordering matters.

**Flat is better than nested**: If a function has more than 2 levels of indentation, refactor. Extract inner conditions into named functions. Replace nested if/else with early returns (guard clauses). ML code with deeply nested data validation logic is a review red flag.

**Errors should never pass silently**: Never catch exceptions just to suppress them. A `try/except: pass` in data loading code means corrupt data flows silently through the pipeline. If you catch an exception, log it, re-raise it, or handle it explicitly.

**There should be one -- and preferably only one -- obvious way to do it**: In an ML codebase, if there are three different ways to load data or two different feature encoding patterns, standardize on one. Inconsistency multiplies the cognitive load for every reviewer and future maintainer.

**If the implementation is hard to explain, it is a bad idea**: This applies directly to feature engineering. If a feature transformation requires a paragraph to explain, it will be implemented incorrectly by the next person who touches it. Simpler features that are easy to understand and maintain beat clever features that only the author can debug.

## Common Anti-Patterns

### God Objects

A class that manages data loading, preprocessing, training, evaluation, and serving is a God object. It violates SRP, is untestable in isolation, and becomes a merge conflict magnet. In ML code, the `ModelPipeline` class that does everything is the most common God object. Split it into separate classes with clear interfaces.

### Feature Envy

A function that accesses the internals of another object more than its own data. Common in ML: a training function that reaches into the data loader to modify its state, or an evaluation function that accesses the model's internal weights directly instead of using the prediction interface.

### Long Parameter Lists

Functions with 8+ parameters, common in model training code that passes hyperparameters individually. Solution: group parameters into configuration objects (`TrainingConfig`, `DataConfig`, `ModelConfig`).

### Boolean Blindness

`train_model(data, True, False, True)` -- what do those booleans mean? Use keyword arguments or, better, use enums or configuration objects. `train_model(data, use_gpu=True, shuffle=False, verbose=True)` is self-documenting.

### Magic Numbers

Hardcoded thresholds, dimensions, or indices scattered through code. `if score > 0.7` -- what is 0.7? Why 0.7? Name it: `APPROVAL_THRESHOLD = 0.7`. In ML code, magic numbers in feature engineering and evaluation logic are particularly dangerous because they are easily confused with hyperparameters.

### Dead Code

Commented-out model architectures, unused feature engineering functions, experimental code paths that were never cleaned up. Dead code in ML projects accumulates faster than in other software because of rapid experimentation. Remove it -- git preserves history.

### Premature Abstraction

Creating a `BaseModel` abstract class and `ModelFactory` pattern when the project only has one model type. In ML, wait until you have at least two concrete implementations before abstracting. Over-engineering the model interface before the problem is well-understood creates abstractions that do not match reality.

## When to Break the Rules

Rules exist to reduce cognitive load, not to be followed dogmatically. Break them when:

- **Performance requires it**: A vectorized numpy operation that is "too long" but runs 100x faster than the "clean" loop version should stay as-is. Add a comment explaining why.
- **Domain convention overrides general style**: ML papers use `X`, `y`, `W`, `b` for features, labels, weights, biases. Using `feature_matrix` everywhere obscures the mathematical correspondence.
- **Readability is subjective**: If the team agrees a longer function is clearer than splitting it, that is a valid decision. Document the rationale.

## When to Use This

- During code review of any ML Python code -- use these conventions as the baseline.
- When onboarding new team members to establish shared coding standards.
- When refactoring notebook code into production modules.
- When a codebase has inconsistent style and needs a reference standard.

## Red Flags to Watch For

- Functions longer than 30 lines with multiple responsibilities mixed together.
- Variables named `data`, `result`, `output`, `temp`, `x` in non-mathematical contexts.
- No type hints on function signatures.
- Bare `except` clauses swallowing errors silently.
- Boolean parameters without keyword naming in function calls.
- Commented-out code blocks that have persisted across multiple commits.
- Inconsistent naming conventions within the same module.
- Functions with more than 5 parameters that are not grouped into configuration objects.
- Import statements scattered throughout the file instead of grouped at the top.
- Mutable default arguments (`def process(data, cache={})`) -- a classic Python footgun.
