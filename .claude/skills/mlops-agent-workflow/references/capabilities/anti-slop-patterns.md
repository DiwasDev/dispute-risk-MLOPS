# Anti-Slop Patterns for Agent-Driven Development

Slop is code that "works" in the narrowest sense -- it runs without errors on the happy path -- but is untested, unreviewed, poorly structured, and fragile. It is the AI equivalent of technical debt, accumulated at the speed of code generation rather than the speed of human typing. An agent can produce a thousand lines of slop in minutes. Cleaning up that slop takes hours. The economics of agent-driven development only work if slop is prevented at the source, not patched after the fact.

## Rule 1: Never Fix Bad Output

When an agent produces slop, the instinct is to edit the output: fix the variable name here, add error handling there, restructure this function. This is wrong. Patching slop is patching symptoms. The root cause is upstream: a bad prompt, missing context, wrong approach, or an agent in the dumb zone.

The correct response to bad agent output:

1. Diagnose why the output was bad. Was the prompt vague? Did the agent lack context about existing patterns? Was the task too large for one context window? Was the agent deep in the dumb zone after a long conversation?
2. Fix the root cause. Rewrite the prompt. Provide missing context. Decompose the task. Start a fresh agent.
3. Rerun from scratch. The agent produces a clean output based on the fixed inputs.

Patching slop on top of slop creates a debt spiral. Each patch makes the code harder to understand, which makes the next agent interaction worse (agents pattern-match on what they see), which produces more slop, which requires more patches. Break the cycle at the source.

## The Anti-Mocking Position

Mocks test implementation, not behavior. When you mock a database, you are testing that your code calls the mock correctly -- you are not testing that your code works with a real database. The mock is a bet that your understanding of the database's behavior is complete and correct. That bet is often wrong.

For ML pipelines, mocking is especially dangerous:

- **Mocked preprocessing hides training-serving skew**: If the mock returns perfectly formatted data, the test passes. In production, the real preprocessor returns data with a different column order, different null handling, or different encoding -- and the model produces garbage predictions silently.
- **Mocked model inference hides latency and memory issues**: The mock returns instantly. The real model takes 200ms and allocates 500MB. The integration that "works" in tests fails under production load.
- **Mocked feature stores hide data freshness issues**: The mock returns current features. The real feature store returns stale features because the ingestion job is delayed. The model makes decisions on outdated data.

The alternative: use real dependencies in tests.

- Use a real database (SQLite for unit tests, the actual database engine for integration tests).
- Use real file systems (tmpdir fixtures, not mocked file objects).
- Use real model objects (small models trained on tiny datasets, not mock objects that return hardcoded predictions).

The only acceptable mocks: external APIs with rate limits or per-call costs. And even then, prefer recorded responses (VCR pattern) over handcrafted mock responses. A recorded response is a snapshot of real behavior. A handcrafted mock is an assumption about behavior.

Integration tests catch real bugs. Mocks catch imaginary ones. The test suite should be weighted heavily toward integration tests, with unit tests reserved for pure functions with no side effects.

The testing pyramid for agent-driven ML development is inverted compared to traditional software: integration tests at the base (most numerous, highest value), contract tests in the middle (verifying interfaces between pipeline stages), and unit tests at the top (fewest, for pure computation only). This is because the most dangerous bugs in ML systems are integration bugs: data format mismatches, training-serving skew, and pipeline ordering errors. Unit tests cannot catch these.

## Zero-Ambiguity Specs

Every specification given to an agent must be detailed enough that two independent agents, given the same spec, would produce functionally identical implementations. If the spec is ambiguous, the agent will guess. It will guess wrong roughly half the time.

A zero-ambiguity spec includes:

- **Exact file paths**: "Modify the preprocessing module" is ambiguous. "Modify `src/preprocessing/feature_engineering.py`, function `encode_categoricals` at line 47" is not.
- **Exact function signatures**: "Add a validation function" is ambiguous. "Add `def validate_schema(df: pd.DataFrame, schema: pa.DataFrameSchema) -> pd.DataFrame` that raises `SchemaError` on failure" is not.
- **Code snippets for complex logic**: If the logic involves a non-obvious algorithm, conditional branching, or specific error handling, include the code in the spec. The agent should be implementing, not designing.
- **Test cases that define correct behavior**: "It should handle edge cases" is ambiguous. "Given input DataFrame with all-null column 'age', the function should raise `ValueError` with message 'Column age has 100% null rate, exceeding threshold of 50%'" is not.
- **Negative requirements**: what the implementation should NOT do. "Do not modify the model training step. Do not add new dependencies. Do not change the function signature of any existing public function."

