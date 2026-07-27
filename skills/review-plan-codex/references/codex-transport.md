# Codex Transport Reference

Defines the precise mechanics that `SKILL.md` references abstractly: the two
codex call shapes (convergence loop, triage), response extraction, the
`CONVERGENCE:` line grammar, the fixes-plan schema, and the sad-path branches.

---

## Transport: `codex exec`

- Package: `@openai/codex` (>= v0.134.0). Install: `npm install -g @openai/codex@latest`.
- Authentication: ChatGPT Pro subscription (`codex login` once; persists in `~/.codex/`).
- Model and reasoning effort come from `~/.codex/config.toml` (`model`,
  `model_reasoning_effort`). Do NOT pass `-m`/`--model` in this skill; the
  config file is the single place the model is chosen, so upgrades happen
  there. Record the actual model from the `model:` line in the raw output.
- No per-call $ cost; counts against ChatGPT Pro rate limits.
- Overhead: ~30k tokens of agentic scaffolding per call on top of the prompt
  content; loop calls add the Codex-side skill body and its canonical reads.

Common flags for every call:

```
CODEX_GIT_FLAG    = "--skip-git-repo-check"   # required when cwd is not a git repo
CODEX_STDIN_GUARD = "< /dev/null"             # required; codex reads stdin by default and will hang
```

Sandbox differs by call shape: `workspace-write` for loop calls (the loop
edits the plan file), `read-only` for triage calls (critique only).

---

## Call shape A: convergence loop

Runs the Codex-side `review-plan-auto` skill (`~/.codex/skills/review-plan-auto/`)
on the plan. Used by Stage 1 only. Stage 4 no longer calls codex; it runs
`scripts/verify-applied-fixes.py`, documented in SKILL.md.

**Shell-quoting rule (load-bearing):** the literal `$review-plan-auto` must
reach codex intact. Inside double quotes the shell expands `$review` to an
empty string and the skill never triggers. Single-quote the literal and
concatenate the path:

```bash
LOOP_PROMPT='$review-plan-auto file:'"$PLAN_PATH"          # Stage 1

cd "$PLAN_DIR" && command codex exec \
  --skip-git-repo-check \
  --sandbox workspace-write \
  "$LOOP_PROMPT" < /dev/null > "$RAW_OUT" 2>&1
```

`cd "$PLAN_DIR"` is required: workspace-write scopes writes to the working
directory, and the loop must be able to write `$PLAN_PATH` in place.

**Timing:** a multi-pass loop runs well past foreground Bash timeouts. Launch
with `run_in_background: true` and wait for the completion notification; do
not poll with sleep. Bound it at 20 minutes: past that the loop is rewriting
rather than converging, so stop the task and record `loop1: TIMEOUT` per
SKILL.md Stage 1 rather than waiting it out or relaunching.

### Loop verdict extraction

The Codex-side skill ends its final message with a single machine-parseable
line:

```
CONVERGENCE: verdict=<APPROVE|REVISE> exit=<approve|clean|churn|self-churn|inflation|hard-cap|findings-only|error> score=<N> passes=<K>/<MAX>
```

The exit token set mirrors `const contract.convergence.exitEnum` in
`review-plan-auto/scripts/review-loop.js`. The v2.1 contract retired the old
`deterioration|regression|marginal` tokens (the loop never emitted them);
`churn` and `error` replace that range. The v2.2 contract adds `self-churn` (the
loop stopped because it was reviewing machinery its own reviser added) and
`findings-only` (a derivation plan reviewed without being rewritten). Both carry
`verdict=REVISE`, since the author, not the loop, applies the fixes. Extract the
line directly from the raw output:

```bash
grep -E '^CONVERGENCE: verdict=' "$RAW_OUT" | tail -1
```

Record the line verbatim in `$FIXES_FILE` as the gate proof. If the grep is
empty, apply sad-path S3 below.

---

## Call shape B: triage (single-shot, read-only)

Sends the plan plus Claude's Stage 2 review to the GPT-side model for
adversarial triage. Single-shot, but not fast: a triage over two dozen findings
runs past five minutes. Launch it with `run_in_background: true` and wait for
the completion notification, like the loop call, under the same 20-minute
bound. A foreground timeout short enough to fire mid-call is worse than none,
because a call shunted to the background is indistinguishable from a failed one
at the moment it happens.

```bash
FULL_PROMPT="$(cat ~/.claude/skills/review-plan-codex/references/codex-triage-prompt.md)

---
Context briefing: <your 2-4 sentence briefing, derived from the plan>

---
Plan under review:

$(cat "$PLAN_PATH")

---
Reviewer findings to triage:

$(cat "$REVIEW_FILE")"

cd "$PLAN_DIR" && command codex exec \
  --skip-git-repo-check \
  --sandbox read-only \
  "$FULL_PROMPT" < /dev/null > "$TRIAGE_RAW" 2>&1
```

### Response extraction (both call shapes, when the body is needed)

