---
name: solving-model
description: >
  Systematically set up, solve, and verify an economic model with step-by-step
  derivations and cross-model mathematical checking. Use when user wants to
  formalize an economic idea into a model, solve a model, derive equilibrium
  conditions, check derivations, or verify mathematical results. Also use when
  user says "solve", "derive", "set up the model", "formalize", "verify the math",
  "check derivation", "model setup". Not for the solving_models pipeline
  repository (the one with AGENTS.md), where a model starts as a sketch
  interview under prompts/sketch_interview.md; do not use there.
argument-hint: "[model description or path] [--from=N] [--name=model-name] [--verify]"
---

# solving-model

Orchestrate economic model derivation and verification through five checkpointed phases, each dispatched to a dedicated sub-agent.

## Architecture

```
SKILL.md (this file) — argument parsing, phase routing, checkpoint enforcement
  ├── references/phase-1-setup.md         — Model setup elicitation + Oracle review
  ├── references/phase-2-derivation.md    — Step-by-step derivation
  ├── references/phase-3-verification.md  — Local checks + Oracle re-derivation
  ├── references/phase-4-comp-statics.md  — Comparative statics + Oracle sign verification
  ├── references/phase-5-documentation.md — Assembly + compilation
  ├── references/oracle-prompts.md        — Oracle prompt templates
  └── references/example-walkthrough.md   — Concrete output pattern (collateral model)

Shared preferences (read by sub-agents as needed):
  ├── preferences/model-solving-conventions.md  — LaTeX templates
  ├── preferences/verification-protocol.md      — Check procedures + parameter tables
  └── preferences/latex-research.md             — General LaTeX conventions
```

## Phase 0: Argument Parsing

Parse `$ARGUMENTS` for:

| Argument | Effect |
|----------|--------|
| `--from=N` | Start at Phase N (1-5), reading prior phase outputs from disk |
| `--verify` | Alias for `--from=3` |
| `--name=X` | Set model name → working directory `solving_models/X/` |
| File path (`.tex`, `.pdf`) | Use as input; detect type by extension |
| Everything else | Treat as verbal model description |

**If `--name` not provided:** Ask the user for a model name using AskUserQuestion.

**Create working directory:**
```bash
mkdir -p solving_models/[name]/
```

**If `--from=N` with N > 1:** Verify prior phase files exist:

| Start phase | Required files |
|-------------|---------------|
| 2 | `model_setup.tex` |
| 3 | `model_setup.tex`, `derivation.tex` |
| 4 | `model_setup.tex`, `derivation.tex`, `verification_log.tex` |
| 5 | `model_setup.tex`, `derivation.tex`, `verification_log.tex`, `comparative_statics.tex` |

If any required file is missing, explain what's needed and suggest the correct `--from` value.

**Detect input type:**
- `.pdf` extension → `INPUT_TYPE=pdf`
- `.tex` extension → `INPUT_TYPE=latex`
- Otherwise → `INPUT_TYPE=verbal`

---

## Phase Dispatch

Execute phases sequentially. Each phase is dispatched as a **sub-agent** that reads its dedicated reference file for full instructions.

**Dispatch pattern for each phase:**

1. Read `references/phase-N-*.md` for the full phase instructions
2. Set context variables: `$MODEL_NAME`, `$WORKING_DIR`, `$INPUT_TYPE`, `$INPUT_CONTENT`
3. Execute the phase following its instructions exactly
4. At the phase CHECKPOINT: present results and wait for user approval via AskUserQuestion
5. **Do NOT proceed to the next phase without explicit user approval**
6. If the user requests changes, re-execute the relevant steps within the current phase

### Phase 1: Model Setup

Read and follow `references/phase-1-setup.md`.

**Summary:** Elicit model primitives → write `model_setup.tex` → Oracle review → checkpoint.

**Skip if:** `--from` >= 2 (read existing `model_setup.tex` instead).

---

### Phase 2: Derivation

Read and follow `references/phase-2-derivation.md`.

**Summary:** Identify targets → derive step-by-step → flag `% VERIFY` → weasel word scan → checkpoint.

**Skip if:** `--from` >= 3 (read existing `derivation.tex` instead).

**Special:** If derivation reveals model setup is incomplete, HALT and offer to return to Phase 1.

---

### Phase 3: Verification

Read and follow `references/phase-3-verification.md`.

**Summary:** Collect flagged steps → user selects Oracle steps → run 3 local checks on all flagged → Oracle blind re-derivation on selected → HALT on any failure → checkpoint.

**"Verify existing" entry:** If `--verify` with an external file, or `--from=3` when `derivation.tex` lacks `\paragraph{Step` labels, Phase 3 begins with step parsing (see the phase file for full parsing specification). Normal `--from=3` resumes (where `derivation.tex` was produced by Phase 2) skip parsing and go straight to verification.

**Critical rules:**
- Oracle receives `model_setup.tex` only — NEVER `derivation.tex`
- Numerical checks execute via Python, not in-context arithmetic
- Any check failure triggers HALT with side-by-side presentation

---

### Phase 4: Comparative Statics

Read and follow `references/phase-4-comp-statics.md`.

**Summary:** User selects parameters → derive and sign → Oracle batched verification → summary table → checkpoint.

**Oracle budget:** Max 5 sign claims per Oracle call. Split automatically if more.

---

### Phase 5: Documentation & Compilation

Read and follow `references/phase-5-documentation.md`.

**Summary:** Assemble `full_model.tex` with `\input{}` → apply formatting → compile → present PDF.

**Critical:** Must `cd` to working directory before `xelatex` (relative `\input` paths). Only `full_model.tex` is compilable — phase files are fragments.

---

## Error Handling

| Error | Response |
|-------|----------|
| Oracle timeout/failure | Present error, offer retry or skip. Record "Oracle: SKIPPED (timeout)" in verification log. Show degraded-verification warning at checkpoint. |
| LaTeX compilation failure | Show error log. Try common fixes (missing packages, undefined refs). If stuck, present to user. |
| Missing prior phase files | Explain what's missing, suggest correct `--from=N`. |
| Phase 2 discovers setup gap | Re-execute Phase 1 to amend `model_setup.tex` (backup previous version), then restart Phase 2. Preserve partial `derivation.tex` as `derivation.tex.partial`. |
| Phase file overwrite | Always copy existing `.tex` to `.bak` before overwriting. |

## Oracle Budget

Budget 3-6 Oracle sessions total per model run:
1. Setup review (Phase 1) — 1 call
2. Blind re-derivation (Phase 3) — 1-2 calls (max 5 claims each)
3. Sign verification (Phase 4) — 1-3 calls (max 5 claims each)

## First-Time Usage

On first invocation or when the user seems unfamiliar with the workflow, read `references/example-walkthrough.md` to show them the expected output format for each phase.
