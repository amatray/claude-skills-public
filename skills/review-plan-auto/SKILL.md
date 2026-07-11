---
name: review-plan-auto
description: Use when the user wants automated iterative plan review with convergence detection (multiple review passes without manual approval between iterations) OR wants to audit a plan's adversarial-agent contract (check that Adversary, Verifier, audit-readiness, or determinism agents are wired always-on, not conditionally gated). Triggers on "auto-review the plan", "iterate on plan review", "review my plan thoroughly", "keep reviewing until it's tight", "/review-plan-auto", "check whether my adversarial agents will actually fire", "audit how the plan wires the Adversary", "stress-test the safety machinery in my plan", "is this plan safe for an overnight run", "verify the plan's adversarial-agent contract", "make sure the Adversary in this plan is not just a deterministic check", or any case where the user would otherwise run `/review-plan` repeatedly.
argument-hint: "[file:path] [role:\"...\"] [focus:dimension] [depth:quick|standard|deep] [max:N] [dryrun] [help]"
allowed-tools: ["Read", "Glob", "Grep", "Write", "Edit", "Bash", "Agent", "WebSearch", "WebFetch"]
---
# Automated Plan Review

*v1.2 — Iterative plan review with convergence-based stopping, deterioration detection, and upstream-fix classification. Each pass fans out the dimensions across parallel subagents, then generates one coherent revision*

Runs the structured plan critique loop automatically (up to N passes) until the plan has no critical issues. Each pass uses fresh-context subagents to avoid planner bias (except at `depth:quick`, which reviews inline). Detects circular changes and surfaces issues that belong upstream rather than in the plan.

**Parity note:** the flag table, plan-location tiers, role table, research queries, review dimensions, classification, and anchoring rule are mirrored with `review-plan/SKILL.md`. When editing any shared section, apply the same edit to the other skill.

## Instructions

### Step 0: Pre-checks

Parse `$ARGUMENTS` for flags. **If `$ARGUMENTS` is `help`, print the table below and stop.**

| Flag | Syntax | Default | Purpose |
|------|--------|---------|---------|
| Help | `help` | — | Show this options table and stop |
| File path | `file:path` | Auto-detect | Explicit plan location |
| Expert role | `role:"..."` | Auto-detect | Override persona |
| Focus area | `focus:dimension` | All dimensions | Weight one dimension (e.g. `focus:feasibility`) |
| Depth | `depth:quick/standard/deep` | `standard` | Web research intensity + review mode (`quick` = inline critique, no subagent fan-out) |
| Quick | `quick` | Off | Shorthand for `depth:quick` |
| Max passes | `max:N` | `4` | Hard cap on automated passes |
| Dry run | `dryrun` | Off | Show role + research plan only |

### Step 1: Locate and Read the Plan

Four-tier priority:
1. **Explicit file** — `file:path/to/plan.md` argument
2. **Project-local plans** — search for `plan*.md` files in the current project's `notes/`, `plans/`, or `pap/` subdirectories (including additional working directories). Prefer the most recently modified match.
3. **Plan-mode file** — most recent file in `~/.claude/plans/`
4. **Conversation history** — scan the current session for the plan

If no plan found:
> "No plan found. Usage: `/review-plan-auto` (after plan mode) or `/review-plan-auto file:path/to/plan.md`"

Record the plan source (file path or "conversation") for the final summary.

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

### Step 2b: Execution-Mode Calibration

Classify who executes the plan. This sets the review posture and is as load-bearing as the role: the same critique dimensions applied with the wrong posture inflate a small plan into project-management scaffolding.

| Execution mode | Signals | Posture |
|---|---|---|
| `autonomous-execution` | An agent or machine runs the plan text unattended (Bob, overnight runs, pipelines, batch jobs); the plan text is the only carrier of safeguards | Full rigor: missing checks, gates, and escalation paths are real gaps |
| `human-in-the-loop` | A person executes or approves each step (content, comms, events, teaching, writing, outreach); standing house rules (approval gates, storage conventions, style and verification rules) already govern execution | Parsimony: the plan's job is substance, not governance |

Default to `human-in-the-loop` when no agent, pipeline, or unattended run is named in the plan.