The effort to write a zero-ambiguity spec feels high. It is lower than the effort to debug, review, and fix the ambiguous output the agent would have produced.

## Mental Alignment Through Plan Reviews

The highest-leverage point for human review is the plan, not the code. A bad plan produces a hundred bad lines of code that are expensive to fix. A bad line of research -- misunderstanding how a system works -- sends the entire implementation in the wrong direction.

Review hierarchy by impact:

1. **Review the research** (highest leverage): Is the agent's understanding of the system correct? Did it find the right files? Did it identify the right patterns? A wrong understanding here cascades into every subsequent decision.
2. **Review the plan** (high leverage): Does the plan solve the right problem? Is the approach sound? Are the steps in the right order? Are the verification criteria correct? Catching a bad plan saves hours of implementation and debugging.
3. **Review the code** (lower leverage): Does the code match the plan? Are there implementation errors? This is the traditional code review, and it is the least impactful place to invest human attention because a good plan constrains the implementation space dramatically.

Move human review effort upstream. Spend 70% of review time on research and plan, 30% on code.

## Standardization

One place for issues. One place for agent learnings. One place for agent work output. Scattered context is lost context.

If agent A discovers a gotcha (e.g., "the feature store returns UTC timestamps but the training data uses local time") and logs it in a random markdown file in its worktree, agent B will never find it. Agent B will discover the same gotcha independently, wasting time, or worse, miss it and produce code with a timezone bug.

Standardized locations:

- **Agent learnings**: `.agent/learnings/` -- gotchas, codebase quirks, non-obvious patterns. Each learning is a short markdown file with a descriptive filename.
- **Agent plans**: `.agent/plans/` -- implementation plans, keyed by task ID or branch name.
- **Agent research**: `.agent/research/` -- research documents from the RPI workflow.
- **Issues and tasks**: one issue tracker (GitHub Issues, Linear, Jira). Not scattered across markdown files, Slack messages, and email threads.

Agents should read the learnings directory at the start of every task. New discoveries should be written there immediately. This creates an institutional memory that improves over time.

## The "Explain It To Me" Test

If an agent cannot explain why it made a specific decision, the decision is probably wrong. Good code comes with reasoning. Code without reasoning is cargo-culted.

Apply this test to agent output:

- Why this data structure? (Because it supports O(1) lookup by feature name, which the serving path requires.)
- Why this algorithm? (Because the input is already sorted, so binary search is optimal.)
- Why this error handling strategy? (Because the upstream API returns transient 503 errors that resolve on retry, but 400 errors indicate bad input and should not be retried.)

If the answer is "because that is how the agent did it," the decision needs human scrutiny. Ask the agent to explain its reasoning. If the explanation is vague or circular, the decision was arbitrary and should be redesigned.

This test is especially important for ML-specific decisions: feature selection, model choice, threshold setting, evaluation metric selection. These decisions have outsized impact on model quality and must be grounded in explicit reasoning, not pattern-matched from training data.

## Pit of Success for Agents

Structure the codebase so the easiest path is the correct path. Agents follow the path of least resistance, just like humans. Make the correct path the easiest one.

Concrete patterns:

- **Typed configs**: Use Pydantic or dataclasses for configuration. Agents cannot pass wrong types because the type checker catches it. Compare this to raw dictionaries where any key and any value type is accepted silently.
- **Strict linters**: Ruff with comprehensive rules catches common mistakes before the agent commits. The agent learns from the linter output and adjusts.
- **Pre-commit hooks that block bad patterns**: If the hook rejects code with bare excepts, the agent will stop using bare excepts.
- **Template files for common patterns**: If every new pipeline step follows the same structure, provide a template. The agent copies and adapts the template rather than inventing a new structure.
- **Comprehensive type hints on all interfaces**: An agent reading a function with full type hints knows exactly what to pass and what to expect back. Without type hints, it guesses.

