---
name: review-plan-codex
description: Use when the user wants an external second opinion on a plan from the strongest available ChatGPT model via codex, or says "send the plan to GPT", "get ChatGPT to review my plan", "codex review of the plan", "external review of the plan", "second opinion on the plan from GPT", "/review-plan-codex", or wants a cross-model critique round run as a standalone step on any plan (not just empirical Bob plans). Codex runs the convergence loops; Claude supplies the independent critique; each model's findings are audited by the other.
argument-hint: "[file:path] [skip-internal] [skip-final] [local] [help]"
allowed-tools: ["Read", "Glob", "Grep", "Write", "Edit", "Bash", "Skill", "Agent"]
---

# Review Plan via Codex (cross-model sandwich)

*Unattended four-stage pipeline: Codex convergence loop, independent Claude
critique, Codex triage of that critique, Codex final convergence check.*

The division of labor follows one principle: **iteration is mechanical,
judgment is where model diversity pays.** The multi-pass convergence loops run
on Codex (`codex exec` against the Codex-side `$review-plan-auto` skill,
ChatGPT Pro entitlement, no per-call cost). Claude contributes exactly one
fresh-context critique of the GPT-converged plan; that is where the second
model family earns its keep. The GPT side then audits Claude's findings, so each
model's judgment is checked by the other. Claude tokens are spent only on
orchestration, the single critique pass, and edit application.

Any finding, from either model, can be wrong (already addressed, factually
off, or based on missing context). The cross-audit exists so a wrong claim is
rejected with a recorded reason, never applied blindly.

## Autonomy principle (load-bearing)

This skill runs UNATTENDED. The user starts it and walks away. It must
complete all stages and produce a final report with zero mid-run interaction.

- NEVER call AskUserQuestion or otherwise block on the user mid-run.
- Apply changes automatically. Make every mutation recoverable instead of
  gated: back up before the first write, keep all backups, and put the diffs
  and a one-line revert command in the final report. Recoverability replaces
  approval.
- The only legitimate hard stop is a fail-loud abort (detected confidential
  data, or codex unusable AND local fallback impossible). Abort with a clear
  message; never pause to ask a question.

## Stage gates (load-bearing)

Three stages are gates, not intents. Violating the letter of a gate is
violating the spirit: doing the stage's work yourself in place of the mandated
call is the exact failure this skill exists to prevent, because it silently
collapses the cross-model design back into a single model.

| Gate | Satisfied ONLY by | Proof recorded in `$FIXES_FILE` |
|---|---|---|
| Stage 1 loop | `codex exec` run of `$review-plan-auto` (or the disclosed `local` fallback) | `loop1: CODEX` + its `CONVERGENCE:` line |
| Stage 3 triage | `codex exec` run of the triage prompt (or the disclosed `local` fallback) | `triage: CODEX` + the triage table |
| Stage 4 verify | `scripts/verify-applied-fixes.py` exiting 0 | `verify: SCRIPT` + its `VERIFY:` line |

Stage 4 is a deterministic script, not a model call, so it has no `local`
fallback and cannot be satisfied by reading the plan yourself. A run where the
script was not executed has no Stage 4 proof.

Stage 2 has its own gate: the critique must come from a fresh-context Agent
dispatch, not from you reviewing inline (inline is a disclosed fallback only).

No recorded proof means the stage did not run: automatic FAIL. The `local`
fallback path is legitimate ONLY when codex is unreachable or `local` was
passed, and the final report must name every stage that fell back and why.

| Rationalization | Reality |
|---|---|
| "I can run the convergence loop myself, it's faster" | Running it on Claude is the defect: it burns the metered budget and erases the GPT-converged baseline that Stage 2 stress-tests. |
| "My findings are obviously valid, no need for GPT triage" | Self-audited findings are the failure mode. Confidence does not satisfy the gate. |
| "Codex looked flaky earlier, I'll just do it all locally" | Fallback requires an actual failed preflight or call, recorded verbatim. A hunch is not a failure. |
| "I flagged the deviation, per say-so-if-done-differently" | Disclosure is not consent. That rule reports unavoidable gaps; it never authorizes skipping a mandated call. |

## Confidentiality guard (non-interactive)

The plan body, and in Stage 3 Claude's findings, are uploaded to OpenAI.
Because the run is unattended, this is a detect-and-abort guard, not a
question. Scan the plan for obvious confidential markers (internal Fed data,
non-public datasets, credentials, tokens, embargoed material). If any are
found, ABORT loud with what was detected and where, and send nothing.
Otherwise proceed. Starting an unattended run on a given plan is the user's
authorization to send that plan externally. The `local` flag exists for plans
that must not leave the machine.