**Announce** the mode alongside the role: "**Execution mode:** [mode]."

For `human-in-the-loop` plans, include this instruction in every critique prompt (subagent and inline alike):

> A person executes and approves each step of this plan, operating under standing house rules (explicit approval before anything ships, storage conventions, style and verification rules). Absence of process or governance machinery (owners, monitoring windows, incident procedures, storage policy, approval workflows, measurement schemes) is NOT a finding unless the plan text contradicts a standing rule. Review the substance instead: are the claims correct and verifiable, is each deliverable feasible, is the sequencing sound.

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

Issue the searches as parallel calls in a single message (they are independent), so the round-trips overlap instead of running one at a time. Then distill into 3-5 key principles relevant to this plan. These are reused across all passes (no repeat research).

### Step 4: Automated Review Loop

**Announce:** "Running up to [max] automated review passes. Will stop earlier if no critical issues remain or if diminishing returns are detected."

**Initialize state:**
- `pass_number = 1`
- `pass_history = []` (list of {pass, score, lines, red_labels, yellow_labels, fixed, new})
- `upstream_items = []` (accumulated across passes)
- `decision_pending_items = []` (accumulated across passes)
- `current_plan = <plan text from Step 1>`
- `original_lines = <line count of current_plan>` (the inflation-guard baseline)

---

**Loop body — repeat until exit condition:**

#### 4a. Fresh-context critique (parallel fan-out)

**Why fan out:** The review dimensions are independent, so one serial subagent covering all of them makes each pass as slow as the sum of every dimension. Dispatch one subagent per dimension in a single message instead; per-pass wall-clock collapses to the slowest single dimension. The loop across passes stays sequential, since each pass needs the prior pass's revised plan.

In a single message, dispatch one `Agent` call (`subagent_type="general-purpose"`) per active dimension. Each per-dimension prompt contains:

1. The full `current_plan` text
2. The 3-5 best practices from Step 3
3. EXACTLY ONE of the dimensions below (its definition)
4. The upstream/plan-fixable classification instruction
5. Prior-pass issue summary (compact: labels + statuses only, not full critique text) so labels stay consistent across passes
6. The per-dimension critique output format
7. The anchoring rule

Dimension 7 is conditional: include its subagent only when the plan mentions Adversary / Verifier / audit-readiness / determinism / sensitivity / robustness agents. Otherwise dispatch the 7 core dimensions (1 to 6 and 8) and treat dimension 7 as "n/a". Dimension 8 is always on.

**The 8 review dimensions:**

1. **Pre-mortem** — "It's 3 months later and this plan failed. What were the top 3 causes?"
2. **Completeness** — What's missing that a domain expert would expect?
3. **Feasibility** — Are there steps that depend on unconfirmed resources or approvals?
4. **Best-practice alignment** — How does this compare to standards from the research?
5. **Sequencing** — Are there hidden blockers? Would reordering reduce risk?
6. **Specificity** — Could someone unfamiliar execute each step?
7. **Adversarial-agent contract** — Conditional, fires only when the plan mentions Adversary / Verifier / audit-readiness / determinism / sensitivity / robustness agents. In the dimension-7 subagent prompt, give the path `~/.claude/preferences/adversarial-agent-contract.md` and instruct the subagent to Read that file and apply its full detection patterns and contract requirements; flag as violations: conditional-gating language near an agent spec without a sibling `cannot_do_job:` block, a missing closed `slo_enum` declaration or `role_invocation_audit.json` emission, missing task-specific cost-benefit push-back, and any undeclared dispatch mode or documented fallback. Each violation is a [Red] [Plan-fixable] issue. If the plan does not mention any of the trigger terms, this dimension reports "n/a" and contributes nothing to the score.

8. **Proportionality**: Always on; this is the counterweight to the gap-finding dimensions, which can only ever push a plan to grow. What in this plan is more process than its stakes justify? Flag as findings: sections whose deletion would not change the outcome, restatements of rules the standing environment already enforces, and machinery (gates, state machines, role tables, owners, measurement windows) that serves no named failure mode. Over-engineering findings are classified Red/Yellow plan-fixable like any other, and their fix is deletion or tightening, never addition.

**Upstream/plan-fixable classification instruction (include in subagent prompt):**

