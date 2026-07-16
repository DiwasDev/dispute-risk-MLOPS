# Agent Isolation and Multi-Agent Coordination

Agent isolation is the practice of ensuring that multiple agents working on the same codebase cannot interfere with each other. An isolated agent is a safe agent. Without isolation, agents overwrite each other's changes, create merge conflicts in real time, and produce code that assumes a state of the codebase that no longer exists because another agent changed it. Isolation is not optional for multi-agent development -- it is a prerequisite.

## Git Worktrees

Git worktrees are the foundation of agent isolation. A worktree is a separate working directory backed by the same git repository. Each worktree has its own checked-out branch, its own index, and its own working tree. Changes in one worktree are invisible to other worktrees until they are committed and merged.

### Setting Up Worktrees

Create a worktree for each agent task:

```bash
git worktree add ../agent-feature-validation feature-validation
git worktree add ../agent-feature-monitoring feature-monitoring
git worktree add ../agent-bugfix-drift-calc bugfix-drift-calc
```

Each command creates a new directory with a fresh checkout of the specified branch. If the branch does not exist, add `-b` to create it:

```bash
git worktree add -b feature-new-metrics ../agent-new-metrics main
```

### Why Worktrees Over Branches

Branches share the working directory. If agent A is mid-edit on branch `feature-a` and agent B checks out `feature-b`, agent A's uncommitted changes are either lost or create conflicts. Worktrees solve this by giving each agent its own working directory. Agent A works in `../agent-feature-a/` and agent B works in `../agent-feature-b/`. They never touch each other's files.

### Worktree Lifecycle

1. **Create**: Before assigning a task to an agent, create a worktree branching from the current main.
2. **Work**: The agent operates exclusively within its worktree directory. All file paths, all test runs, all tool operations are scoped to this directory.
3. **Commit**: The agent commits to its branch within its worktree.
4. **Push**: The agent pushes its branch to the remote.
5. **PR**: A pull request is created from the agent's branch to main.
6. **Clean up**: After the PR is merged (or abandoned), remove the worktree:

```bash
git worktree remove ../agent-feature-validation
```

### Worktree Hygiene

- Never modify the main worktree while agents are working in their worktrees. Pull updates to main only between agent sessions.
- Each worktree should have its own virtual environment if the project uses Python. Shared virtual environments can cause import conflicts.
- Lock worktrees that should not be modified: `git worktree lock ../agent-feature-a` prevents accidental removal.

## Branch-Per-Agent

One agent, one branch, one PR. This is non-negotiable.

Never have two agents committing to the same branch. Even with worktrees, two agents on the same branch create race conditions: agent A commits, agent B commits on top, agent A commits again and must reconcile B's changes. The result is merge conflicts, duplicated work, and code that assumes incompatible states.

Branch naming convention: `agent/<task-type>/<short-description>`. Examples:

- `agent/feature/data-validation`
- `agent/bugfix/drift-threshold`
- `agent/refactor/preprocessing-module`
- `agent/test/evaluation-coverage`

The prefix makes it easy to identify agent-created branches, filter them in CI, and clean them up.

## Hard Blocks by Agent Role

Different phases of the RPI workflow require different permission levels. Enforce these as hard constraints, not guidelines.

### Scout/Research Agents

Permissions: read-only. Can read files, grep, glob, run read-only shell commands (ls, cat, find, git log, git diff).

Cannot: write files, edit files, run commands that modify state (git commit, pip install, database writes).

Purpose: explore the codebase and produce a research document. The read-only constraint prevents the research phase from accidentally modifying code, which would invalidate the research for subsequent agents.

### Plan Agents

Permissions: read-only on source code, write access to plan files only (e.g., files in `.agent/plans/`).

Cannot: modify source code, test files, configuration files, or any file outside the designated plan directory.

Purpose: produce a detailed implementation plan based on research. Write access is limited to plan documents to prevent the planning agent from "just quickly fixing" something it notices, which would bypass the implementation phase's verification steps.

### Implement Agents

Permissions: full write access to source code, test files, and configuration within their worktree.

Cannot: push to remote. Cannot merge to main. Cannot modify files outside their worktree.

Purpose: execute the plan step by step. The inability to push or merge means that all agent code goes through review before it reaches main.