## Transport reference

Read `~/.claude/skills/review-plan-codex/references/codex-transport.md` before
Stage 1; it is the source of truth for both codex call shapes (loop and
triage), shell-quoting of `$review-plan-auto`, response extraction, the
`CONVERGENCE:` line grammar, the fixes schema, and the sad-path branches.

Read `gotchas.md` before Stage 1 and before Stage 4: it holds the rationalization
table, the red-flags list, and the measured run behind the wall-clock bounds and
the deterministic Stage 4.

## Stage 0: Locate the plan, set names, preflight

1. Parse `$ARGUMENTS`. If `help`, print the flag table below and stop.

   | Flag | Effect |
   |---|---|
   | `file:path` | Explicit plan location |
   | `skip-internal` | Skip Stage 1 (no Codex pre-clean loop) |
   | `skip-final` | Skip the Stage 4 consistency check |
   | `local` | No codex calls: Stage 1 via the local `review-plan-auto` Skill, triage by Claude, all disclosed. Stage 4 still runs; it is a script, not a model call |
   | `help` | Print this table and stop |

2. Locate the plan (four-tier priority, same as review-plan-auto): explicit
   `file:` argument, then project `plans/` or `notes/` or `pap/` (most recent
   match), then most recent file in `~/.claude/plans/`, then conversation
   history. If none found, stop with: "No plan found. Usage:
   `/review-plan-codex file:path/to/plan.md`".

3. Derive a slug and set artifact paths in a sibling folder:

   ```bash
   PLAN_DIR="$(dirname "$PLAN_PATH")"
   BASE="$(basename "$PLAN_PATH" .md)"
   OUT_DIR="$PLAN_DIR/${BASE}_codex"; mkdir -p "$OUT_DIR"
   DATE="$(date +%Y%m%d)"
   LOOP1_RAW="$OUT_DIR/${BASE}_codex_loop1_raw_${DATE}.txt"
   REVIEW_FILE="$OUT_DIR/${BASE}_claude_review_${DATE}.md"
   TRIAGE_RAW="$OUT_DIR/${BASE}_codex_triage_raw_${DATE}.txt"
   FIXES_FILE="$OUT_DIR/${BASE}_codex_fixes_${DATE}.md"
   POSTFIX="$OUT_DIR/${BASE}_post_fixes_${DATE}.md"
   BACKUP="$OUT_DIR/${BASE}_pre_codex_${DATE}.md"
   ```

4. Preflight (skip if `local`):

   ```bash
   bash ~/.claude/skills/review-plan-codex/scripts/codex-preflight.sh "$BASE" "$PLAN_PATH"
   ```

   On non-zero exit: do NOT abort. Record the preflight stderr verbatim in
   `$FIXES_FILE`, switch the entire run to `local` mode, and say so in the
   final report ("codex unreachable, ran in local mode: <stderr>"). If
   `TOKEN_ESTIMATE` exceeds ~150k, note the size warning in the report and
   proceed (unattended runs do not stop to ask about trimming).

5. Back up before anything mutates: `cp "$PLAN_PATH" "$BACKUP"`. The backup is
   the whole-run revert target.

## Stage 1: Codex convergence loop (pre-clean)

Skip if `skip-internal`.

Run the full iterative review-plan-auto loop on Codex so the plan converges
before the independent critique round is spent on it.

0. Record `wc -l "$PLAN_PATH"` before launching. Stage 1 rewrites in place, so
   this is the only chance to measure what it did.
1. Invoke per the loop call shape in `codex-transport.md`: working directory
   `$PLAN_DIR` (workspace-write must cover the plan file), sandbox
   `workspace-write`, prompt `$review-plan-auto file:$PLAN_PATH` (single-quote
   the literal so the shell does not expand `$review`), stdout to
   `$LOOP1_RAW`. Launch with `run_in_background: true` and wait for the
   completion notification; a multi-pass loop routinely outruns foreground
   Bash timeouts. Do not poll with sleep.

   **Wall-clock bound: 20 minutes.** A convergence loop that has not returned
   by then is not converging, it is rewriting. On breach, stop the task, record
   `loop1: TIMEOUT` with elapsed minutes and the plan's line count in
   `$FIXES_FILE`, and continue to Stage 2 on whatever is on disk. Do not
   relaunch and do not fall back to `local`: a timeout is a bounded result, not
   a transport failure. Disclose it in the final report.
