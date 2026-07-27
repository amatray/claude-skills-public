---
name: review-plan-auto
description: Use when the user wants automated iterative plan review with convergence detection (multiple review passes without manual approval between iterations) OR wants to audit a plan's adversarial-agent contract (check that Adversary, Verifier, audit-readiness, or determinism agents are wired always-on, not conditionally gated). Triggers on "auto-review the plan", "iterate on plan review", "review my plan thoroughly", "keep reviewing until it's tight", "/review-plan-auto", "$review-plan-auto", "check whether my adversarial agents will actually fire", "audit how the plan wires the Adversary", "stress-test the safety machinery in my plan", "is this plan safe for an overnight run", "verify the plan's adversarial-agent contract", "make sure the Adversary in this plan is not just a deterministic check", or any case where the user would otherwise run `/review-plan` repeatedly.
argument-hint: "[file:path] [role:\"...\"] [focus:dimension] [depth:quick|standard|deep] [max:N] [dryrun] [help]"
allowed-tools: ["Read", "Glob", "Grep", "Write", "Edit", "Bash", "Agent", "Workflow", "WebSearch", "WebFetch"]
---
# Automated Plan Review

*v2.1 (contract `review-plan-auto/2.1`): iterative plan review with convergence-based stopping. One parallel review pass finds issues, one revision fixes them, then cheap verification passes confirm the fixes and stop. The loop, scoring, guards, and all verbatim review text are a deterministic program in `scripts/review-loop.js`; agents only critique, revise, and verify. ONE SKILL.md serves both Claude Code and Codex: Claude runs the loop through the `Workflow` tool, Codex runs the SAME loop file through `scripts/codex-harness.mjs`, so behavior cannot drift between runtimes.*

Runs the structured plan critique loop automatically until the plan has no confirmed critical issues. Fresh-context reviewers avoid planner bias (except at `depth:quick`, which reviews inline). Verification passes check prior findings rather than re-reviewing from scratch, which is what lets the loop terminate: a review pass that hunts fresh gaps in freshly revised text always finds some, so gap-hunting is confined to pass 1.

**Parity note:** the flag table, plan-location tiers, role table, research queries, review dimensions, classification, and anchoring rule are mirrored with `review-plan/SKILL.md`. The single source of truth for the review dimensions, classification, anchoring rule, reviser constraint, execution-mode paragraph, defaults, exit enum, and convergence mapping is the non-exported `const contract` in `scripts/review-loop.js`; the prose copies below (needed for the inline and fallback paths, which do not run the loop file) must be kept in step with it. When editing any shared section, apply the same edit to `const contract` and to `review-plan/SKILL.md`.

## Instructions

### Step 0: Pre-checks

Parse `$ARGUMENTS` for flags. **If `$ARGUMENTS` is `help`, print the table below and stop.**

| Flag | Syntax | Default | Purpose |
|------|--------|---------|---------|
| Help | `help` | (none) | Show this options table and stop |
| File path | `file:path` | Auto-detect | Explicit plan location |
| Expert role | `role:"..."` | Auto-detect | Override persona |
| Focus area | `focus:dimension` | All dimensions | Weight one dimension (e.g. `focus:feasibility`) |
| Depth | `depth:quick/standard/deep` | `standard` | Web research intensity + review mode (`quick` = inline critique, no fan-out) + reviewer effort (`standard` = medium, `deep` = high) |
| Quick | `quick` | Off | Shorthand for `depth:quick` |
| Max passes | `max:N` | `4` | Hard cap on passes (pass 1 reviews and revises; passes 2..N verify and re-revise) |
| Dry run | `dryrun` | Off | Show role + research plan only |

### Step 1: Locate and Read the Plan

Four-tier priority:
1. **Explicit file**: `file:path/to/plan.md` argument
2. **Project-local plans**: search for `plan*.md` files in the current project's `notes/`, `plans/`, or `pap/` subdirectories (including additional working directories). Prefer the most recently modified match.
3. **Plan-mode file**: most recent file in `~/.claude/plans/` (Claude) or `~/.codex/plans/` (Codex); check both.
4. **Conversation history**: scan the current session for the plan

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

The execution-mode paragraph passed to reviewers lives in `const contract.modeInstruction`. For `autonomous-execution`, pass `modeInstruction: ""` in Step 4; for `human-in-the-loop`, omit the arg so the loop uses the contract default (this is the human-in-the-loop paragraph). The inline and fallback paths (which do not run the loop file) use this text directly:

> A person executes and approves each step of this plan, operating under standing house rules (explicit approval before anything ships, storage conventions, style and verification rules). Absence of process or governance machinery (owners, monitoring windows, incident procedures, storage policy, approval workflows, measurement schemes) is NOT a finding unless the plan text contradicts a standing rule. Review the substance instead: are the claims correct and verifiable, is each deliverable feasible, is the sequencing sound.

### Step 3: Research Best Practices

