---
name: prompt
description: Format an informal, conversational request into a structured prompt, then execute it. Use when user invokes /prompt with a task description.
argument-hint: "[informal request text] [depth:light|standard|deep]"
allowed-tools: ["Read", "Glob", "Grep", "Write", "Edit", "Bash", "Agent"]
---
# /prompt: Format and Execute

*v3.1: two-phase skill, format first, execute second*

Format an informal request into a structured prompt, then execute it.

## Reference Files
@./references/formatting-core.md
@./references/roles.md

## Input
$ARGUMENTS

## Phase 0: Ground the request

Use the conversation and project context already available before formatting.
When accuracy depends on local architecture, perform the minimum read-only file
inspection needed to identify the real paths, producers, constraints, and
variants. This is grounding, not execution: do not edit files or perform the
requested work yet.

Prompt detail follows task complexity, not input length. A one-sentence request
to compare decks, audit a pipeline, or modify generated files still needs the
architecture that makes the task executable.

## Why This Skill Exists

Users often dictate informal, rambling requests. This skill adds value by *reformulating* those requests into clear, structured prompts before acting on them. If you skip the reformulation and jump straight to doing the task, the skill has added zero value, since the user could have just typed the request directly. The formatted prompt is the product of Phase 1. Treat it like a deliverable, not a mental note.

## Phase 1: Format (produce visible output)

Your first job is to produce a formatted prompt and display it. Nothing else. Do not begin working on the underlying task yet.

1. **Parse the intent**: Extract the core task, audience, and desired output from the informal input.

2. **Auto-select role**: Check the request against the trigger signals in roles.md. If a role matches, include it. If none fits or the task is trivial, omit.

3. **Calibrate depth** using the heuristic in formatting-core.md:
   - **Light** (default): Format only. No depth injection.
   - **Standard**: Format + append assumptions/rationale block.
   - **Deep**: Format + append research/compare/verify block.
   - User can override with `depth:light`, `depth:standard`, or `depth:deep`.

   A task involving local files, comparison, diagnosis, design, or multiple
   steps is at least Standard. Light is for genuinely simple tasks, not merely
   short dictation.

4. **Format into a structured prompt** using the formatting elements in formatting-core.md. Match formatting complexity to task complexity, not dictation length.

   For Standard and Deep tasks, use explicit `Context`, `Task`, `Constraints`,
   and `Output` fields whenever they add information. Do not merely paraphrase
   the user's sentence. Add the local paths, classification scheme, comparison
   dimensions, and acceptance condition that make the request operational.

5. **Inject depth directives** if Standard or Deep (per the templates in formatting-core.md). For Light, skip.

6. **Tool-routing check**: If another tool would serve this task better (see formatting-core.md), add a brief note.

7. **Output the formatted prompt.** This is the deliverable of Phase 1.

   Write the line `📋 Formatted prompt:` as ordinary text. Then put the prompt itself inside exactly one fenced code block: one opening fence on its own line, the prompt text, one closing fence on its own line.

   **Fence rules. Violating these breaks the whole reply, so treat them as hard constraints:**
   - Never nest code fences. One opening fence, one closing fence, nothing else.
   - The `📋 Formatted prompt:` label goes outside the block, never inside it.
   - Close the fence before writing anything else. An unclosed fence swallows the entire rest of the response into a code block, so the user sees unwrapped monospace running off the screen.
   - If the formatted prompt must itself contain a triple-backtick fence, wrap the outer block in four backticks instead of three.

Phase 1 ends here. You have now produced visible output that the user can see and review.

---

## Phase 2: Execute

Now, and only now, execute the formatted prompt as if the user had typed it directly. Use Claude Code tools (MCP, file access, search) as needed.

A formatted prompt alone is never the final answer. In the same invocation,
perform at least one concrete Phase 2 action and report its result. For a task
requiring tools, call the first appropriate tool immediately after displaying
the prompt. For a task answerable in chat, give the substantive answer
immediately after it.

`Do not edit`, `assess first`, and similar constraints require read-only
execution; they are not permission to stop after formatting. Stop after Phase 1
only when the user explicitly asks for prompt-only output, asks you to wait, or
the active mode prohibits execution.

**Exception, plan mode**: If plan mode is active, do Phase 1 only. Show the formatted prompt, design the plan, and wait for user approval. Do not execute.

**Exception, hold**: If the user says "hold", "don't run", or "just format", do Phase 1 only.

## Failure checks

| Temptation | Correct response |
|---|---|
| "The input is short, so a one-sentence prompt is enough." | Complexity follows the task and project architecture, not dictation length. |
| "The user only asked whether I can do it." | Feasibility is the task. Inspect the relevant files and give the verdict. |
| "Do not edit means I should stop after the prompt." | Perform the requested read-only assessment and make no edits. |
| "I displayed the prompt, so the skill is complete." | Phase 2 is mandatory in the same invocation unless a real hold applies. |

Red flags: the formatted prompt merely restates the user's sentence; a local
file task names no paths or producer; the answer ends immediately after the
code block. Any red flag means stop and correct the invocation.

## Clarification

Ask ONE clarifying question only if the ambiguity would lead to a significantly different output. Otherwise, make reasonable assumptions and proceed through both phases.
