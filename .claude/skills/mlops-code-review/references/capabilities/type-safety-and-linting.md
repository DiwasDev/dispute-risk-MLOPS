# Type Safety and Linting for ML Code

ML code suffers from a pervasive type ambiguity problem. A variable named `features` might be a pandas DataFrame, a numpy ndarray, a list of lists, a scipy sparse matrix, or a torch Tensor. Each has different APIs, different performance characteristics, and different failure modes. Without type annotations, every function boundary is a potential runtime surprise. Type hints and linting are not bureaucracy -- they are the first line of defense against the "worked in the notebook, crashed in production" class of bugs.

## Why Type Hints Matter in ML

**DataFrame vs ndarray vs Tensor confusion**: ML pipelines frequently convert between data representations. Preprocessing produces a DataFrame. The model expects an ndarray. The serving layer returns JSON. Each conversion is a potential shape, dtype, or content error. Type annotations make these conversions explicit and reviewable.

**Function signatures as documentation**: In a codebase with functions like `def process(data, config, params)`, readers must trace through the implementation to understand what `data` is. `def process(data: pd.DataFrame, config: TrainingConfig, params: dict[str, float]) -> np.ndarray` is immediately clear.

**Static analysis catches real bugs**: mypy and pyright catch errors that tests might miss: passing a Series where a DataFrame is expected, returning Optional when the caller does not handle None, using an ndarray method on a DataFrame. These are exactly the bugs that cause silent failures in ML pipelines.

## Annotation Standards

**Annotate all function signatures**: Every function must have type annotations for all parameters and the return type. No exceptions for "internal" or "simple" functions.

**Use specific types**: `pd.DataFrame` not `Any`. `np.ndarray` not `object`. `ClassifierMixin` not `Any`. The more specific the type, the more bugs the type checker catches.

**Generic types for containers**: `list[str]` not `list`. `dict[str, float]` not `dict`. `tuple[str, int, float]` not `tuple`. Python 3.9+ supports this natively; for 3.8, import from `typing`.

**Optional and Union**: Use `Optional[pd.DataFrame]` (or `pd.DataFrame | None` in 3.10+) when a function can return None. Never return None from a function annotated to return `pd.DataFrame` -- the type checker will miss it and the caller will get a runtime AttributeError.

**Protocol classes for model interfaces**: Use `typing.Protocol` to define structural typing for model interfaces. A model protocol defines `fit`, `predict`, and optionally `predict_proba` without requiring inheritance. Any class that implements these methods satisfies the protocol, enabling duck typing with type safety.

```
class ModelProtocol(Protocol):
    def fit(self, X: pd.DataFrame, y: pd.Series) -> None: ...
    def predict(self, X: pd.DataFrame) -> np.ndarray: ...
```

This is more Pythonic than abstract base classes for defining ML interfaces because it does not require the implementation to inherit from anything.

**TypeAlias for complex types**: When a type annotation becomes unwieldy, define an alias. `FeatureMatrix = pd.DataFrame` or `PredictionArray = np.ndarray` improves readability at function boundaries.

## Ruff Configuration

Ruff is the current standard linter for Python -- it replaces flake8, isort, pyflakes, and many plugins with a single, fast tool. Configure it in `pyproject.toml`.

**Recommended rule sets for ML projects**:
- **E, W**: pycodestyle errors and warnings. Basic style compliance.
- **F**: pyflakes. Catches unused imports, undefined names, redefined unused variables.
- **I**: isort. Consistent import ordering.
- **N**: pep8-naming. Enforces naming conventions (snake_case functions, PascalCase classes).
- **UP**: pyupgrade. Modernizes syntax (use `dict` instead of `typing.Dict` in 3.9+).
- **B**: flake8-bugbear. Catches common bugs (mutable default arguments, assert on tuples).
- **A**: flake8-builtins. Prevents shadowing built-in names (`list`, `dict`, `type`).
- **SIM**: flake8-simplify. Suggests simpler expressions (unnecessary if/else, mergeable conditions).
- **TCH**: flake8-type-checking. Moves type-only imports behind `TYPE_CHECKING` to reduce runtime import costs.

**Configuration pattern**:
```toml
[tool.ruff]
target-version = "py311"
line-length = 99

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "A", "SIM", "TCH"]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S101"]  # Allow assert in tests
```

## mypy Configuration

**Progressive strictness**: Start with basic type checking and increase strictness over time. Do not start with `--strict` on an existing codebase -- it will produce hundreds of errors and be abandoned.

**Progression path**:
1. Start with `--warn-return-any` and `--warn-unused-ignores`. Catches the most common issues without overwhelming noise.
2. Add `--disallow-untyped-defs` for new code (enforce via per-module configuration).
3. Add `--no-implicit-optional` to catch `def f(x: int = None)` bugs.
4. Progress to `--strict` for core modules (model interfaces, preprocessing, evaluation).

**Configuration pattern**:
```toml
[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_ignores = true
disallow_untyped_defs = true
no_implicit_optional = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
```

**Handling third-party libraries**: Many ML libraries (XGBoost, LightGBM) lack type stubs. Use `ignore_missing_imports` for specific modules rather than globally. Install `pandas-stubs` and `types-PyYAML` for commonly used libraries.

## pyproject.toml as Single Source of Truth

Consolidate all tool configuration in `pyproject.toml`. Ruff, mypy, pytest, and project metadata all live in one file. This eliminates configuration scatter across `setup.cfg`, `mypy.ini`, `.flake8`, and `tox.ini`.

## When to Use This

- When reviewing any ML code -- check for type annotations on function signatures.
- When setting up a new ML project -- configure ruff and mypy before writing model code.
- When onboarding a codebase without type hints -- start the progressive strictness path.
- When reviewing PRs that add new functions or modify interfaces -- verify annotations are present and specific.

## Red Flags to Watch For

- Functions with no type annotations, especially at module boundaries.
- `Any` used as a type annotation when a specific type is known.
- No linter configured in the project, or linter disabled via inline comments throughout.
- `# type: ignore` comments without explanation of why the ignore is necessary.
- `mypy` or `pyright` not included in CI.
- `ruff` rules limited to `E` and `F` only -- missing `B`, `SIM`, and `N` catches fewer bugs.
- Type annotations that lie -- annotated as `pd.DataFrame` but actually receives a dict at runtime.
- No `pyproject.toml` -- configuration scattered across multiple dotfiles.
- Import-time side effects that `TCH` rules would catch and move behind `TYPE_CHECKING`.
