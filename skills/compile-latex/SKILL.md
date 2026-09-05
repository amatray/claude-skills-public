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