### Merge Authority

Only CI/CD systems or humans can merge to main. No agent has merge authority. This is the final quality gate and the most important one. An agent that can merge its own code bypasses all review and creates an unaudited path to production.

## Traceability

Every commit made by an agent must be traceable to the agent that made it, the task it was working on, and the plan it was following.

Commit message format:

```
[agent/<role>] <description>

Task: <task-id or description>
Plan: <plan-file-path>
Step: <step-number>

Co-Authored-By: <agent-identifier>
```

PR descriptions document the full agent workflow: which research was done, which plan was followed, which agent executed the implementation. This creates an audit trail that enables debugging when agent-produced code causes issues in production.

## Preventing Cross-Agent Interference

Beyond git isolation, prevent interference at the resource level:

### No Shared Mutable State

- Each agent uses its own test database or isolated test schema. Two agents running tests against the same database will see each other's test data and produce flaky results.
- Each agent uses its own temporary directories. Shared /tmp paths lead to file collisions.
- Each agent uses its own port ranges for local servers. Two agents starting a server on port 8000 causes one to fail.

### Environment Isolation

- Each worktree gets its own `.env` file (or no `.env` -- use environment variables scoped to the agent's process).
- Each worktree gets its own virtual environment. Use the worktree path to name the venv for easy identification:

```bash
python -m venv ../agent-feature-validation/.venv
```

### Test Isolation

- Use test fixtures that create and tear down their own data. No test should assume data created by another test or another agent exists.
- Run tests with `--forked` or equivalent to prevent process-level interference.
- Use unique prefixes for test artifacts (model files, output CSVs) to prevent collisions.

## Swarm Coordination

When running multiple agents in parallel, a coordinator is required. The coordinator is itself an agent (or a script) with a specific role:

- **Assign tasks**: decompose a large task into sub-tasks and assign each to an agent with its own worktree and branch.
- **Collect results**: monitor agent progress, collect completion summaries, and handle failures.
- **Merge**: after all agents complete and their PRs pass review, merge PRs in dependency order.

Individual agents never communicate directly. Agent A does not read agent B's worktree or branch. All communication goes through the coordinator via structured summaries (markdown files, PR descriptions, or structured messages).

If agent B depends on agent A's output, the dependency must be explicit: agent A merges first, agent B's worktree pulls the updated main, then agent B begins. Never have agent B read from agent A's branch directly -- it may contain incomplete or incorrect code.

## Cleanup Protocol

After an agent finishes its task:

1. Verify the worktree is clean: no uncommitted changes, no untracked files.
2. Verify the branch is pushed to remote.
3. Verify the PR is created.
4. Remove the worktree: `git worktree remove ../agent-<task>`.
5. After the PR is merged, delete the remote branch: `git push origin --delete agent/<task>`.

Accumulated worktrees waste disk space and create confusion. Clean up promptly.

## When to Use This

- When running any multi-agent workflow. Even two agents working simultaneously need isolation.
- When a single agent works on multiple tasks sequentially. Use a fresh worktree for each task to prevent cross-contamination.
- When setting up CI/CD for agent-driven development. CI should create worktrees for agent runs and clean them up afterward.
- When debugging agent-produced code. Traceability metadata in commits and PRs identifies which agent and which plan produced the code in question.

## Red Flags to Watch For

- **Multiple agents on the same branch**: This will produce conflicts, duplicated code, and inconsistent state. Always one agent per branch.
- **Agents working in the main worktree**: The main worktree should be reserved for human work and coordination. Agents work in their own worktrees.
- **No role-based permissions**: If a research agent can edit files, it will. Constraints must be enforced, not requested.
- **Direct agent-to-agent communication**: Agents reading each other's worktrees or branches without going through the coordinator creates implicit dependencies that are impossible to debug.
- **Worktrees accumulating without cleanup**: Each worktree is a full checkout. Dozens of stale worktrees consume disk and create confusion about which work is active.
- **Agents with merge authority**: No agent should be able to merge its own code to main. This bypasses review and creates an unaudited path to production.
- **Shared test databases**: Two agents running tests against the same database will produce flaky, unreliable results that waste time and erode trust in the test suite.