Extract the plan's primary domain and approach. Build search queries:
- Query A: "[approach] best practices [year]"
- Query B: "[domain] common pitfalls"
- Query C (deep only): "[specific methodology] implementation guide"

| Depth | Web searches |
|-------|-------------|
| `quick` | 0 (skip entirely) |
| `standard` | 2 (queries A + B) |
| `deep` | 3-4 (all queries) |

Use the runtime's web search (Claude `WebSearch`, or Codex native search). If web search is unavailable, skip research and disclose it in the final summary; never invent citations. Issue the searches as parallel calls in a single message (they are independent). Then distill into 3-5 key principles relevant to this plan. These are passed to the reviewers once; there is no repeat research.

### Step 4: Automated Review Loop

At `depth:quick`, skip to the **Inline path** below.

**Build `activeDimensionKeys` first (both runtimes).** Start with the seven always-active keys: `pre-mortem`, `completeness`, `feasibility`, `best-practice`, `sequencing`, `specificity`, `proportionality`. Add `adversarial-agent-contract` only when the plan mentions any of: Adversary, Verifier, audit-readiness, determinism, sensitivity, robustness (agent). Dimension selection has exactly one owner (this list); the loop maps each key to its verbatim definition in `const contract`.

**Announce:** "Running the review loop (up to [max] passes: review, revise, then verification cycles). Will stop as soon as all Red findings verify as fixed."

Assemble these run-specific args (the verbatim dimension, classification, anchoring, reviser, and mode text all come from `const contract`, so they are NOT passed per run):

| args field | Value |
|---|---|
| `plan` | The full plan text from Step 1 |
| `role` | The role sentence from Step 2 (e.g. "Meticulous AI engineering and skill design specialist") |
| `activeDimensionKeys` | The array built above |
| `principles` | The distilled 3-5 principles from Step 3, as one string (`""` if research was skipped) |
| `focus` | The `focus:` flag value, or `null` |
| `maxPasses` | The `max:` flag value (omit to use the contract default, 4) |
| `reviewEffort` | `"medium"` at `depth:standard`, `"high"` at `depth:deep` |
| `modeInstruction` | `""` for `autonomous-execution`; omit for `human-in-the-loop` |

Then run the loop by the **runtime ladder**:

- **Claude Code (Workflow available):** invoke the `Workflow` tool with `scriptPath` set to `<this skill's base directory>/scripts/review-loop.js` and `args` set to the object above. The workflow runs in the background; wait for its completion notification, then use its return value in Step 5. Do not dispatch any review agents yourself while it runs. If the workflow returns `status: "error"` or the return value is unusable, fall back to the **Fallback path**.
- **Codex (no Workflow tool):** write the args object to `args.json`, then run `node <this skill's base directory>/scripts/codex-harness.mjs args.json out.json` and read `out.json`. The parent Codex session MUST be unsandboxed (launched with `--dangerously-bypass-approvals-and-sandbox`), or the harness's nested `codex exec` children cannot start under the OS sandbox; the harness fires a preflight probe and fails fast with this remedy. If the parent is sandboxed and cannot be relaunched, use the pivot: the parent writes `args.json` and the user runs the harness command in a plain (non-Codex) shell, then hands back `out.json`. On any harness failure, fail loud naming the failing path; do NOT fall back to an inline review.
- **Neither tool present:** fail loud naming the missing runtime primitive.

The loop owns the mechanics deterministically: it fans all dimension reviewers out in one `parallel()` call, merges findings by label in code (plus one cheap clustering agent when more than 8 findings survive), dispatches one coherent revision agent (if fixing everything would blow the size cap, it retries with Reds only and defers the Yellows to the report), then runs verification passes in which each dimension's verifier checks only its own prior findings and may add new Reds only for failure modes the revision introduced. It stops on: converged, churn, inflation (a revision over 1.25x the original line count, with a 30-line headroom floor), or the hard cap.

**Inline path (`depth:quick`):** perform the full-dimension critique inline across all active dimensions, then one inline revision honoring the reviser constraint and the 1.25x inflation cap. Use this critic stance:
> You are now the critic, not the planner. Do not rationalize. Your job is to find what's missing, what will break, and what's wishful thinking.

**Fallback path (Claude only; Workflow tool unavailable or failed):** dispatch one `Agent` call (`subagent_type="general-purpose"`) per active dimension, all batched in one message, each given the same prompt content the loop assembles (role, critic stance, mode instruction, principles, one dimension, classification, anchoring, plan). Then merge findings (no Red dropped or downgraded), dispatch one revision agent under the reviser constraint, and run one batched verification round with the same rules. Apply the same exit conditions and the 1.25x cap by hand. (There is no inline fallback on the Codex path: a harness failure is reported, not worked around.)

**The 8 review dimensions** (verbatim definitions live in `const contract.dimensions`):

