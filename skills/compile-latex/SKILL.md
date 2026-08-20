---
name: compile-latex
description: Use when the user asks to compile, build, typeset, or verify a LaTeX document or PDF, including research papers, internal research notes, Beamer decks, and referee reports.
argument-hint: "[path-to-tex-file]"
allowed-tools: ["Bash", "Read", "Glob"]
---
# Compile LaTeX

Classify the master document before compiling:

| Profile | Signal | Route |
|---|---|---|
| `research` | Academic paper, working paper, policy brief, or research note | Shared research compiler |
| `beamer` | `documentclass{beamer}` or frames | Existing deck gate and build workflow |
| `referee` | Referee-report source | Existing referee lint and build workflow |
| `generic` | Other LaTeX output | Explicit generic compilation |

An unclassified document cannot receive research certification.

## Research compilation

Run:

```bash
python3 ~/claude-core/scripts/compile-research-tex.py \
  path/to/master.tex --profile research
```

Do not call `xelatex`, `pdflatex`, `lualatex`, or `latexmk` directly for a
research document. The shared compiler runs the source linter, uses the correct
bibliography backend through `latexmk`, verifies the PDF, and writes the QA
receipt.

Before reporting completion:

1. Require a zero exit status.
2. Read the receipt and confirm its status is `pass`.
3. Report every warning.
4. State whether the rendered pages were visually inspected. Rendering alone is
   not visual inspection.
5. Never treat the existence of a PDF as proof of a successful build.

## Other profiles

- For `beamer`, follow the `deck-matray` compile and audit workflow.
- For `referee`, run both referee lint scripts before compilation.
- For `generic`, state that no research QA receipt is produced.