Codex stdout structure: banner, config echo, the prompt echoed back, then one
or more `codex` scaffolding cycles. The final answer lives between the LAST
`^codex$` marker and `^tokens used$`. Hook output (`hook: Stop` lines) can sit
inside that window; strip it:

```bash
START=$(grep -n "^codex$" "$RAW" | tail -1 | cut -d: -f1)
END=$(grep -n "^tokens used$" "$RAW" | head -1 | cut -d: -f1)
sed -n "$((START + 1)),$((END - 1))p" "$RAW" | grep -v '^hook: ' > "$RESPONSE_FILE"
```

Validate the triage response headers:

```bash
for H in "## Triage table" "## Fix recommendations"; do
  grep -q "^$H" "$RESPONSE_FILE" || { echo "FAIL: missing $H"; exit 1; }
done
```

---

## Fixes plan: full schema

File: `${BASE}_codex_fixes_<YYYYMMDD>.md`

```markdown
# Cross-Model Review Record for <slug>

## Source

| Field | Value |
|---|---|
| Plan | `<plan_path>` |
| Backup | `<backup_path>` |
| Codex model | <from the raw output `model:` line> |
| Claude review file | `<review_file>` |
| Run date | YYYY-MM-DD |

## Gate proofs

- loop1: CODEX|LOCAL -- CONVERGENCE: <line verbatim, or verdict=UNPARSED + quoted exit line>
- triage: CODEX|LOCAL -- <headers validated | fallback reason>
- loop2: CODEX|LOCAL|SKIPPED -- CONVERGENCE: <line verbatim, or skip reason>

## Triage table

| # | Finding (short) | Plan citation | Validity | Confidence | Reason (<=25 words) |
|---|---|---|---|---|---|

Validity and confidence are assigned by the GPT-side triage (VALID / PARTIAL /
INVALID; HIGH / MEDIUM / LOW). INVALID rows keep their one-line justification
as the audit trail. INVALID + LOW rows are additionally surfaced in the final
report as cross-model disagreement.

## Applied edits

One block per VALID or PARTIAL item, formatted for the Edit tool:

### Fix 1 (citation: <plan citation>, validity: VALID, confidence: HIGH)

**Old text** (exact match required):
```
<verbatim before text>
```

**New text:**
```
<verbatim after text>
```

**Justification:** <one line>

## Drifted blocks

Blocks whose old-text no longer matched at apply time, recorded and skipped.

## Open questions

LOW-confidence items and anything the triage could not settle from the plan
alone.
```

---

## Sad-path branches

**Failure detection (load-bearing):** `codex exec` can exit 0 on a hard API
error (e.g. a model-rejection 400 prints `ERROR: {...}` lines and exits
cleanly). A call has FAILED when ANY of these hold: non-zero exit, no
`^codex$` response marker in the raw output, or `^ERROR:` lines present with
no response after them. Check all three before treating a call as successful.

| # | Trigger | Branch |
|---|---|---|
| S1 | Preflight non-zero (codex unreachable) | Switch the whole run to `local` mode; record stderr verbatim; disclose in report. Stage 4 is unaffected: it is a script. |
| S2 | Loop call fails (per failure detection above) | Run the local `review-plan-auto` Skill for that stage; record `loop: LOCAL` + reason; disclose. |
| S2b | Stage 1 loop or triage exceeds the 20-minute bound | Stop the task. Record `loop1: TIMEOUT` or `triage: TIMEOUT` with elapsed minutes and the plan's line count. Continue on what is on disk. Do NOT relaunch and do NOT treat it as a transport failure warranting `local`: the bound produced a result. |
| S3 | `CONVERGENCE:` line absent but loop evidence present (final summary in raw output, plan mtime changed) | Record `verdict=UNPARSED` plus the summary's exit-reason line verbatim; continue. No evidence at all = treat as S2. |
| S4 | Triage call fails (per failure detection above) or headers missing | Claude performs the triage itself, skeptically; record `triage: LOCAL` + reason; report flags the degraded cross-model audit. |
| S5 | `TOKEN_ESTIMATE` > ~150k | Note the size warning in the report and proceed (unattended runs do not stop to ask). |
| S6 | Every finding INVALID at triage | Record "no plan-fixable issues survived triage"; skip Stage 4; report both models' verdicts. |
| S7 | An edit block's old-text does not match the plan (drift) | Skip that block, record it under Drifted blocks, continue with the rest. |
| S8 | Confidential markers detected in the plan | ABORT loud before any codex call; name what was detected and where. |
| S9 | Stage 4 `verify-applied-fixes.py` exits non-zero | Record the `VERIFY: verdict=FAIL reason=<CODE>` line verbatim and report it. There is no fallback and no retry: a script failure is a finding about Stage 3's edits, not a transport problem. Do not "verify by reading the plan yourself"; that is the collapse this skill exists to prevent. `FIX_NOT_APPLIED` usually means `$FIXES_FILE` was written as prose instead of `### Fix N` blocks with fences. |
