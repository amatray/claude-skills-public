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

4. **Format into a structured prompt** using the formatting elements in formatting-core.md. Match formatting complexity to task complexity: a 1-sentence ask doesn't need a 20-line prompt.

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

**Exception, plan mode**: If plan mode is active, do Phase 1 only. Show the formatted prompt, design the plan, and wait for user approval. Do not execute.

**Exception, hold**: If the user says "hold", "don't run", or "just format", do Phase 1 only.

## Clarification

Ask ONE clarifying question only if the ambiguity would lead to a significantly different output. Otherwise, make reasonable assumptions and proceed through both phases.
