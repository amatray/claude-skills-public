---
name: pdf-chunker
description: MANDATORY for any task involving reading, analyzing, summarizing, reviewing, or extracting content from a PDF file. Triggers on any PDF input regardless of size. Replaces the default PDF reader (which silently truncates) with a structure-aware chunker that preserves section headings, page numbers, and context. Use this whenever a PDF is provided or referenced — papers, reports, filings, books — even if the user only says "read", "summarize", "look at", or "pull X from" the file.
---

# PDF Chunker

**MANDATORY FIRST STEP FOR ANY PDF**: run the extraction script BEFORE reading or analyzing PDF content. Do not read the PDF directly — the default reader silently truncates long files, and raw page text throws away the section structure you need to navigate a document.

```bash
python <skill_path>/scripts/extract_pdf.py <pdf_path> --output /tmp/extracted.txt
```

Then read `/tmp/extracted.txt`. This applies to ALL PDFs, small or large.

## What the output looks like

The script produces **context-carrying chunks**, not a flat dump. The file has two parts:

1. A **table of contents** — the reconstructed heading tree with page numbers. Read this first to find the sections you care about.
2. A sequence of **chunks**, each headed by its parent-section breadcrumb and page range:

   ```
   ### [3. Data > 3.2 Sample construction] (pp.5–6) · chunk 11/61
   <the section text>
   ```

Because each chunk carries its breadcrumb, any single chunk is self-explanatory: you can quote or reason about it without scrolling the whole document, and you always know which section and page a fact came from. For a long document, read the table of contents, then pull only the chunks whose breadcrumbs match what you need.

## How it chunks

- **Structural (default)** — reconstructs headings from font sizes plus an academic-section regex (`Abstract`, `3.2 Data`, `IV. Results`, …), splits on them, prepends the parent-header breadcrumb, keeps chunks near a word cap (splitting oversized sections, merging tiny ones), and drops footnotes and running heads. Best for papers, reports, and filings. Extraction is column-aware, so two-column papers don't get their columns interleaved.
- **Semantic (`--semantic`)** — for long stretches with no sub-headings, splits by *meaning*: each sentence is embedded and a new chunk starts when the topic drifts from the running average. Use for prose-heavy documents with few headings. Needs `sentence-transformers` (local; downloads a small model once).

Extraction falls back across pdfplumber → PyMuPDF → pypdf, so it works even if one library is missing. `tiktoken` and `sentence-transformers` are optional.

## Options

| flag | default | purpose |
|------|---------|---------|
| `--output PATH` | `<pdf>.txt` | where to write |
| `--semantic` | off | topic-drift splitting for headerless prose |
| `--flat` | off | old behaviour: plain page-by-page dump, no chunking |
| `--max-words N` | 350 | soft target chunk size (words) |
| `--min-words N` | 40 | merge chunks smaller than this |
| `--max-tokens N` | none | hard token cap per chunk (needs tiktoken) |

Run with no path to batch-process every PDF in `./pdfs/` into `./extracted_pdfs/`.

## If a layout looks off

For an unusual layout (e.g. a 3-column magazine) the heading detector may over-fire; a built-in density check then keeps only regex-detected section headings. If the result is still messy, fall back to `--flat` and read linearly.