1. **Pre-mortem**: "It's 3 months later and this plan failed. What were the top 3 causes?"
2. **Completeness**: What's missing that a domain expert would expect?
3. **Feasibility**: Are there steps that depend on unconfirmed resources or approvals?
4. **Best-practice alignment**: How does this compare to standards from the research?
5. **Sequencing**: Are there hidden blockers? Would reordering reduce risk?
6. **Specificity**: Could someone unfamiliar execute each step?
7. **Adversarial-agent contract**: Conditional, fires only when the plan mentions Adversary / Verifier / audit-readiness / determinism / sensitivity / robustness agents. The reviewer must Read `~/.claude/preferences/adversarial-agent-contract.md` and apply its full detection patterns and contract requirements; flag as violations: conditional-gating language near an agent spec without a sibling `cannot_do_job:` block, a missing closed `slo_enum` declaration or `role_invocation_audit.json` emission, missing task-specific cost-benefit push-back, and any undeclared dispatch mode or documented fallback. Each violation is a [Red] [Plan-fixable] issue. If the plan mentions none of the trigger terms, this dimension is not dispatched.
8. **Proportionality**: Always on; the counterweight to the gap-finding dimensions, which can only ever push a plan to grow. What in this plan is more process than its stakes justify? Flag as findings: sections whose deletion would not change the outcome, restatements of rules the standing environment already enforces, and machinery (gates, state machines, role tables, owners, measurement windows) that serves no named failure mode. Over-engineering findings are classified Red/Yellow plan-fixable, and their fix is deletion or tightening, never addition.

**Classification instruction:**

> For each issue found, classify its **fixability** alongside its severity:
> - **[Plan-fixable]**: The plan text can be revised to address this (add a step, clarify a section, reorder, add a contingency).
> - **[Upstream]**: This issue originates outside the plan: inconsistent naming conventions, input data format mismatches, tool configuration problems, missing upstream decisions, or infrastructure constraints. Revising the plan cannot fix the root cause. Do NOT generate fix recommendations for upstream issues.
> - **[Decision-pending]**: The issue concerns a choice the plan explicitly leaves open for the user (a section titled "Open decisions", "Open questions", or equivalent). An open decision is a feature of the plan, not a gap: report it, but do NOT generate a fix, and do NOT propose process machinery to manage the openness.

**Anchoring rule:** every Red or Yellow finding must name or quote the specific plan step or section it concerns; a finding about an omission must state "absent from plan". A finding that cannot be anchored this way is not reportable: unanchored critique is how generic, plausible-sounding filler enters a review.

**Reviser constraint:**

> Fix only the listed findings. Never add a section, gate, state machine, role table, owner assignment, or measurement scheme that no listed finding names. Prefer deleting or tightening over adding. When a fix can be a sentence, it is not a subsection. Leave sections marked as open decisions untouched.

### Step 5: Generate Final Summary

**Plan-mode behavior:** When in plan mode, write only the final plan (`finalPlan`) to the plan file. Display the convergence trajectory and upstream issues inline.

**Normal mode:** If the plan source is a file, write `finalPlan` to the file.

Render the summary from the loop's return value using the skeleton in `templates/final-summary.md`. The plan-size line and the DECISION-PENDING section are always filled in; FINDINGS NOT APPLIED appears only when `notApplied` is non-empty; the CHURN REPORT appears only when the exit reason names churn.

**Then always emit the machine-parseable verdict line** as the LAST line of the final message (skip only for `help` and `dryrun`), per `const contract.convergence`:

```
CONVERGENCE: verdict=<APPROVE|REVISE> exit=<approve|clean|churn|inflation|hard-cap|error> score=<N> passes=<K>/<MAX>
```

- `verdict` = APPROVE iff `exit` is `approve` or `clean`, else REVISE.
- `exit` is keyed on the return's `status` + `exitReason` prefix: `converged`+`Approved`→`approve`; `converged`+`Converged`→`clean`; `converged`+`Revision applied without verification`→`clean`; `stopped`+`Churn detected`→`churn`; `stopped`+`Inflation detected`→`inflation`; `stopped`+`Hard cap reached`→`hard-cap`; `stopped`+`Revision agent failed`→`error`; `status: "error"` or any unmapped pair →`error` (quote the raw `exitReason` in the summary).
- `score` = the last `passHistory` entry's score; `passes` = `passHistory.length`/`maxPasses`.

**Name any failed reviewers or verifiers.** On the Codex path, list every entry in `out.json`'s `calls` array with `outcome: "failed"` (a reviewer/verifier dimension whose structured output never validated). On the Claude path, name any dimension whose agent failed. Partial coverage is reported, never silent (Hard Rule 12).

## Examples

```
/review-plan-auto
/review-plan-auto file:~/Documents/project-plan.md
/review-plan-auto max:2
/review-plan-auto depth:deep max:4 focus:feasibility
/review-plan-auto quick
/review-plan-auto role:"clinical trial design specialist" file:~/project/trial-plan.md
```