> For each issue found, classify its **fixability** alongside its severity:
> - **[Plan-fixable]** — The plan text can be revised to address this (add a step, clarify a section, reorder, add a contingency).
> - **[Upstream]** — This issue originates outside the plan: inconsistent naming conventions across project files, input data format mismatches, tool configuration problems, missing upstream decisions, or infrastructure constraints. Revising the plan cannot fix the root cause; it must be addressed elsewhere. Do NOT generate fix recommendations for upstream issues.
> - **[Decision-pending]** — The issue concerns a choice the plan explicitly leaves open for the user (a section titled "Open decisions", "Open questions", or equivalent). An open decision is a feature of the plan, not a gap: report it so the user sees it, but do NOT generate a fix, and do NOT propose process machinery to manage the openness.
>
> Examples of upstream issues: folder names use mixed conventions (backslash vs underscore vs space), input data arrives in inconsistent formats, a dependency has not been configured yet, a decision by another team is pending.
> Examples of plan-fixable issues: a step is missing, instructions are vague, sequencing creates a hidden blocker, no contingency for a known risk.
> Examples of decision-pending issues: the plan asks the user to choose between two scopes, the plan defers a channel or sequencing choice to the user, the plan lists open questions for a later session.

**Per-dimension critique output format (each subagent returns findings for its dimension only):**

> STRENGTHS
> 1. [Label] — [Explanation]
>
> WEAKNESSES & GAPS
> [Red] [Plan-fixable] [Short-Label] — [Issue] → Fix: [Recommendation]
> [Yellow] [Upstream] [Short-Label] — [Issue] → Root cause: [Explanation]
> [Green] [Plan-fixable] [Short-Label] — [Issue] → Fix: [Recommendation]
> (Use consistent short labels across passes so issues can be tracked.)

**Anchoring rule (subagent and inline paths alike):** every Red or Yellow finding must name or quote the specific plan step or section it concerns; a finding about an omission must state "absent from plan". A finding that cannot be anchored this way is not reportable: unanchored critique is how generic, plausible-sounding filler enters a review.

