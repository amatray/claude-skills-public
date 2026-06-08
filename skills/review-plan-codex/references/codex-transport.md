# Codex Transport Reference

Defines the precise mechanics that `SKILL.md` references abstractly: how to call
codex, how to extract its response, the fixes-plan schema, and the sad-path
branches.

---

## Transport: `codex exec`

The plan is sent to an external LLM (GPT-5.5 from OpenAI) for a second critique
via `codex exec`, synchronously.

- Package: `@openai/codex` (>= v0.134.0). Install: `npm install -g @openai/codex@latest`.
- Synchronous: codex runs the prompt and returns the response on stdout in 1-3 min.
- Authentication: uses a ChatGPT Pro subscription (logged in via `codex login` once; persists in `~/.codex/`).
- Model: GPT-5.5 by default (codex picks the current ChatGPT Pro entitlement).
- No per-call $ cost; counts against ChatGPT Pro rate limits.
- Overhead: ~30k tokens of agentic scaffolding per call ON TOP of prompt + plan content. For a typical plan (5-15k chars), total cost is ~35-50k tokens.
- Failure handling: on `codex exec` non-zero exit or missing response headers, abort with a codex-failure message. No async fallback.

---

## Constants

```
TRANSPORT         = "codex"
CODEX_MODEL       = "gpt-5.5"   # codex auto-selects from ChatGPT Pro entitlement; bump as OpenAI releases newer models
CODEX_SANDBOX     = "read-only" # do NOT use workspace-write; this is a critique task, not a coding task
CODEX_GIT_FLAG    = "--skip-git-repo-check"  # required when cwd is not a git repo
CODEX_STDIN_GUARD = "< /dev/null"  # required; codex reads stdin by default and will hang
```

---

## Invocation

### Build the full prompt

```bash
FULL_PROMPT="$(cat $PROMPT_FILE)

---
Plan to review:

$(cat $PLAN_PATH)"
```

### Invoke codex

```bash
codex exec \
  --skip-git-repo-check \
  --sandbox read-only \
  "$FULL_PROMPT" < /dev/null > "$RAW_OUT" 2>&1
EXIT=$?
```

If `EXIT` != 0: codex failed. Inspect `$RAW_OUT` for the error, surface it, and exit.

### Response extraction

Codex stdout has this structure:

```
Codex banner (includes "--------" separators)
OpenAI Codex v0.134.0
--------
workdir: ...
model: gpt-5.5
provider: openai
...
session id: <uuid>
--------
user
<the full prompt echoed back>
codex                                <- response-start marker (line N)
<the model's response>
tokens used                          <- response-end marker (line M)
<token count>
<duplicate of response>              <- summary block, ignored
```

Extract lines (N+1) through (M-1). **Use the LAST `^codex$` marker, not the
first** -- codex's agentic scaffolding can emit multiple `codex`/`exec` cycles
before the final response (e.g., when codex decides to read its own files
first). The final response always lives between the LAST `^codex$` marker and
`^tokens used$`:

```bash
START=$(grep -n "^codex$" "$RAW_OUT" | tail -1 | cut -d: -f1)
END=$(grep -n "^tokens used$" "$RAW_OUT" | head -1 | cut -d: -f1)
sed -n "$((START + 1)),$((END - 1))p" "$RAW_OUT" > "$RESPONSE_FILE"
```

Validate the three required headers:

```bash
for HEADER in "## Missing verifications" "## Potential problems" "## Unclear demands"; do
  grep -q "^$HEADER" "$RESPONSE_FILE" || {
    echo "FAIL: missing $HEADER. Aborting."
    exit 1
  }
done
```

---

## Fixes plan: full schema

File: `${BASE}_codex_fixes_<YYYYMMDD>.md`

```markdown
# Codex-Derived Fixes for <slug>

## Source

| Field | Value |
|---|---|
| Codex review file | `<path>` |
| Codex review date | YYYY-MM-DD |
| Model | gpt-5.5 |
| Plan reviewed | `<plan_path>` |
| Plan body sha at send time | `<sha>` |

## Triage table

| # | Section | Plan citation | Codex claim (verbatim, <=30 words) | Validity | Confidence | Action |
|---|---|---|---|---|---|---|

### Validity codes (assigned by Claude)

- **VALID**: claim is correct and not addressed elsewhere in the plan. Apply the fix.
- **PARTIAL**: claim is partly correct, or addresses a real issue with the wrong fix. Apply a modified fix.
- **INVALID**: claim is wrong (already addressed, factually incorrect, or based on missing context). Skip with one-line justification.

### Confidence codes (assigned by Claude)

- **HIGH**: confident in the validity assessment without re-reading additional context.
- **MEDIUM**: assessed by re-reading the cited line and surrounding section.
- **LOW**: uncertain; flag for domain judgment.

## Proposed edits

One block per VALID or PARTIAL item, formatted for the Edit tool:

```
### Fix 1 (citation: <plan citation>, validity: VALID, confidence: HIGH)

**File:** `<plan_path>`

**Old text** (exact match required):
```
<verbatim before text>
```

**New text:**
```
<verbatim after text>
```

**Justification:** <one-line reason this fix addresses the claim>
```

## Open questions

Any LOW-confidence item, or any item where validity cannot be determined from
the plan alone. Numbered list, each item naming the claim and the missing
context needed.
```

---

## Sad-path branches

| Test | Branch | Exit behavior |
|---|---|---|
| 13 | Token estimate > 150k chars (codex context headroom) | Warn the user the plan is large; proceed or trim. |
| 14 | `codex exec` exits non-zero (auth lapse, network hang, CLI broken) | Abort with the codex-failure message. Re-run after fixing codex. |
| 17 | Codex response missing one of the three required section headers | Abort with the codex-failure message; user may retry. |
| 18 | All items INVALID at triage | Print: "Codex found no plan-fixable issues. Original plan untouched." Exit cleanly. |
| 19 | An approved fix's "before text" does not match plan content | Restore from backup; print: "Fix application failed (text drift); plan restored. Review the codex review manually." |
