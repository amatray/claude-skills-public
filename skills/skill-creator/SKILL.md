---
name: skill-creator
description: Create new skills, modify and improve existing skills, and measure skill performance. Use when users want to create a skill from scratch, edit, or optimize an existing skill, run evals to test a skill, benchmark skill performance with variance analysis, or optimize a skill's description for better triggering accuracy.
---

# Skill Creator

The core loop (RED–GREEN–REFACTOR):

1. Decide what the skill does.
2. Write 2–3 pressure-test scenarios — the kind of prompt where a naive agent would fail or cut corners.
3. **RED**: run scenarios *without* a skill. Capture verbatim what the agent does and how it rationalizes any failures.
4. **GREEN**: draft the skill targeted at the observed failures. Don't write defenses against problems you didn't see.
5. Re-run scenarios *with* the skill. Verify behavior actually changed.
6. Review outputs with the user (qualitatively) and assertions (quantitatively).
7. **REFACTOR**: close loopholes from new rationalizations that emerge under the skill.
8. Repeat 4–7 until satisfied.
9. Optimize the description for triggering accuracy.

Why baseline first: skills get written against imagined failures and end up bloated with defenses against problems the agent would never have made. Watching the unaided baseline tells you what actually breaks — and whether the skill is needed at all. If the baseline already does the right thing, stop.

For a skill meant to save repeated explanation, step 5 also checks whether the agent still asks for information it already had.

Figure out where the user is in this loop and pick up from there. If they say "just vibe with me, skip the evals", do that — but resist skipping the baseline; it's cheap and decides whether the skill earns its existence.

---

## Creating a skill

### Capture intent

Extract from conversation history first. The user may already have given you the workflow, tools used, input/output formats, and corrections. Confirm gaps, then ask:

1. What should this skill enable Claude to do?
2. When should it trigger (user phrases, contexts)?
3. What's the expected output format?
4. Test cases worth setting up? Skills with verifiable outputs (file transforms, data extraction, code, fixed workflows) benefit from tests. Subjective skills (style, art) often don't.

Research in parallel via subagents (or inline) if useful.

When the skill is built from work just done in this conversation, separate what is reusable from the specifics of this one case (a country, a meeting, a client, a deadline). The specifics go in the project notes, not the skill: a skill built from one country's run that hard-codes that country fails on the next one.

### Settle the design

Infer these from the task and the conversation, and ask in plain chat only for what cannot be inferred. Each is decided by what a wrong answer costs the person who reads the output.

