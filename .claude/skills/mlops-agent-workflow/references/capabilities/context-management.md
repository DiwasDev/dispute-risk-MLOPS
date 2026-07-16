# Context Management for Coding Agents

Context management is the most important and least intuitive skill in agent-driven development. LLMs are stateless: on every turn, the model reads the entire conversation from scratch and picks the next action based on everything it sees. The quality of that decision depends directly on the signal-to-noise ratio in the context window. A fresh agent with a focused prompt produces dramatically better output than a long-running agent with accumulated tool outputs, error messages, and corrections cluttering its context. Understanding this dynamic and managing it deliberately is the difference between agents that produce reliable code and agents that produce slop.

## The Smart Zone and the Dumb Zone

### The Smart Zone

The smart zone is roughly the first 40% of the context window utilization. In this zone:

- The agent has a clear prompt with a focused task.
- There is minimal noise from previous tool calls, file reads, and error messages.
- The model's attention is concentrated on the task description and relevant context.
- Output quality is at its highest: the agent follows instructions precisely, makes good decisions about which files to read, and produces clean code.

This is where the most important work should happen. High-stakes decisions (architecture choices, complex algorithm design, critical bug fixes) should always be made in the smart zone.

### The Dumb Zone

The dumb zone begins at roughly 40% context utilization and gets progressively worse. In this zone:

- The context is filled with file contents, grep results, error messages, and previous tool outputs.
- The model's attention is diluted across hundreds of lines of code it has already processed.
- The agent begins to repeat itself, contradict previous decisions, forget which files it already edited, and suggest solutions it already tried.
- Output quality declines: the agent misses instructions, makes sloppy edits, and produces code that does not match the patterns it identified earlier.

The transition from smart zone to dumb zone is gradual and invisible. The agent does not announce that it is producing lower-quality output. It continues with the same confidence, making it harder to detect degradation.

## Why This Happens

Every turn, the model processes the full conversation as a flat sequence of tokens. It has no special memory of "what I decided earlier" or "what I already tried." It reconstructs its understanding from the raw text every time. When that text contains a clean task description and relevant code, the reconstruction is accurate. When it contains thousands of lines of tool output, correction attempts, and tangential exploration, the reconstruction becomes noisy and unreliable.

The conversation trajectory also shapes future output. If the agent made a mistake and the human corrected it, the trajectory now contains the pattern: make mistake, get corrected. The model learns from this in-context and may produce more tentative, correction-seeking behavior. If the agent went down a wrong path before being redirected, the wrong path is still in context and can influence future decisions.

## Context Budget

Before starting a task, estimate how much context it will consume:

- **Small task** (single file bug fix, adding a test): one agent, one prompt, no compaction needed. The task completes well within the smart zone.
- **Medium task** (feature spanning 3-5 files): one agent with careful context management. Read only the files you need, compact after exploration, keep tool output minimal.
- **Large task** (cross-module feature, pipeline redesign): must be decomposed into sub-tasks. Each sub-task gets its own agent. A coordinator agent assigns work and collects results.

The budget is not just about token count. It is about cognitive load. Ten small files are less context pollution than one massive file, even at the same token count, because the model can more easily extract relevant information from focused content.

For ML pipeline tasks specifically:

- Data exploration (understanding schemas, distributions, quality): medium context. Requires reading data samples and existing validation code.
- Feature engineering changes: medium context. Requires understanding current features, their computation, and downstream dependencies.
- Model training modifications: large context. Requires understanding data flow, feature pipeline, training loop, evaluation, and deployment -- many files across the full pipeline.
- Adding monitoring or alerting: small to medium context. Usually isolated to a monitoring module with clear interfaces.

## One Agent, One Task, One Prompt

Never reuse an agent for a different task. Even if the agent has context remaining, starting a new task in the same conversation pollutes the context with irrelevant information from the previous task. The new task will be processed in the dumb zone, surrounded by noise from the old task.

Never ask an agent to "also while you are at it" handle a second concern. Each concern gets its own agent, its own prompt, and its own fresh context.

The prompt itself matters. A focused prompt with clear boundaries produces better output than a vague prompt with open-ended scope. Specify: what to do, which files are relevant, what patterns to follow, what the success criteria are, and what not to do.

The trajectory effect is subtle but powerful. Consider: an agent that was asked to implement feature A, struggled with it, received three corrections, and finally got it right. Now you ask it to implement feature B in the same conversation. The agent has learned from the trajectory that its initial attempts are wrong and corrections are expected. It will produce more tentative, less decisive output. Start a fresh agent for feature B and it will approach it with full confidence and clarity.

## Frequent Intentional Compaction

Do not wait until the context is full to compact. Compact proactively every 3-5 significant operations (file reads, tool calls, code edits). Compaction means having the agent summarize its findings and progress into a structured markdown document, then starting a fresh agent with that document as input.

Compaction preserves knowledge while resetting context quality. The fresh agent starts in the smart zone with a clean summary of everything discovered so far.

Effective compaction summaries include:

- What the task is and what has been completed so far.
- Key findings: file paths, function signatures, patterns discovered.
- Decisions made and why.
- What remains to be done.
- Any gotchas or constraints discovered.