2. On completion, extract the `CONVERGENCE:` line (grammar in
   `codex-transport.md`) and record `loop1: CODEX` plus that line in
   `$FIXES_FILE`. The loop writes its revision to `$PLAN_PATH` in place; let
   it. The revised plan is the Stage 2 input unconditionally.

   Record the after line count next to the before count. Growth past 25 percent
   goes in the final report as a flagged number, because a pre-clean loop that
   inflates the plan by a quarter has done something other than clean it. This
   is a disclosure, not a gate: Stage 2 still reviews what Stage 1 produced.
3. Sad paths (full table in `codex-transport.md`): non-zero exit means run the
   local `review-plan-auto` Skill fallback with disclosure; a missing
   `CONVERGENCE:` line with clear evidence the loop ran (summary present, plan
   mtime changed) means record `verdict=UNPARSED` plus the summary's exit line
   and continue.

`local` mode: invoke the `review-plan-auto` Skill on `file:$PLAN_PATH`, record
`loop1: LOCAL` plus its convergence verdict.

## Stage 2: Independent Claude critique (single pass)

This is the cross-model judgment pass: a fresh evaluation of the
GPT-converged plan by a different model family. One pass, no loop.

1. Choose the rubric:

   ```bash
   if grep -qE 'GUARDRAIL\[|^[[:space:]]*(threshold|assertion|ladder|escalation):' "$PLAN_PATH"; then
     PROMPT_FILE=~/.claude/skills/review-plan-codex/references/codex-review-prompt-strict.md
   else
     PROMPT_FILE=~/.claude/skills/review-plan-codex/references/generic-review-prompt.md
   fi
   ```

2. Dispatch ONE `Agent` call (`subagent_type="general-purpose"`). Its prompt
   is: a 2-4 sentence context briefing you derive from the plan (what it is,
   who or what executes it, what failure looks like; never a literal
   placeholder), then the full rubric file content, then the full current
   plan text. Instruct it to return only the review, using the rubric's three
   exact headers. Fresh context is the point: the subagent must not see your
   conversation, the Stage 1 output, or any hint of expected findings.
3. Write the returned review to `$REVIEW_FILE` and validate:

   ```bash
   for H in "## Missing verifications" "## Potential problems" "## Unclear demands"; do
     grep -q "^$H" "$REVIEW_FILE" || { echo "FAIL: missing $H"; exit 1; }
   done
   ```

   On a malformed return, re-dispatch once; if still malformed, fall back to
   an inline critique with the critic stance ("you are the critic, not the
   planner") and disclose the fallback in the report.
4. If all three sections say nothing to flag, record "Claude found no issues
   in the converged plan" in `$FIXES_FILE` and skip to Stage 4 (which then
   also skips, since no fixes were applied; the report still shows both
   verdicts).

## Stage 3: Codex triage of Claude's findings

The GPT-side model audits the Stage 2 findings against the plan. Findings
survive only with a recorded validity verdict.

1. Build the triage prompt per `codex-transport.md`: the content of
   `references/codex-triage-prompt.md`, the same context briefing, the full
   plan, and the full `$REVIEW_FILE`. Invoke codex read-only with
   `run_in_background: true` and wait for the completion notification, exactly
   as Stage 1 does. Stdout to `$TRIAGE_RAW`.

   Single-shot does not mean fast: a triage over two dozen findings runs past
   five minutes. Background launch keeps a slow call distinguishable from a
   failed one. Apply the same 20-minute bound as Stage 1; on breach, record
   `triage: TIMEOUT` and take the degraded self-triage path in step 2,
   disclosing it.
