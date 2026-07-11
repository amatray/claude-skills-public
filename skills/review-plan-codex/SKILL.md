---
name: review-plan-codex
description: Use when the user wants an external second opinion on a plan from GPT-5.5 Pro via codex, or says "send the plan to GPT", "get ChatGPT to review my plan", "codex review of the plan", "external review of the plan", "second opinion on the plan from GPT-5.5", "/review-plan-codex", or wants an external GPT-5.5 critique round run as a standalone step on any plan (not just empirical Bob plans). Sandwiches an internal review-plan-auto pass, a codex/GPT-5.5 external review, and an audit of that review.
argument-hint: "[file:path] [skip-internal] [skip-final] [help]"
allowed-tools: ["Read", "Glob", "Grep", "Write", "Edit", "Bash", "Skill"]
---

# Review Plan via Codex (external second opinion)

*Unattended three-stage sandwich: internal auto-review, external GPT-5.5 review via codex, audit of the external review.*

Sends a plan to GPT-5.5 Pro for an independent critique through `codex exec` (the
`@openai/codex` CLI, routed through your ChatGPT Pro entitlement, no re-login),
then triages every external finding. It runs on ANY plan: project plans,
research plans, migrations, workflows, or Bob/GUARDRAIL empirical plans.

The external model is advisory. A confident-sounding external finding can be
wrong (already addressed, factually off, or based on missing context). Stage 3
exists so a wrong claim is rejected with a reason, never applied blindly.

## Autonomy principle (load-bearing)

This skill runs UNATTENDED. The user starts it and walks away. It must complete
all three stages and produce a final report with zero mid-run interaction.

- NEVER call AskUserQuestion or otherwise block on the user mid-run. There is no
  user watching to answer.
- The internal pre-clean ALWAYS applies its revision and ALWAYS sends the
  resulting MODIFIED plan to codex. Do not ask whether to send the modified or
  original version; the modified version is the contract.
- Apply changes automatically. Make every mutation recoverable instead of
  gated: back up before each write, keep all backups, and put the diffs and a
  one-line revert command in the final report. Recoverability replaces approval.
- The only legitimate hard stop is a fail-loud abort (codex unreachable,
  malformed codex output, detected confidential data). Abort with a clear
  message; never pause to ask a question.

## Sub-skill invocations are hard gates (load-bearing)

Two stages (Stage 1 and Stage 3.3) require invoking `review-plan-auto` as a real
sub-skill through the Skill tool. These are gates, not intents. Violating the
letter of the gate is violating the spirit: doing the equivalent critique
yourself in place of the call is the exact failure this skill exists to prevent,
because the whole value of the sandwich is an independent, iterating, multi-pass
loop that you did not hand-roll and cannot shortcut on a confidence call.

A gate is satisfied ONLY by an actual Skill-tool call to `review-plan-auto` that
records its convergence verdict in `$FIXES_FILE`. No recorded verdict means the
stage did not run, which is an automatic FAIL. If the Skill tool cannot be
called for any reason, ABORT loud (`review-plan-auto did not run: <reason>`); do
not substitute your own pass, and do not continue to the next stage.

| Rationalization | Reality |
|---|---|
| "I did the equivalent work by hand, lighter" | Not equivalent. The mandated loop iterates and checks convergence; one manual read does not. The lighter pass is the defect, not a substitute. |
| "review-plan-auto is heavy, no need to spawn it twice" | The cost is the contract. Both gates fire on every run, full stop. |
| "Risk of skipping is small / the plan already looks clean" | There is no degenerate-skip gate. Confidence and a clean-looking plan do not satisfy the gate. |
| "I flagged the deviation, per say-so-if-done-differently" | That rule reports unavoidable gaps; it never authorizes skipping a mandated step. Disclosure is not consent. |

## Confidentiality guard (non-interactive)

The plan body is uploaded to OpenAI. Because the run is unattended, this is a
detect-and-abort guard, not a question. Scan the plan for obvious confidential
markers (internal Fed data, non-public datasets, credentials, tokens, embargoed
material). If any are found, ABORT loud with what was detected and where, and
send nothing. Otherwise proceed. Starting an unattended run on a given plan is
the user's authorization to send that plan externally.

## Transport: the codex bridge

The codex transport mechanics are vendored into this skill so it runs
self-contained:

- Preflight (codex reachable + token estimate): `~/.claude/skills/review-plan-codex/scripts/codex-preflight.sh`
- Invocation, response extraction, sad-path branches, and the triage/fixes
  schema: `~/.claude/skills/review-plan-codex/references/codex-transport.md`
- Strict GUARDRAIL review prompt: `~/.claude/skills/review-plan-codex/references/codex-review-prompt-strict.md`
- Generic (non-GUARDRAIL) review prompt: `~/.claude/skills/review-plan-codex/references/generic-review-prompt.md`

Read `codex-transport.md` before Stage 2; it is the source of truth for the
codex call and the response-extraction grep.

