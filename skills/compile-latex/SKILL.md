---
name: compile-latex
description: Use when the user asks to compile, build, typeset, or verify a LaTeX document or PDF, including research papers, internal research notes, Beamer decks, and referee reports.
argument-hint: "[path-to-tex-file]"
allowed-tools: ["Bash", "Read", "Glob"]
---
# Compile LaTeX

## Activation boundary

An approved small edit to an existing manuscript is source-only unless the user
explicitly requests a PDF rebuild/update or delivery of a completed revision.
Apply the targeted edit, verify the source, and reply:
`Source edited; PDF not rebuilt.`
Do not enter the compile workflow merely because a .tex file changed. Do not
attach a stale PDF as the output of a source-only edit. Compile accumulated edits
once when PDF delivery is requested. This rule also applies to deletion of a
symbol and changes to a theorem's formatting.

Classify the master document before compiling:

| Profile | Signal | Route |
|---|---|---|
| `research` | Academic paper, working paper, policy brief, or research note | Shared research compiler |
| `beamer` | `documentclass{beamer}` or frames | Shared compiler plus deck audit |
| `referee` | Referee-report source | Shared compiler plus referee lint and label checks |
| `generic` | Other LaTeX output | Shared compiler with generic profile |

An unclassified document cannot receive research certification.

## Compilation

Run:

```bash
python3 ~/claude-core/scripts/compile-research-tex.py \
  path/to/master.tex --profile research
```

Replace `research` with `beamer`, `referee`, or `generic` when that profile
applies. The referee profile also requires the manuscript text and either the
referee lexicon or corpus arguments reported by `--help`.

Do not call `xelatex`, `pdflatex`, `lualatex`, or `latexmk` directly for a
document. The shared compiler runs the profile-specific source checks, uses the
correct bibliography backend through `latexmk`, verifies the PDF, and writes
the QA receipt.

The research-LaTeX source linter runs for every profile. Table and figure rules
are universal, so labeling a reply or internal document `generic` does not
bypass regression-table validation.

Before reporting completion:

1. Require a zero exit status.
2. Read the receipt and confirm its status is `pass`.
3. Report every warning.
4. State whether the rendered pages were visually inspected. Rendering alone is
   not visual inspection.
5. Never treat the existence of a PDF as proof of a successful build.

## Small-edit fast path

When PDF delivery accompanies a local prose or notation edit, reuse instructions already loaded
in the session. Do not replan, delegate, re-audit the model, or broaden the edit.
Apply the required writing checks only to new prose; a literal deletion does not
require generating a replacement or rerunning a manuscript-wide writing pass.

Use `~/claude-core/scripts/latex-edit-fast.py` for the mechanical bookkeeping:

1. Batch the targeted read/edit and `stage MASTER --profile research --qa-root
   QA_DIR` in one execution. Use the existing QA directory. Wait up to 10 seconds
   rather than requesting one-second polling. It runs the canonical compiler,
   validates the baseline PDF hash and visual receipt, and returns JSON with
   `changed_pages`, warnings and `manifest`.
2. In Codex, parse that JSON and emit the changed-page images within the same
   orchestration call when feasible. Inspect only those pages; request full-size
   crops only if needed. If many pages changed, use bounded image batches to
   avoid truncation. Missing/untrusted baseline means all pages need review.
3. After actual visual inspection, call `publish MANIFEST --reviewed PATHS...
   --reviewer Codex --notes "Actual findings"`. With no changed pages, use
   `--reviewed` with no paths. This writes the attestation, publishes through the
   canonical compiler and runs the publication verifier in one command.
4. Give a short completion reply and the required PDF folder/filename.

Never invent visual approval or suppress compiler warnings. Do not hand-write
hash-comparison scripts or receipt JSON for each edit. If publication detects a
concurrent source edit, preserve it and rebuild once; if sources keep changing,
report that publication is pending rather than entering a silent retry loop.

Latency target: two orchestration calls after the local edit for an ordinary
small change, except additional image batches or a genuine compile failure.
This is a tool-round-trip target, not a guarantee about external build time.
