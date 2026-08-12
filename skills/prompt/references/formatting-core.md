# Prompt Formatting Core — Shared Reference

*v2.0 — Shared formatting rules, depth calibration, and tool routing for the /prompt family*

---

## Formatting Elements

When formatting a prompt, apply these elements as appropriate (not all are needed for every prompt):

- **Role/persona** — auto-select from `roles.md` based on task signals. Include only when specialized expertise sharpens the output. Omit for trivial tasks.
- **Task** — stated clearly in 1-2 sentences (always include)
- **Context** — relevant background the model needs
- **Constraints** — length, tone, format, what to avoid
- **Output format** — specify structure (bullets, table, sections, etc.)
- **Bookend pattern** — restate the key instruction at the end if the prompt is long
- **Examples** — include only if they would reduce ambiguity (try zero-shot first)

**Scaling rule:** Match formatting complexity to task complexity, not to the
length of the user's dictation. A short request about a multi-file project,
comparison, diagnosis, or design still needs enough context, paths, constraints,
and output structure to be executable. Light prompts may stay short; Standard
and Deep prompts should normally expose `Context`, `Task`, `Constraints`, and
`Output` when those fields carry distinct information.

---

## Depth Calibration

Before formatting, assess how much depth this task needs. **Default to Light** (format only). Depth injection is additive, not automatic.

### Heuristic

| Level | When to use | User override |
|-------|-------------|---------------|
| **Light** | Default. Quick replies, simple lookups, routine tasks, short emails | `depth:light` |
| **Standard** | Analysis, research, writing, or design where output quality depends on rigor | `depth:standard` |
| **Deep** | High stakes: methodology, identification strategy, grant proposals; or when user explicitly asks for thoroughness | `depth:deep` |

### Escalation signals (upgrade from Light)

- Task involves synthesis, analysis, or original argument → **Standard**
- Task requires reading local files, comparing versions, tracing producers, or classifying changes → **Standard**
- Task involves research design, causal inference, or policy implications → **Standard** or **Deep**
- Words like "comprehensive," "thorough," "rigorous" in the request → **Standard** or **Deep**
- High-stakes deliverables (pre-analysis plan, grant proposal, methodology section) → **Deep**

---

## Depth-Injection Templates

### Light (default)
No injection. Format the prompt using the elements above. Done.

### Standard — append to formatted prompt:
```
Include at the end:
- Key assumptions (2-3 bullets)
- Brief rationale for major choices
```

### Deep — append to formatted prompt:
```
Before answering:
- Research current best practices for [task domain]
- Compare your approach against established standards in [domain]
- Flag where your approach deviates and why

Include at the end:
- Key assumptions (2-3 bullets)
- Brief rationale for major choices
- What you verified and what remains uncertain
```

---

## Tool-Routing Awareness

After formatting, check whether the task is better suited to a different capability available in this environment. Available: Claude Code (default — strong at reasoning, editing, local files), Stata (via MCP for statistical work), Gmail / Google Calendar / Google Drive (via MCP), web fetch (read-only, limited). If a task requires capability not available here (e.g., heavy live-web synthesis), note the limitation in the output rather than suggesting an external tool the user does not have integrated.

**For `/prompt`**: Add a brief note before executing if a capability gap is relevant.
**For `/prompt-only`**: Note any capability gap after the code block.
**For `/prompt-refine`**: Note in the changes list if the refined prompt has a capability constraint.