## Stage 0: Locate the plan and set names

1. Parse `$ARGUMENTS`. If `help`, print the flag table below and stop.

   | Flag | Effect |
   |---|---|
   | `file:path` | Explicit plan location |
   | `skip-internal` | Skip Stage 1 (no pre-clean); go straight to codex |
   | `skip-final` | Skip the Stage 3 final convergence re-review |
   | `help` | Print this table and stop |

2. Locate the plan (same four-tier priority as review-plan-auto): explicit
   `file:` argument, then project `plans/` or `notes/` or `pap/` (most recent
   match), then most recent file in `~/.claude/plans/`, then conversation
   history. If none found, stop with: "No plan found. Usage:
   `/review-plan-codex file:path/to/plan.md`".

3. Derive a slug from the plan filename and set artifact paths in a sibling
   folder (keeps the plan's directory uncluttered):

   ```bash
   PLAN_DIR="$(dirname "$PLAN_PATH")"
   BASE="$(basename "$PLAN_PATH" .md)"
   OUT_DIR="$PLAN_DIR/${BASE}_codex"; mkdir -p "$OUT_DIR"
   DATE="$(date +%Y%m%d)"
   RAW_OUT="$OUT_DIR/${BASE}_codex_raw_${DATE}.txt"
   REVIEW_FILE="$OUT_DIR/${BASE}_codex_review_${DATE}.md"
   FIXES_FILE="$OUT_DIR/${BASE}_codex_fixes_${DATE}.md"
   BACKUP="$OUT_DIR/${BASE}_pre_codex_${DATE}.md"
   ```

## Stage 1: Internal pre-clean (review-plan-auto)

Skip if `skip-internal` is set.

Run the internal critique loop first so you do not spend an external round on
issues Claude can already catch. This stage ALWAYS applies and the resulting
modified plan is what proceeds to Stage 2.

1. Back up the plan first: `cp "$PLAN_PATH" "$BACKUP"`. The backup is the revert
   target named in the final report; it is what makes auto-apply safe.
2. Invoke `review-plan-auto` by **calling the Skill tool** with `file:$PLAN_PATH`.
   This is a hard gate (see "Sub-skill invocations are hard gates"), not an
   intent. Doing the equivalent critique yourself in its place ("by hand", "a
   lighter pass", "I already caught the issues") is non-conforming and
   forbidden, however confident you are or however clean the plan looks. In
   normal mode it converges and writes its revision to `$PLAN_PATH` in place;
   let it. Record `review-plan-auto: INVOKED` plus its convergence verdict in
   `$FIXES_FILE` as proof-of-execution. A Stage 1 with no recorded verdict is an
   automatic FAIL. If the Skill tool cannot be called, ABORT loud
   (`review-plan-auto did not run: <reason>`); do not substitute your own review
   and do not proceed to Stage 2.
3. Do NOT ask the user whether to keep the revision. The now-modified
   `$PLAN_PATH` is the Stage 2 input unconditionally. Record the diff
   (`$BACKUP` vs `$PLAN_PATH`) for the final report so the user can inspect or
   revert after the run.

## Stage 2: External review via codex

### 2.1 Preflight (gate)

```bash
bash ~/.claude/skills/review-plan-codex/scripts/codex-preflight.sh "$BASE" "$PLAN_PATH"
```

If exit code is non-zero (codex unreachable or plan missing), STOP and surface
the preflight stderr verbatim. Do not fall back silently. Fail loud: tell the
user codex is unreachable and what to do (`npm install -g @openai/codex@latest`,
then `codex login`).

If `TOKEN_ESTIMATE` exceeds ~150k, warn the user the plan is large and ask
whether to proceed or trim, per `codex-transport.md` sad-path test 13.

### 2.2 Choose the review prompt (adaptive)

Detect whether the plan is a Bob/GUARDRAIL plan:

```bash
if grep -qE 'GUARDRAIL\[|^[[:space:]]*(threshold|assertion|ladder|escalation):' "$PLAN_PATH"; then
  PROMPT_FILE=~/.claude/skills/review-plan-codex/references/codex-review-prompt-strict.md   # strict Bob rubric
else
  PROMPT_FILE=~/.claude/skills/review-plan-codex/references/generic-review-prompt.md        # generic rubric
fi
```

Strict rubric expects GUARDRAIL blocks and 3am-executor framing; the generic
rubric uses missing-checks / fragile-assumptions / ambiguity. Both emit the same
three top-level headers so Stage 2.4 parsing is identical.

### 2.3 Build the full prompt and invoke codex

Prepend a short problem briefing so the external model starts with context; it
has zero project knowledge. Derive the briefing yourself from the plan (2-4
sentences: what this plan is, who or what executes it, what a failure looks
like). Do not leave a literal placeholder.

The codex call runs 1-3 min synchronously. The Bash tool default timeout is 2
min, so a 3-min call would be killed and misreported as a codex failure. Set an
explicit `timeout: 300000` (5 min) on this Bash call.

```bash
FULL_PROMPT="$(cat "$PROMPT_FILE")

---
Context briefing: <your 2-4 sentence briefing here>.

---
Plan to review:

$(cat "$PLAN_PATH")"

codex exec \
  --skip-git-repo-check \
  --sandbox read-only \
  "$FULL_PROMPT" < /dev/null > "$RAW_OUT" 2>&1
EXIT=$?
```

If `EXIT` != 0: codex failed. Inspect `$RAW_OUT`, surface the error, and STOP.
No async fallback (per `codex-transport.md` sad-path test 14).

### 2.4 Extract the response

Take lines between the LAST `^codex$` marker and `^tokens used$` (codex can emit
multiple scaffolding cycles; the final answer is always last):

```bash
START=$(grep -n "^codex$" "$RAW_OUT" | tail -1 | cut -d: -f1)
END=$(grep -n "^tokens used$" "$RAW_OUT" | head -1 | cut -d: -f1)
sed -n "$((START + 1)),$((END - 1))p" "$RAW_OUT" > "$REVIEW_FILE"
```

Validate the three required headers are present:

```bash
for H in "## Missing verifications" "## Potential problems" "## Unclear demands"; do
  grep -q "^$H" "$REVIEW_FILE" || { echo "FAIL: missing $H"; exit 1; }
done
```

If a header is missing, the codex output is malformed. STOP and tell the user to
retry (sad-path test 17). Do not partially proceed.

## Stage 3: Audit the external review

The external review is NOT applied as-is. Audit it.

### 3.1 Triage every finding

Build `$FIXES_FILE` using the fixes-plan schema in `codex-transport.md`.
For each external finding, assign:

- Validity: VALID (correct, not already handled), PARTIAL (right problem, wrong
  or incomplete fix), INVALID (wrong, already addressed, or missing-context).
- Confidence: HIGH / MEDIUM / LOW.

INVALID findings are dropped with a one-line justification (kept in
`$FIXES_FILE` as the audit trail). VALID and PARTIAL findings become Edit blocks
(exact old-text / new-text). LOW-confidence items are still applied if VALID or
PARTIAL, but flagged in the final report under "Low-confidence, review these"
so the user can spot-check them after the run.

If every finding is INVALID, record "Codex found no plan-fixable issues" in
`$FIXES_FILE` and skip to Stage 3.3.

### 3.2 Apply automatically (backup already exists)

The run is unattended, so apply the VALID and PARTIAL fixes directly to
`$PLAN_PATH` without asking. `$BACKUP` from Stage 1 is the revert target (if
Stage 1 was skipped, `cp "$PLAN_PATH" "$BACKUP"` before the first edit). For
each Edit block, if its old-text does not match the current plan (drift),
restore from `$BACKUP`, record the failed block in `$FIXES_FILE`, and continue
with the remaining blocks rather than aborting the whole run. The final report
lists what applied, what drifted, and the revert command.

### 3.3 Final convergence check (review-plan-auto)

Skip if `skip-final` is set or no fixes were applied.

Re-run `review-plan-auto` by **calling the Skill tool** with `file:$PLAN_PATH`
on the merged plan, to confirm the externally-driven edits did not introduce new
inconsistencies. This is a hard gate (see "Sub-skill invocations are hard
gates"), not an intent: re-reading the merged plan yourself does NOT satisfy it,
no matter how confident you are that the edits are consistent. It may revise the
plan in place; that is fine, `$BACKUP` remains the full-revert target. Record
`review-plan-auto (final): INVOKED` plus its verdict in `$FIXES_FILE`; no
recorded verdict is an automatic FAIL. If the Skill tool cannot be called, ABORT
loud rather than substituting your own read.

## Output to the user (end of run)

This is the single report the user reads after the unattended run. Include, in
this order:
1. Stage 1 outcome: applied / skipped, plus the pre-clean diff summary.
2. Codex run: model, token count, `$REVIEW_FILE` path.
3. Triage summary: N findings, breakdown VALID / PARTIAL / INVALID.
4. Fixes applied to the plan (list), any drifted blocks, and low-confidence
   items to spot-check.
5. Final convergence verdict (or skipped).
6. Revert command: `cp "$BACKUP" "$PLAN_PATH"` to undo the entire run.

State explicitly anything skipped or unverified (skipped stages, drifted blocks,
codex warnings). Do not report "done" if a stage was skipped.

## Artifacts (kept for audit trail)

- `${BASE}_codex_raw_<DATE>.txt`: raw codex stdout (extraction debugging).
- `${BASE}_codex_review_<DATE>.md`: extracted GPT-5.5 review.
- `${BASE}_codex_fixes_<DATE>.md`: triage table and proposed edits.
- `${BASE}_pre_codex_<DATE>.md`: plan backup (revert target).