2. Extract the response (last `^codex$` to `^tokens used$`, strip `^hook: `
   lines) and validate the headers `## Triage table` and
   `## Fix recommendations`. On non-zero exit or malformed output: perform the
   triage yourself with disclosure ("cross-model audit unavailable:
   <reason>"); do so skeptically, but know this is the degraded path and say
   so in the report.
3. Build `$FIXES_FILE` from the triage using the fixes-plan schema in
   `codex-transport.md`. Validity (VALID / PARTIAL / INVALID) and confidence
   (HIGH / MEDIUM / LOW) come from the triage; keep INVALID rows with their
   one-line justifications as the audit trail. Any finding rejected as
   INVALID with LOW confidence goes in the final report under "Cross-model
   disagreement, spot-check these": a weak rejection of a Claude finding is
   user-relevant signal, not noise.
4. Apply fixes: for each VALID or PARTIAL item, turn the triage's fix
   recommendation into an Edit block (exact old-text / new-text against the
   current plan) and apply it to `$PLAN_PATH` without asking. If old-text
   does not match (drift), skip that block, record it in `$FIXES_FILE`, and
   continue with the remaining blocks. If every finding is INVALID, record
   "no plan-fixable issues survived triage" and skip Stage 4.

   `$FIXES_FILE` must carry each applied item as a real `### Fix N` block with
   its Old text and New text fences, per the schema in `codex-transport.md`.
   Stage 4 parses those fences to confirm the edits landed, so a fixes file
   summarizing the edits in prose instead of reproducing them makes Stage 4
   unable to verify anything and it will fail `FIX_NOT_APPLIED`.
5. Snapshot immediately, before Stage 4 runs:

   ```bash
   cp "$PLAN_PATH" "$POSTFIX"
   ```

   This is the post-fix recovery point. Without it the only revert target is
   `$BACKUP`, so a bad Stage 4 forces you to discard Stages 1 through 3 as
   well, which is a disproportionate loss for a failure in the cheapest stage.

## Stage 4: Deterministic consistency check

Skip if `skip-final` or no fixes were applied in Stage 3.

Confirm the Stage 3 edits landed and did not break the plan's structure. This
is a mechanical check, so it runs as a script and finishes in under a second:

```bash
python3 ~/.claude/skills/review-plan-codex/scripts/verify-applied-fixes.py \
  --plan "$PLAN_PATH" --snapshot "$POSTFIX" --fixes "$FIXES_FILE"
```

Record `verify: SCRIPT` plus the emitted `VERIFY:` line in `$FIXES_FILE`. On a
non-zero exit, record the failure reason verbatim, report it, and leave the
plan alone: the script never edits, so a failure is information about what
Stage 3 did, not damage to repair. `--max-growth` defaults to 0.10 and exists
for plans where the fixes legitimately restructure a section.

The five assertions are: every applied fix's new text is present; code fences
balance; no section heading is duplicated; the first non-blank line is still a
level-1 heading; and the line count is within budget of `$POSTFIX`.

**Why this is a script and not a model call.** A model asked to check a
document will improve it, and an improvement here is indistinguishable from
the corruption the stage exists to detect: a stage that rewrites the fixes it
was asked to confirm destroys the audit trail linking each triaged finding to
its edit, while leaving the plan looking fine. The check must therefore be
incapable of editing. `gotchas.md` records the run that establishes this,
including the measured cost.

## Output to the user (end of run)

The single report after the unattended run. Include, in this order:

1. Engine table: one row per stage (1, 2, 3, 4) with engine used
   (CODEX / CLAUDE / SCRIPT / LOCAL-fallback), outcome or verdict, and skipped
   stages marked as skipped with the reason.
2. Stage 1 `CONVERGENCE:` line, the pre-clean diff summary (`$BACKUP` vs
   post-Stage-1 plan), and the before/after line counts with growth flagged
   past 25 percent.
3. Stage 2: finding counts per rubric section, `$REVIEW_FILE` path.
4. Triage summary: N findings, breakdown VALID / PARTIAL / INVALID, plus the
   "Cross-model disagreement, spot-check these" list (INVALID + LOW).
5. Fixes applied (list) and any drifted blocks.
6. Stage 4 `VERIFY:` line (or skipped).
7. Two revert commands, narrower first, because they undo different amounts:
   - `cp "$POSTFIX" "$PLAN_PATH"` undoes Stage 4 only, keeping the converged
     plan and all applied fixes.
   - `cp "$BACKUP" "$PLAN_PATH"` undoes the entire run back to the plan as the
     user wrote it.

State explicitly anything skipped, fallen back, or unverified (preflight
failure, unparsed verdict lines, malformed triage, drifted blocks). Do not
report "done" if a stage was skipped or degraded.

## Artifacts (kept for audit trail)

- `${BASE}_codex_loop1_raw_<DATE>.txt`: raw Stage 1 loop stdout.
- `${BASE}_claude_review_<DATE>.md`: Claude's independent critique.
- `${BASE}_codex_triage_raw_<DATE>.txt`: raw Stage 3 triage stdout.
- `${BASE}_codex_fixes_<DATE>.md`: gate proofs, triage table, edits, audit trail.
- `${BASE}_post_fixes_<DATE>.md`: plan after Stage 3, before Stage 4. The
  narrow revert target and Stage 4's line-count baseline.
- `${BASE}_pre_codex_<DATE>.md`: plan backup (whole-run revert target).

Stage 4 produces no raw transcript, because it is a script rather than a codex
call. Its `VERIFY:` line in `$FIXES_FILE` is the whole record.