**Inline critique (`quick` depth, or fallback):** At `depth:quick`, skip the fan-out entirely and perform the full-dimension critique inline (the subagent fan-out is where most of each pass's time and token cost sits, so a quick run that keeps it is not quick). Also use the inline path if subagent dispatch isn't available or any per-dimension dispatch fails. Either way, use this critic stance:
> You are now the critic, not the planner. Do not rationalize. Your job is to find what's missing, what will break, and what's wishful thinking.

#### 4a-ii. Synthesize critique

Merge the per-dimension findings into one consolidated review: collect strengths, dedupe overlapping issues across dimensions, normalize short labels against the prior-pass labels so the same issue keeps the same label, and sort by severity. No subagent Red may be dropped or downgraded during the merge: every Red either appears in the consolidated review or is merged into a duplicate with the dedup stated ("also flagged by [dimension]"). The synthesizing agent may have helped write the plan, and silently softening Reds is the channel through which planner bias re-enters an otherwise fresh-context review. Then set the verdict:
- **APPROVE** if no Red plan-fixable issues remain.
- **REVISE** otherwise.

#### 4a-iii. Generate revision (only if REVISE)

Dispatch a single `Agent` call (`subagent_type="general-purpose"`), given the full `current_plan` and the consolidated WEAKNESSES & GAPS from 4a-ii, instructed to return the complete revised plan with [CHANGED] and [NEW] markers on modified or added sections. Do not address [Upstream] or [Decision-pending] items in the revision. Keeping revision as one coherent pass (rather than fanning it out per dimension) prevents conflicting edits to the same plan sections.

Include this constraint in the reviser prompt verbatim; without it the reviser resolves findings by adding machinery, which is the channel through which small plans balloon:

> Fix only the listed findings. Never add a section, gate, state machine, role table, owner assignment, or measurement scheme that no listed finding names. Prefer deleting or tightening over adding. When a fix can be a sentence, it is not a subsection. Leave sections marked as open decisions untouched.

#### 4b. Parse results

From the synthesized critique (4a-ii) and the generated revision (4a-iii), extract:
- Red plan-fixable items (with labels)
- Yellow plan-fixable items (with labels)
- Green items (noted but not scored)
- Upstream items (with labels and root causes)
- Decision-pending items (with labels)
- Verdict (APPROVE or REVISE)
- Revised plan text (if REVISE)

#### 4c. Compute convergence score

`score = -(3 * count(Red_plan_fixable) + 1 * count(Yellow_plan_fixable))`

Upstream and Decision-pending items are excluded from the score. Neither can be fixed by plan revision and neither should drive iteration.

#### 4d. Accumulate upstream and decision-pending items

Add any new upstream and decision-pending items to their running lists. Deduplicate by semantic similarity against existing items (same root cause = same item, even if worded differently).

#### 4e. Record pass

Add to `pass_history`:
```
{
  pass: N,
  score: <computed>,
  lines: <line count of the plan this pass reviewed>,
  red_labels: [...],
  yellow_labels: [...],
  fixed_from_prev: [...],  // labels present in pass N-1 but absent now
  new_issues: [...],        // labels absent in pass N-1 but present now
  verdict: APPROVE|REVISE
}
```

#### 4f. Check exit conditions (evaluate in this order)

| # | Condition | Trigger | Exit reason |
|---|-----------|---------|-------------|
| 1 | Inflation guard | Applying this pass's revision would push the plan past `1.5 * original_lines`, or grow it by more than 40% in this single pass | Inflation detected |
| 2 | Clean exit | `count(Red_plan_fixable) == 0` | No critical issues remain |
| 3 | Subagent approves | Verdict = APPROVE | Reviewer sees no issues |
| 4 | Deterioration (churn) | Any issue label that was present in pass K, absent in pass K+1, and present again now | Circular changes detected |
| 5 | Score regression | `pass > 1` and `score` worsened by 3+ points vs. previous pass | Plan getting worse |
| 6 | Marginal improvement | `pass > 1` AND `count(Red_plan_fixable) == 0` AND score improved by 0 or 1 point | Diminishing returns |
| 7 | Hard cap | `pass_number == max` | Safety limit reached |

When the inflation guard fires: do NOT apply the offending revision. Keep the current (pre-revision) plan as the final version and carry the pass's unaddressed findings into the summary under FINDINGS NOT APPLIED, each with its suggested fix, so the user can adopt them by hand. A plan that cannot absorb its fixes within a bounded size is telling you the fixes belong in a report, not in the plan; growth without convergence is the signature failure this guard exists to stop.

Marginal improvement only fires when Red == 0. If Red items persist, the loop continues until the hard cap, deterioration, or Red items are resolved. This prevents premature stops while critical issues remain.

If an exit condition is met, proceed to Step 5.

#### 4g. Apply revision and loop

If no exit condition is met and the verdict is REVISE:
1. Take the complete REVISED PLAN output from 4a-iii
2. Replace `current_plan` wholesale (no selective merge)
3. If NOT in plan mode and the plan source is a file, write the updated plan to the file
4. Increment `pass_number`
5. Return to 4a

If synthesis ever yields APPROVE while Red items remain, override the verdict and continue the loop. Trust the score over the verdict when they disagree.

#### Budget warning

At pass `max - 1`, if convergence has not been reached, emit:
> "WARNING: Pass [N] of [max] completed. Score: [score] ([R] Red, [Y] Yellow remaining). One pass remains before hard cap."

### Step 5: Generate Final Summary

**Plan-mode behavior:** When in plan mode, write only the final revised plan to the plan file. Display the convergence trajectory and upstream issues inline (not written to any file).

**Normal mode:** If the plan source is a file, write the final plan to the file.

Output the summary using the skeleton in `templates/final-summary.md`. The plan-size line and the DECISION-PENDING section are always filled in; FINDINGS NOT APPLIED appears only when the inflation guard fired.

If the exit reason is Deterioration detected, append the DETERIORATION REPORT section from the same template.

## Examples

```
/review-plan-auto
/review-plan-auto file:~/Documents/project-plan.md
/review-plan-auto max:3
/review-plan-auto depth:deep max:5 focus:feasibility
/review-plan-auto quick max:2
/review-plan-auto role:"clinical trial design specialist" file:~/project/trial-plan.md
```
