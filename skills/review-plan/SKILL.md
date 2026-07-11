---
name: review-plan
description: Use when the user wants to stress-test, critique, or pressure-check a plan document — catch blind spots, missing steps, and unstated assumptions. Triggers on "review my plan", "stress-test the plan", "critique this plan", "what am I missing", "expert review of the plan", or "/review-plan". Runs structured expert critique, best-practice research, and optional fresh-context subagent review.
argument-hint: "[file:path] [role:\"...\"] [focus:dimension] [depth:quick|standard|deep] [dryrun] [help]"
allowed-tools: ["Read", "Glob", "Grep", "Write", "Edit", "Bash", "Agent", "WebSearch", "WebFetch"]
---
# Plan Review

*v1.3 — Stress-test a plan with structured expert critique, best-practice research, and parallel fresh-context subagent review*

Stress-test a plan with structured expert critique, web research on best practices, and a revised version if needed. Use after developing a plan, or on any plan file. Catches blind spots, missing steps, and wishful thinking.

## Instructions

### Step 0: Pre-checks

Parse `$ARGUMENTS` for flags. **If `$ARGUMENTS` is `help`, print the table below and stop.**

| Flag | Syntax | Default | Purpose |
|------|--------|---------|---------|
| Help | `help` | — | Show this options table and stop |
| File path | `file:path` | Auto-detect | Explicit plan location |
| Expert role | `role:"..."` | Auto-detect | Override persona |
| Focus area | `focus:dimension` | All dimensions | Weight one dimension (e.g. `focus:feasibility`) |
| Depth | `depth:quick/standard/deep` | `standard` | Web research intensity + review mode (`quick` = inline review, no subagent fan-out) |
| Quick | `quick` | Off | Shorthand for `depth:quick` |
| Dry run | `dryrun` | Off | Show role + research plan only |

### Step 1: Locate and Read the Plan

Four-tier priority:
1. **Explicit file** — `file:path/to/plan.md` argument
2. **Project-local plans** — search for `plan*.md` files in the current project's `notes/`, `plans/`, or `pap/` subdirectories (including additional working directories). Prefer the most recently modified match.
3. **Plan-mode file** — most recent file in `~/.claude/plans/`
4. **Conversation history** — scan the current session for the plan

If no plan found:
> "No plan found. Usage: `/review-plan` (after plan mode) or `/review-plan file:path/to/plan.md`"

**Announce the resolved source before doing anything else.** When the plan was auto-detected (tier 2, 3, or 4), state it in chat before Step 2, so a wrong match is caught before any research or subagent cost is spent:
> "**Plan under review:** `path/to/plan.md` (auto-detected; pass `file:` to override)"

For tier 4, say "plan from this conversation" instead of a path. Then proceed without waiting; the user can interrupt if the match is wrong.

### Step 2: Assign Expert Role

Infer the domain from plan content:

| Domain signals | Assigned role |
|---------------|---------------|
| skill, command, agent, MCP, Claude Code | AI engineering and skill design specialist |
| proposal, grant, funder, budget | Grant strategy and research funding specialist |
| paper, manuscript, identification, regression | Academic research methodology specialist |
| project management, tracker, workflow, dashboard | Operations and project management specialist |
| data, analysis, pipeline, code, replication | Data science and reproducibility specialist |
| Default (no strong signal) | Strategic planning and implementation specialist |

If `role:"..."` is provided, use that instead.

**Announce:** "**Reviewing as:** Meticulous [role]. (Override with `role:"your role"` if this doesn't fit.)"

### Step 3: Research Best Practices

Extract the plan's primary domain and approach. Build web search queries:
- Query A: "[approach] best practices [year]"
- Query B: "[domain] common pitfalls"
- Query C (deep only): "[specific methodology] implementation guide"

| Depth | Web searches |
|-------|-------------|
| `quick` | 0 — skip entirely |
| `standard` | 2 (queries A + B) |
| `deep` | 3-4 (all queries) |

Issue the searches as parallel calls in a single message (they are independent), so the round-trips overlap instead of running one at a time. Then distill into 3-5 key principles relevant to this plan.

### Step 4: Structured Review (parallel fan-out)

**Why fan out:** The 6 dimensions are independent — sequencing analysis does not depend on completeness analysis. One serial subagent reviewing all 6 makes wall-clock equal to the sum of all 6. Dispatching one subagent per dimension in a single message collapses wall-clock to the slowest single dimension, with no loss of rigor: each reviewer still sees the full plan.