Poor compaction summaries are vague ("looked at the codebase, found some issues") or include raw file contents instead of synthesized findings.

## Sub-Agents for Context Control

Sub-agents are fresh agent instances forked to explore a specific subsystem or answer a specific question. The sub-agent runs in its own clean context, completes its task, and returns a short summary to the parent agent. The parent agent stays in the smart zone because it never loaded the sub-agent's exploration into its own context.

Sub-agents are not about anthropomorphizing roles. Do not create a "frontend agent" and a "backend agent" and a "database agent." Create sub-agents based on context boundaries: "explore how the feature store handles caching" is a good sub-agent task because it requires reading a bounded set of files and returning a bounded summary.

Good sub-agent tasks: investigate a subsystem, verify a hypothesis, run and interpret tests, explore alternatives for a specific design decision. Bad sub-agent tasks: "handle the frontend" (too broad), "review my code" (needs the parent's full context).

Sub-agent output format matters. The sub-agent should return a structured summary, not a narrative. Include: what was investigated, what was found (with file paths and line numbers), what the conclusion is, and what the parent agent should know. Keep it under 30 lines. A sub-agent that returns 200 lines of findings defeats the purpose -- the parent agent's context is now polluted with the same information the sub-agent was supposed to encapsulate.

## Practical Context Monitoring

While exact token counts are not always visible, you can estimate context consumption:

- Each file read adds roughly its line count in tokens (plus overhead for tool call formatting).
- Each tool call and response adds both the request and the full response to context.
- Error messages and stack traces are especially expensive -- a single Python traceback can be 30-50 lines.
- Conversation turns accumulate: your messages, the agent's messages, and all tool interactions.

Track operations mentally: after reading 10 files and making 5 edits, you have consumed significant context. If the task is not near completion, compact.

## Signals It Is Time to Compact or Restart

Watch for these indicators that context quality is degrading:

- The agent repeats an action it already performed (re-reading a file it already read, re-running a command it already ran).
- The agent makes suggestions that contradict its earlier analysis.
- The agent loses track of which files it has already edited and suggests editing them again.
- The agent proposes solutions it already tried and abandoned.
- The agent starts producing boilerplate or generic code instead of code tailored to the specific codebase patterns.
- The agent ignores instructions that were clear in the original prompt.

When any of these signals appear, compact immediately. Do not try to course-correct the agent in the same context. The correction adds more noise, pushing the agent further into the dumb zone.

A common mistake is attributing these signals to model quality rather than context quality. The model is not "bad" or "confused" -- it is processing a noisy context. The same model, given a fresh context with the same task and the accumulated findings, will produce dramatically better output. The fix is not a better model. The fix is a cleaner context.

## Error Message Management

Error messages and stack traces are disproportionately expensive in context. A single Python traceback can be 30-50 lines, and a sequence of failed attempts with their stack traces can consume the smart zone entirely.

When an agent encounters errors:

- Capture the relevant error line and message, not the full traceback.
- If the same error occurs repeatedly, summarize it ("same ImportError as before") rather than including the full trace again.
- After resolving errors, compact to remove the error-resolution noise from context. The resolution is valuable; the failed attempts are noise.

## The MCP Trap

Model Context Protocol (MCP) tools that return large JSON payloads consume disproportionate amounts of the context window. A single MCP call that returns 500 lines of JSON eats the same context budget as reading an entire source file. Be selective about which tools to use and filter their output to only what is needed.

Strategies for managing MCP context cost:

- Use tools that support filtering or pagination. Request only the fields you need, not the full response.
- Process tool output immediately and discard the raw response. Summarize the relevant findings in a short statement rather than leaving the full JSON in context.
- Avoid tools that dump entire database schemas, API responses, or log files into context. If you need to explore large outputs, use a sub-agent so the raw data stays out of the parent agent's context.
- Be especially cautious with tools that return nested or recursive structures. A deeply nested JSON response with repeated schema information is mostly noise.

## When to Use This

- When running any agent-driven development workflow. Context management applies to every agent interaction, not just complex tasks.
- When an agent's output quality has noticeably declined during a long conversation. Compact and restart.
- When planning a multi-step task. Estimate context budget and decompose accordingly before starting.
- When debugging agent misbehavior. Often the root cause is not a bad prompt but a polluted context.

## Red Flags to Watch For

- **Long-running agents without compaction**: Any agent conversation that exceeds 40% context utilization without compaction is producing degraded output.
- **Reusing agents across tasks**: The old task's context pollutes the new task's output.
- **Vague compaction summaries**: A summary that does not include specific file paths, line numbers, and concrete findings loses critical information across the compaction boundary.
- **MCP tools dumping large payloads**: Check what tools are putting into context. A single verbose tool can consume the entire smart zone.
- **Correcting an agent repeatedly in the same conversation**: Each correction makes the trajectory worse. After two corrections, compact and restart with a better prompt.
- **No sub-agent usage for exploration**: If the parent agent is reading dozens of files to answer a question, that exploration should be delegated to a sub-agent.