The harder it is to write bad code, the better agent output you get.

## The Feedback Loop Problem

Agents do not learn across sessions. Agent A's mistake does not teach agent B to avoid the same mistake. Without explicit mechanisms to capture and propagate learnings, every agent starts from zero.

Solutions:

- **Agent learnings directory**: after every task, the agent writes a short file documenting any non-obvious discoveries, gotchas, or patterns. Future agents read this directory at the start of their task.
- **Post-incident updates**: when agent-produced code causes a bug, document the root cause and update the agent's prompt template or reference material to prevent recurrence.
- **Pattern libraries**: collect examples of good implementations that agents can reference. Instead of describing what good error handling looks like, show a concrete example from the codebase. Agents learn more effectively from examples than from descriptions.

This feedback loop is the difference between a team that gets progressively better at using agents and one that makes the same mistakes repeatedly.

## Task Decomposition

A focused agent is a correct agent. Large, vaguely scoped tasks produce large amounts of vaguely correct code. Small, precisely scoped tasks produce small amounts of precisely correct code.

The principle: one agent, one task, one prompt. Each task should be completable in a single context window without the agent entering the dumb zone. If a task requires the agent to hold more context than it can manage, decompose it.

Decomposition rules:

- Each sub-task has a single, clear objective that can be stated in one sentence.
- Each sub-task produces a testable increment (the codebase passes all tests before and after).
- Sub-tasks have explicit dependencies (B depends on A being merged) or are fully independent.
- The agent should not need to ask follow-up questions. If the prompt requires clarification, the spec is not detailed enough.

## Decision Points

Standardize when the human needs to come back into the loop. Not after every line of code -- that defeats the purpose of agent-driven development. Not never -- that produces unsupervised slop.

Human decision points:

- **Architectural decisions**: choosing between approaches, introducing new dependencies, changing data contracts. These decisions have long-term consequences that agents cannot evaluate.
- **Scope changes**: the task turned out to be larger or different than expected. The human decides whether to expand scope or defer.
- **Unexpected failures**: the plan failed and the agent cannot determine why. Escalate rather than improvise.
- **Trade-off decisions**: performance vs. readability, completeness vs. shipping speed, generality vs. simplicity. These are judgment calls that reflect project priorities.

Everything else -- implementation details, test writing, refactoring, linting fixes -- agents handle autonomously within the boundaries set by the plan and quality gates. The human intervenes at high-leverage decision points and trusts the automated system for everything else.

Define decision points explicitly in the plan document. Each step in the plan should be marked as either "autonomous" (agent proceeds without human input) or "checkpoint" (agent stops and waits for human review). This makes the workflow predictable for both the human and the agent. An agent that does not know when to stop will either stop too often (wasting human time) or never stop (producing unsupervised output).

## When to Use This

- When introducing agents to a team or codebase for the first time. Anti-slop patterns prevent the most common failure modes.
- When agent output quality is declining. Audit the workflow against these patterns to identify which principle is being violated.
- When scaling from one agent to multiple agents. The coordination and standardization patterns become critical at scale.
- When debugging a production issue caused by agent-produced code. Trace back through the workflow: was the spec ambiguous? Was the plan reviewed? Were quality gates enforced?

## Red Flags to Watch For

- **Patching agent output instead of rerunning**: Every manual fix to agent output is a sign that the input was wrong. Fix the input, not the output.
- **Mocks throughout the test suite**: If the test suite is mostly mocks, it is testing assumptions, not behavior. Real bugs will reach production.
- **Ambiguous specs**: "Add error handling" or "improve the preprocessing" are not specs. They are wishes. Agents cannot implement wishes reliably.
- **No plan review before implementation**: The plan is the highest-leverage review point. Skipping it and reviewing code instead wastes human attention on low-leverage details.
- **Agent learnings scattered or absent**: If agents are not writing down what they discover, each agent restarts from zero. Institutional memory is lost.
- **Agents making architectural decisions autonomously**: Architecture decisions require human judgment about long-term consequences. Agents optimize for the current task, not the long-term health of the system.
- **No decision points defined**: If the human never re-enters the loop, the agent is unsupervised. If the human re-enters after every line, the agent is a glorified autocomplete. Define the right balance explicitly.
