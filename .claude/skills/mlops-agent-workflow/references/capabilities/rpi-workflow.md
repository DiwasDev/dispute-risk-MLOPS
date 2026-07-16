# Research-Plan-Implement Workflow

The Research-Plan-Implement (RPI) workflow is a structured methodology for coding agents that separates exploration, design, and execution into distinct phases. Each phase runs in its own context window with a clear mandate and constrained permissions. The core insight is that agents produce dramatically better output when they focus on one cognitive mode at a time rather than interleaving research, planning, and coding in a single conversation. RPI prevents the most common agent failure mode: diving into implementation before understanding the codebase, then producing code that conflicts with existing patterns, misses edge cases, or solves the wrong problem entirely.

## The Three Phases

### Phase 1: RESEARCH

The research phase is read-only. The agent explores the codebase, traces data flow, identifies existing patterns, and builds a mental model of the system. The agent cannot write or edit any files during this phase.

What the agent does in research:

- Reads source files relevant to the task. Uses grep, glob, and targeted file reads to find code that relates to the feature or bug.
- Traces data flow end-to-end. For an ML pipeline task, this means following data from ingestion through preprocessing, training, evaluation, and prediction.
- Identifies existing patterns. How are similar features implemented? What conventions does the codebase follow for error handling, logging, configuration, and testing?
- Discovers gotchas. Are there circular dependencies? Implicit assumptions? Configuration that lives in unexpected places? Tests that are fragile or missing?
- Maps the dependency graph. Which modules depend on what? What will break if a particular interface changes?

Research output format: a markdown document containing:

- **Task understanding**: one-paragraph restatement of what needs to be done.
- **Relevant files**: exact file paths with line numbers for key functions, classes, and configuration.
- **Existing patterns**: how the codebase handles similar concerns (with code snippets).
- **Gotchas discovered**: anything surprising or potentially problematic.
- **Open questions**: things the agent could not determine from code alone.

The research document becomes the input to the plan phase. Its quality directly determines plan quality.

### Phase 2: PLAN

The plan phase is design-only. The agent reads the research document and designs the implementation. The agent can write plan files but cannot modify source code.

What the agent does in planning:

- Reviews the research document to confirm understanding.
- Designs the implementation as a sequence of discrete steps.
- For each step, specifies: which file to modify, what to change (with code snippets showing before and after), what test to run to verify the change, and what success looks like.
- Defines the test strategy: which existing tests must continue passing, what new tests to add, and in what order to run them.
- Identifies risks and defines fallback actions for each.

Plan output format: a step-by-step document where each step contains:

- **Step N: [description]**
- **File**: exact path
- **Change**: code snippet showing the modification
- **Verification**: command to run and expected output
- **Rollback**: how to undo this step if it fails

The plan must be detailed enough that a model with no context about the codebase could follow it mechanically. If a step requires judgment or interpretation, the plan is not detailed enough.

### Phase 3: IMPLEMENT

The implementation phase executes the plan. The agent follows each step in order, running verification after each change. The agent has full write access to source code but operates under a strict constraint: follow the plan.

What the agent does in implementation:

- Executes each step from the plan in sequence.
- After each step, runs the specified verification command.
- If verification passes, moves to the next step.
- If verification fails and the fix is trivial (a typo, a missing import), fixes it and re-verifies.
- If verification fails and the fix is non-trivial, stops immediately. Does not improvise. The correct response is to document what happened and restart the cycle with a new research phase that incorporates the failure.

The critical rule: never improvise during implementation. If the plan says "modify function X to accept parameter Y" and the agent discovers that function X was refactored since the research phase, the agent must stop. Improvised fixes during implementation are the primary source of agent-generated slop.

### Phase Handoff Documents

Each phase produces a handoff document that serves as the sole input to the next phase. This is intentional isolation: the plan agent does not inherit the research agent's full context (all the files it read, all the grep results, all the dead ends). It inherits only the structured research summary. This keeps the plan agent in the smart zone.

Handoff documents must be self-contained. A plan document that says "as we saw in the research phase" is broken -- the implement agent was not in the research phase. Every relevant detail must be restated in the document where it is needed.

The handoff documents also serve as an audit trail. Months later, when someone asks "why was this implemented this way," the research document shows what the agent understood, the plan document shows what approach was chosen and why, and the implementation follows the plan. If any of these documents is missing, traceability is lost.

## When to Restart the Cycle

Restart from research when:

- The scope of the task changes after planning is complete.
- Implementation reveals that the research missed a critical dependency or pattern.
- The plan fails at a step and the failure indicates a misunderstanding of the system, not a simple error.
- The agent is going off track: producing code that does not match the plan, making decisions not covered by the plan, or accumulating workarounds.

Restart from planning (keeping existing research) when:

- The research is still accurate but the approach needs to change.
- A better implementation strategy becomes apparent during early implementation steps.
- External constraints change (e.g., a dependency version is different than expected).

## Task Decomposition for RPI

Large tasks must be broken into RPI-sized chunks. Each chunk should be completable in one context window, which means:

