# Quality Gates for Agent-Driven Development

Quality gates are automated checkpoints that code must pass before it is accepted into the codebase. In agent-driven development, quality gates are not optional safety nets -- they are the primary mechanism for maintaining code quality. Agents produce code faster than humans can review it, which means the feedback loop must be automated and strict. A permissive gate is worse than no gate: it creates the illusion of quality assurance while letting slop through.

## The Pit of Success

The most important concept in agent-driven quality: agents pattern-match on the code they see. If the existing codebase has comprehensive tests, typed function signatures, consistent error handling, and clean module boundaries, the agent will follow those patterns. If the codebase has untested functions, bare excepts, global state, and inconsistent naming, the agent will produce more of the same.

This creates a recursive loop. Good code begets good agent output, which maintains code quality, which produces more good agent output. Bad code begets bad agent output, which degrades code quality, which produces worse agent output. The loop amplifies in both directions.

Investment in code quality before introducing agents has outsized returns. Clean up the codebase first. Add comprehensive tests. Enforce strict linting. Then let agents contribute. The initial investment pays for itself through every subsequent agent interaction.

## Mandatory Gates

Every gate listed below must pass before any code is accepted. No exceptions, no overrides, no "we will fix it later."

### All Tests Pass

100% of tests must pass. Not 99%. Not "all except the known failures." 100%.

Known failures are not allowed. If a test is failing, either fix it or delete it. A failing test that everyone ignores trains both humans and agents to ignore test failures. When a real failure appears, it is lost in the noise.

Skipped tests must have a tracked ticket. Every `@pytest.mark.skip` or `xfail` must reference an issue number. During every sprint review, skipped tests are reviewed. If the issue is not being worked, the test is either fixed or deleted.

Tests must be fast. If running the full test suite takes more than two minutes, agents will be slow and context will fill up waiting for results. Optimize test speed aggressively: use fixtures, avoid unnecessary I/O, parallelize where possible.

### Strict Linting

Configure ruff with a comprehensive rule set. The recommended minimum for ML projects:

```toml
[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "A", "SIM", "TCH"]
```

- **E, F**: pycodestyle errors and pyflakes (basic correctness).
- **I**: isort (import ordering).
- **N**: pep8-naming (consistent naming conventions).
- **UP**: pyupgrade (use modern Python idioms).
- **B**: flake8-bugbear (common bug patterns).
- **A**: flake8-builtins (shadowing built-in names).
- **SIM**: flake8-simplify (unnecessary complexity).
- **TCH**: flake8-type-checking (type-checking import optimization).

Zero warnings allowed. Not "zero errors, some warnings." Zero of both. Every warning that is tolerated becomes an invitation for agents to produce more code with warnings.

### Type Checking

Run mypy or pyright with strict settings on all production code. Type errors are blocking -- code with type errors cannot be merged.

For ML projects, configure mypy to handle common ML library patterns:

```toml
[tool.mypy]
strict = true
plugins = ["pydantic.mypy"]
ignore_missing_imports = false
```

Type hints serve as documentation that agents read. A well-typed codebase gives agents precise information about expected inputs and outputs, reducing guessing.

### No Force Pushes

Force pushes are never acceptable. They rewrite history, which destroys traceability (which agent produced which code, which plan led to which implementation) and can silently delete other agents' work.

### No --no-verify

Pre-commit hooks exist for a reason. Bypassing them with `--no-verify` is never acceptable. If a hook is failing, fix the underlying issue. If a hook is too slow, optimize it. Never skip it.

### PR Review Before Merge

Every change goes through review before merging to the main branch. The review can be human or a structured agent review, but it must happen. Direct commits to main are blocked.

## Configuration Examples

### pyproject.toml

```toml
[tool.ruff]
target-version = "py311"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "A", "SIM", "TCH"]

[tool.mypy]
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
addopts = "--strict-markers --tb=short -q"
markers = []
```

### Pre-commit hooks

```yaml
repos:
  - repo: local
    hooks:
      - id: ruff-format
        name: ruff format
        entry: ruff format --check
        language: system
        types: [python]
      - id: ruff-lint
        name: ruff lint
        entry: ruff check
        language: system
        types: [python]
      - id: mypy
        name: mypy
        entry: mypy
        language: system
        types: [python]
      - id: pytest
        name: pytest
        entry: pytest
        language: system
        pass_filenames: false
```

## Gate Failure Protocol

When a quality gate fails, the agent must fix the issue. The agent cannot skip the gate, disable the check, or mark the test as expected failure. The protocol:

1. Read the gate failure output.
2. Identify the root cause (not the symptom -- the root cause).
3. Fix the root cause in the source code.
4. Re-run the gate to verify the fix.
5. If the agent cannot fix the issue after two attempts, escalate to human review. Do not attempt workarounds.

Gate failures are information. A linting failure means the code does not follow project conventions. A type error means there is a contract mismatch. A test failure means the code does not behave as expected. Treating failures as obstacles to bypass rather than information to act on is the root cause of agent-generated technical debt.

## Progressive Strictness

Start with the gates that catch the most impactful issues and add stricter rules over time:

**Phase 1** (immediate): All tests pass, basic linting (E, F rules), no force pushes.

**Phase 2** (after codebase stabilizes): Full linting rule set, type checking in non-strict mode, pre-commit hooks.

**Phase 3** (mature codebase): Strict type checking, zero warnings, coverage thresholds, security scanning.

Each phase builds on the previous one. Do not jump to Phase 3 on a codebase that has never had linting. The volume of violations will be overwhelming and agents will struggle to produce code that passes all gates simultaneously.

## When to Use This

- When setting up a new project that agents will contribute to. Configure gates before the first agent interaction.
- When introducing agents to an existing project. Audit current gate coverage and fill gaps before agents start writing code.
- When agent output quality is declining. Often the root cause is permissive gates that allow low-quality patterns to accumulate.
- When onboarding new team members or agents. Gates enforce conventions automatically, reducing the need for manual code review of style and correctness issues.

## Red Flags to Watch For

- **Tests marked as expected failures without tickets**: Every xfail or skip needs a tracked issue. Without tracking, skipped tests accumulate and are never fixed.
- **Linting warnings tolerated**: "It is just a warning" is the beginning of codebase degradation. Agents will match the level of strictness they observe.
- **Gates disabled for speed**: If gates are too slow, optimize them. Do not disable them. A fast feedback loop with no quality checks is worse than a slow one with strict checks.
- **Agent bypassing hooks**: If an agent uses `--no-verify` or disables a linter rule inline, the workflow configuration is wrong. Agents should not have the ability to bypass gates.
- **No gate on type checking**: In ML code, type mismatches between pipeline stages are one of the most common bugs. Type checking catches them before runtime.
- **Coverage thresholds without coverage quality**: 80% line coverage with no branch coverage and no assertion quality gives false confidence. Measure what matters.