- **The no-argument run.** Define what happens when the skill is invoked with nothing: a safe default, or a fixed first question with exact wording. Never a silent guess at a missing input.
- **Failure states.** For each file, MCP server, or input the skill depends on: does it stop and say what is missing, or continue with a visible note? Continuing is right only when the gap costs the reader little. Graceful means saying what is missing, not carrying on regardless.
- **Depth levels** (light, standard, deep) only if the same user wants the same job done at two different costs and the cheaper run is still correct about what it covers. A skill with levels prints the level it ran at.
- **Checking the output.** Decide, without asking, whether the output needs a check and what kind:
  - a fixed rule (the numbers add up, every link opens the right document): a script;
  - a judgment (is the argument sound, is anything important missing): a separate reviewer agent, because the model that wrote the output tends to approve its own work;
  - neither: no check.

  Mention a script or no check in one line. A reviewer is provisional until the RED baseline: confirm it if the baseline shows the agent passing its own flawed output, drop it if not. When a reviewer is kept, tell the user in this shape:

  > This skill will hand its output to a separate reviewer before showing it to you. The reason: [the judgment being checked, in the task's words, e.g. "whether the summary claims more than the sources say"]. The same model that wrote it tends to approve its own work, so a fresh reader with no stake in the draft catches more. Cost: each run takes longer and costs more. If you would rather check it yourself, say so and I will leave the reviewer out.

  A skill with a reviewer says, in plain words: the reviewer runs every time; the skill checks that the reviewer actually saved its result; if the reviewer could not finish, the output says it was not reviewed.

### Frontmatter

Only `name` and `description` are required. Optional fields earn their place:

- `name` — kebab-case slug; must match the folder name.
- `description`: primary triggering mechanism. **Lead with when to use the skill, and name what it produces; never summarize its workflow steps.** Start with "Use when..." and list concrete triggers, symptoms, and contexts, then name the output (the findings report, the checked list, the redlined .docx). Reason: when the description lists the steps, Claude follows the description and skips reading the skill body, so the skill becomes documentation Claude ignores. Naming the output is different: it gives Claude one more phrase to match when a user asks for the thing rather than the task. Claude also undertriggers, so be a little pushy on coverage: list multiple phrasings the user might use, including indirect ones.

  ✅ Good: `Use when the user asks to audit, review, or critique an economics manuscript, or mentions checking a paper for typos, structure, or AI-generated language. Produces a findings report and a marked-up copy of the manuscript.`
  ❌ Bad: `Audits papers by running seven modules (typos, grammar, style, prose, apparatus, voice, AI patterns), then reports findings. Use when reviewing a paper.` (lists the workflow, so Claude skips the body)
- `argument-hint` — optional. Shown in `/` autocomplete (e.g. `"[path-to-file]"`, `"[--clean] [path]"`).
- `allowed-tools` — optional but load-bearing when set. Restricts which tools the skill can call. List every tool needed, including MCP tools.
- `metadata`: optional map. Do not put a version line in the skill body; version control already records every edit. A skill copied to other people's machines (a workshop copy, a published skill) carries `metadata:` with `version: "1.0"`, bumped whenever the canonical copy is re-copied, so its users can tell which copy runs.

Example:

```yaml
---
name: review-paper
description: Use when the user asks to review, audit, or critique an economics manuscript, or mentions checking a paper for argument structure, econometric specification, citation completeness, or referee objections. Produces a referee-style report.
argument-hint: "[path to .tex or .pdf]"
allowed-tools: ["Read", "Grep", "Glob", "Write", "Task"]
---
```

### Anatomy

```
skill-name/
├── SKILL.md       (required)  routing + workflow
├── gotchas.md     (optional)  failure modes the agent reads to catch itself
├── templates/     (optional)  artifacts the skill EMITS verbatim or fills in
├── references/    (optional)  prose the skill READS to understand
├── scripts/       (optional)  executable code for deterministic tasks
└── assets/        (optional)  static files used in output (icons, fonts)
```

Three loading levels:

1. **Metadata** (name + description) — always in context (~100 words).
2. **SKILL.md body**: loaded when the skill triggers. Keep SKILL.md under 500 lines and the body under about 5,000 tokens, the limits the Agent Skills specification recommends; `scripts/quick_validate.py` warns past either one. Past that, dispatch heavy content to subfolders. The signal is whether failure catalogues or worked examples are crowding out routing.
3. **Bundled resources** — loaded on demand; scripts can run without being read into context.

Decide subfolder by what the agent does with the content:

- **emit** → `templates/`  (HTML scaffold, .tex skeleton with placeholder sections, response-letter shell)
- **read to understand** → `references/`  (schemas, principles, taxonomies, worked examples, rubric criteria)
- **read to catch itself** → `gotchas.md`  (rationalization table, red-flags list, pressure-scenario failure notes)

`scripts/` and `assets/` are orthogonal to this trichotomy: executable code and static output files. The emit/read/catch distinction applies to content the agent processes as prose.

Boundary case: if the agent reads something to decide *what* to emit (a rubric it applies as a checklist), it's `references/`. If the agent copies the structure into output (a skeleton with section headers), it's `templates/`. A rubric printed verbatim is the rare both-case; file under `references/` and let the template reference it. Worked examples go in `references/` even if their structure is partially copied; templates are bare skeletons, examples are filled prose the agent learns from.

Example: a paper-audit skill with seven failure modes and three rubrics lands at SKILL.md (routing + workflow), `gotchas.md` (rationalization table, red-flags list, observed failures from testing), `references/rubrics.md` (the three rubrics the agent reads), `templates/response-letter.tex` (the skeleton the agent fills in).

For multi-domain skills, split references by variant (`references/aws.md`, `references/gcp.md`, …) and have SKILL.md route. Not every skill uses every subfolder.

Existing skills predate this anatomy and need not be migrated unless touched.

### Writing patterns

Use the imperative. Explain *why*, not just *what* — modern LLMs do better with reasoning than with rigid `MUST`s. If you're reaching for `ALWAYS` / `NEVER` in caps, reframe with the reasoning instead.

Output formats: state them as a template the model can match.

```markdown
## Report structure
Use this template:
# [Title]
## Executive summary
## Key findings
## Recommendations
```

Examples carry weight:

```markdown
**Example 1:**
Input: Added user authentication with JWT tokens
Output: feat(auth): implement JWT-based authentication
```

### Discipline-enforcing skills

For skills whose job is to make the agent *follow a rule* (not just produce an output), the agent will find loopholes under pressure. Three techniques close them. Skip this subsection for technique or reference skills, where the agent isn't tempted to cheat.

**1. Foundational sentence.** State once, early: *"Violating the letter of the rule is violating the spirit."* This single sentence cuts off the entire class of "I'm following the spirit, just not the letter" rationalization. Place it at the top of the rule section.

**2. Rationalization table.** When the agent invents excuses to skip the rule, document each verbatim with a one-line reality check. Build the table from *observed* failures during testing, not from imagination:

| Excuse | Reality |
|---|---|
| "Too simple to test" | Simple code breaks. Test takes 30 seconds. |
| "I already tested it manually" | Manual tests don't replay. Write the assertion. |
| "Tests-after achieve the same goals" | Tests-after = "what does this do?" Tests-first = "what should this do?" |

The table doesn't need to be complete on first draft. Add rows every time you catch a new rationalization in testing.

**3. Red-flags list.** A short list of warning signs the agent can self-check against, with a single hard instruction at the end:

```
## Red Flags — STOP

- Code before test
- "It's about spirit not ritual"
- "This is different because…"
- "I'll add the test after"

All of these mean: stop, start over.
```

Together: the foundational sentence forbids spirit-vs-letter arguments, the table names the excuses, the red-flags list lets the agent catch itself mid-rationalization. Without these, "always do X" gets eroded the first time the agent finds X inconvenient.

If the rationalization table or Red Flags list grows past ~15 lines combined (heuristic, not a hard limit), hoist both to `gotchas.md` and replace the inline content with: `See gotchas.md — rationalization table and red-flags list.` Reason: rationalization catalogues compound as you observe new excuses; inlining them bloats SKILL.md on every trigger.

**Deeper reading**: `references/persuasion-principles.md` covers the empirical basis (Cialdini, 2021; Meincke et al., 2025, N=28,000) for which persuasion levers — authority, commitment, scarcity, social proof, unity — actually move compliance in LLMs, and which to avoid (liking, reciprocity). Load it when writing a discipline-enforcing skill.


## Validate

After any create or modify, run:

```bash
python3 <this skill>/scripts/quick_validate.py <path/to/skill-folder>
```

`<this skill>` is the folder this SKILL.md sits in. Fix every ERROR. Report WARN lines to the user; they are recommendations (size, paths, frontmatter a strict parser misreads) and do not block. NOTE lines need no action. Edits made with the Edit or Write tool under the skills root are also validated automatically by a hook where one is installed; the command above is the route everywhere else.

## Workflow References

Two phases live in `references/` because they only fire when the author is doing that specific activity, not every time the skill triggers:

| Phase | When it runs | Reference |
|---|---|---|
| Evals (test cases, baseline RED, running, iteration loop) | Throughout the RED → GREEN → REFACTOR loop. Load BEFORE the RED baseline (you need it to write test cases and run scenarios against a no-skill agent) | `references/eval-workflow.md` |
| Description optimization | At the end, after the skill is in good shape, to tune triggering accuracy | `references/description-optimization.md` |

Load each reference when you reach that phase, then follow its instructions verbatim. The authoring guidance inline above (capture intent, frontmatter, anatomy, writing patterns, discipline-enforcing skills) covers the *what to write*; `eval-workflow.md` covers the *how to test*.


---

## Package and present

If the `present_files` tool is available:

```bash
python -m scripts.package_skill <path/to/skill-folder>
```

Point the user at the resulting `.skill` file. Skip this step if `present_files` isn't available.

---

## Claude.ai

Same loop (draft → test → review → improve → repeat), but no subagents:

- **Test cases**: run each in series yourself by reading SKILL.md and following its instructions. Less rigorous (you wrote it and you're running it), but a useful sanity check. Skip baselines.
- **Reviewing**: no browser → present results inline. For file outputs (.docx, .xlsx), save to filesystem and tell the user where. Ask "How does this look?" inline.
- **Benchmarking**: skip — without baselines, the numbers aren't meaningful.
- **Description optimization**: skip — needs `claude -p` from Claude Code.
- **Blind comparison**: skip — needs subagents.
- **Packaging**: works anywhere with Python and a filesystem.

### Updating an existing skill

- **Preserve the original name** (directory and frontmatter `name`). Don't append `-v2`.
- **Copy to a writeable location before editing** (installed paths may be read-only). Work in `/tmp/skill-name/`, package from the copy.
- **Building is not publishing.** When the skill lives in a folder that syncs or publishes (a shared skills repository, a plugin), build in the scratch copy and move the result in, in one step, only once the user has approved it. Otherwise every intermediate state is published.
- **An ignored instruction is not fixed with more instructions.** Before adding an instruction, check whether the skill already had one the agent did not follow. If it did, move that rule into a script or a hook, which run every time, rather than writing it again in prose.
- If packaging manually, stage in `/tmp/` first, then move to the output directory.
- **Check for hoist candidates.** If the skill has a Red Flags or rationalization-table section inline and those lines exceed 15 combined, propose hoisting them to `gotchas.md` per the threshold in Anatomy. State the current line count and the proposed split before editing.

---

## Cowork

- Subagents available — the main parallel workflow works. If timeouts hit, fall back to serial runs.
- No display: pass `--static <output_path>` to `generate_review.py` to produce a standalone HTML file the user can open.
- **Generate the eval viewer before doing any qualitative review yourself.** Get the outputs in front of the user first.
- Feedback: "Submit All Reviews" downloads `feedback.json`. Read from the downloaded location.
- Packaging works.
- Description optimization works (`run_loop.py` uses `claude -p` via subprocess, no browser). Save it for the end, after the skill is in good shape.

---

## Advanced: blind comparison

Optional. For "is the new version actually better?", give two outputs to an independent agent without telling it which is which, let it judge, then analyze why the winner won. See `agents/comparator.md` and `agents/analyzer.md`. Most users won't need this.

---

## Reference files

- `agents/grader.md` — evaluating assertions against outputs
- `agents/comparator.md` — blind A/B comparison
- `agents/analyzer.md` — analyzing why one version beat another
- `references/eval-workflow.md` — test cases, baseline, running and evaluating, iteration loop
- `references/description-optimization.md` — 4-step description optimizer loop
- `references/schemas.md` — JSON structures for `evals.json`, `grading.json`, `benchmark.json`
- `references/persuasion-principles.md` — empirical basis (Cialdini; Meincke et al., 2025) for the discipline-enforcement levers
- `references/testing-skills-with-subagents.md` — pressure-scenario design, pressure-type taxonomy, meta-testing, worked bulletproofing example

For Anthropic's official skill-authoring guide (degrees-of-freedom framing, conciseness rules), see <https://github.com/obra/superpowers/blob/main/skills/writing-skills/anthropic-best-practices.md> or the upstream <https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview>. Not mirrored locally — too large, mostly duplicative of this skill.