- The research phase can be completed by reading a bounded set of files (typically under 20 files).
- The plan has fewer than 15 steps.
- The implementation can be completed without the context window filling up with tool outputs and error messages.

Decomposition strategy for ML pipeline tasks:

- **By pipeline stage**: data loading, preprocessing, feature engineering, training, evaluation, and serving each get their own RPI cycle.
- **By concern**: adding a new feature is one cycle. Adding tests for that feature is another. Adding monitoring is a third.
- **By risk**: high-risk changes (modifying shared interfaces, changing data contracts) get small, focused RPI cycles. Low-risk changes (adding a utility function, updating documentation) can be grouped.

Each chunk should produce a working, tested increment. Never plan a chunk that leaves the codebase in a broken state.

Ordering chunks matters. Start with chunks that establish interfaces (data contracts, function signatures, configuration schemas). Then implement the chunks that use those interfaces. This ordering means later chunks can rely on stable interfaces established by earlier chunks, rather than designing interfaces and implementing logic simultaneously.

## Lightweight RPI for Small Tasks

Not every task needs a full three-phase cycle with handoff documents. For small, well-understood changes (fixing a typo, adding a log statement, updating a configuration value), a lightweight RPI is sufficient:

- Research: a quick scan of the relevant file and its tests (30 seconds, not a full codebase exploration).
- Plan: a mental plan (or a single sentence) rather than a written document.
- Implement: make the change, run tests, commit.

The key is recognizing which tasks are genuinely small. If the "small" change requires understanding how the system works, reading more than two files, or has any risk of breaking existing functionality, use the full RPI cycle. Underestimating task complexity is the most common mistake.

## The Compaction Technique

When context grows large during a phase, use compaction: ask the agent to summarize its findings into a structured markdown file, then start a fresh agent with that summary as input. This keeps the new agent in the smart zone (fresh context, high-quality output) while preserving the knowledge accumulated so far.

Compaction is especially valuable between RPI phases. The research document is itself a compaction of the research phase. The plan document is a compaction of the planning phase. Each phase starts fresh with only the relevant summary from the previous phase.

Within a phase, compact when the agent has read many files and the context is filling up. Have the agent write a partial research document, then start a new agent that continues the research from where the previous one left off.

## Example: Adding Data Validation to an ML Pipeline

**Research phase**: The agent reads the existing pipeline code. It discovers that data is loaded from CSV in `src/data_loader.py`, preprocessed in `src/preprocessing.py`, and there is no validation step. It finds that the pipeline uses Pydantic for configuration validation but not for data validation. It notes that `tests/test_preprocessing.py` has fixtures with sample DataFrames. Research document includes all file paths, existing patterns, and the finding that no validation exists today.

**Plan phase**: The agent designs a validation module at `src/data_validator.py` using Pandera (consistent with the Pydantic pattern already in the codebase). Step 1: create the schema definition. Step 2: create the validation function. Step 3: integrate into the pipeline between loading and preprocessing. Step 4: add tests using existing test fixtures. Step 5: add a configuration option to make validation strictness configurable.

**Implement phase**: The agent follows the five steps, running tests after each. At step 3, it discovers that the pipeline orchestrator does not support inserting steps between existing ones without modifying the DAG definition. This is a non-trivial discovery. The agent stops, documents the finding, and a new research phase investigates how to modify the DAG.

**Second RPI cycle**: A new research phase explores the DAG orchestrator. It discovers that the DAG definition lives in `pipelines/training.py` and steps are registered using a `@pipeline.step` decorator with an `after` parameter for ordering. The plan phase designs the integration: add `@pipeline.step(after="load_data")` to the validation function. The implement phase executes this cleanly because the research was thorough.

This example illustrates why stopping at unexpected discoveries is critical. If the first implement agent had improvised a workaround (e.g., monkey-patching the pipeline at runtime), the code would have "worked" but violated the codebase's established pattern. The second RPI cycle produced code that matches the existing architecture because it took the time to understand it.

## When to Use This

- For any task that touches more than two files. Single-file changes rarely need the full RPI cycle.
- For unfamiliar codebases. RPI forces the agent to understand before it acts.
- For tasks where correctness matters more than speed. The overhead of three phases pays for itself in fewer bugs and less rework.
- For onboarding new agents to a project. The research phase produces documentation that benefits future agents.

## Red Flags to Watch For

- **Skipping research**: An agent that starts writing code immediately is guessing at the codebase structure. The output will conflict with existing patterns.
- **Vague plans**: "Modify the preprocessing module to handle edge cases" is not a plan. A plan must specify exactly which edge cases, exactly which functions, and exactly what the code change looks like.
- **Improvising during implementation**: Any deviation from the plan that is not a trivial fix (typo, missing import) should trigger a stop-and-replan, not a creative workaround.
- **Monolithic RPI cycles**: If the research phase requires reading 50+ files or the plan has 30+ steps, the task needs decomposition.
- **No verification between steps**: Implementation without running tests after each step accumulates errors that compound. By the time the agent finishes, the codebase may be in a state that is hard to debug.
- **Reusing the same agent across phases**: Each phase should start with a fresh context. An agent that researched, planned, and is now implementing has a full context window and declining output quality.