**Why fresh-context review matters:** If you wrote or helped develop the plan, you carry planner bias — you're more likely to rationalize gaps than catch them. A fresh-context reviewer sees the plan cold, the way a colleague or referee would.

**Fresh-context parallel review (standard and deep depths):**
In a single message, dispatch one `Agent` call per dimension (`subagent_type="general-purpose"`) so they run concurrently. This avoids planner bias and runs the dimensions in parallel. Each per-dimension prompt contains:
- The full plan text
- The best practices distilled from Step 3
- EXACTLY ONE of the 6 dimensions below (its definition and the critic stance)
- The classification rule (Red/Yellow/Green) and the anchoring rule
- Instruction to return findings for that dimension only, in this format:

> STRENGTHS (for this dimension, if any)
> 1. [Label] — [Explanation]
> WEAKNESSES & GAPS
> [Red] [Label] — [Issue] → Fix: [Recommendation]
> [Yellow] [Label] — [Issue] → Fix: [Recommendation]
> [Green] [Label] — [Issue] → Fix: [Recommendation]

**Synthesis:** Once all subagents return, merge their findings — collect strengths, dedupe overlapping issues across dimensions, and sort by severity (Red → Yellow → Green). This consolidated set feeds Step 5. No subagent Red may be dropped or downgraded during the merge: every Red either appears in the output or is merged into a duplicate with the dedup stated ("also flagged by [dimension]"). The synthesizing agent may have helped write the plan, and silently softening Reds is the channel through which planner bias re-enters an otherwise fresh-context review.

**Inline review (`quick` depth, or fallback):**
At `depth:quick`, skip the fan-out entirely and perform the review inline across all 6 dimensions using the critic stance below; the subagent fan-out is where most of the time and token cost sits, so a quick run that keeps it is not quick. Also use the inline path if subagent dispatch isn't available or any per-dimension dispatch fails.

**CRITIC STANCE:**
> You are now the critic, not the planner. Do not rationalize. Your job is to find what's missing, what will break, and what's wishful thinking.

Review against 6 dimensions:

**1. Pre-mortem** — "It's 3 months later and this plan failed. What were the top 3 causes?"

**2. Completeness** — What's missing that a domain expert would expect?

**3. Feasibility** — Are there steps that depend on unconfirmed resources or approvals?

**4. Best-practice alignment** — How does this compare to standards from Step 3?

**5. Sequencing** — Are there hidden blockers? Would reordering reduce risk?

**6. Specificity** — Could someone unfamiliar execute each step?

**Classify findings:**
- **Red** — Critical. Will likely cause failure if unaddressed.
- **Yellow** — Important. Creates risk but plan can proceed.
- **Green** — Minor. Nice-to-have improvement.

**Anchoring rule (subagent and inline paths alike):** every Red or Yellow finding must name or quote the specific plan step or section it concerns; a finding about an omission must state "absent from plan". A finding that cannot be anchored this way is not reportable: unanchored critique is how generic, plausible-sounding filler enters a review.

### Step 5: Generate Output

**Verdict rule (deterministic):** any Red finding → REVISE; no Reds → APPROVE. Yellows and Greens inform the rationale but never force REVISE on their own. Do not weigh or re-judge; the classification already happened in Step 4.

```
PLAN REVIEW — [Plan Title]

Reviewing as: Meticulous [role]
Plan source: [file / plan mode / conversation]
Depth: [quick / standard / deep]

BEST PRACTICES CONTEXT
[3-5 key principles from research]

STRENGTHS
1. [Label] — [Explanation]

WEAKNESSES & GAPS
[Red] [Label] — [Issue] → Fix: [Recommendation]
[Yellow] [Label] — [Issue] → Fix: [Recommendation]
[Green] [Label] — [Issue] → Fix: [Recommendation]

VERDICT
APPROVE — [Rationale]
  OR
REVISE — [Rationale]. See revised plan below.

REVISED PLAN (only if REVISE)
[Full revised plan with [CHANGED] and [NEW] markers]
```

### Step 6: Iteration Gate

Ask: "Apply these revisions? Or provide feedback to refine further."

## Examples

```
/review-plan
/review-plan file:~/Documents/project-plan.md
/review-plan quick
/review-plan depth:deep focus:feasibility
/review-plan role:"clinical trial design specialist" file:~/project/trial-plan.md
```
