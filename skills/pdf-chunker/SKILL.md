---
name: pdf-chunker
description: MANDATORY for any task involving reading, analyzing, summarizing, reviewing, or extracting content from a PDF file. Triggers on any PDF input regardless of size. This skill replaces the default PDF reading behavior with a reliable chunked extraction method.
---

# PDF Chunker

**MANDATORY FIRST STEP FOR ANY PDF**: Run the extraction script BEFORE attempting to read or analyze PDF content. Do not skip this step. Do not try to read the PDF directly.

```bash
python3 <skill_path>/scripts/extract_pdf.py <pdf_path> --output /tmp/extracted.txt
```

Then read `/tmp/extracted.txt` for all subsequent analysis. Any writable path works for `--output`; use the session scratch directory when one is given.

This applies to ALL PDFs, small or large. Never load a whole PDF into context by any other method. The one exception is the page images described below.

## What the text layer cannot see

Tables and figures are often pasted into a PDF as pictures. Institutional reports do this routinely: in one IMF Article IV report the Selected Economic Indicators, Balance of Payments, Monetary Survey, and Financial Soundness tables are all pictures, and their pages extract as a title with no numbers. A page that comes back nearly empty is therefore not evidence that the page is empty.

The script marks these cases. Its first lines of output and the header of the extracted file list the affected pages.

| Marker in the extracted text | Meaning | What to do |
|---|---|---|
| `[IMAGE-ONLY CONTENT ...]` | The page's table or figure is a picture; the text below it is a title and notes at most. The marker quotes the caption when it finds one. | Read the page as an image whenever the task needs what that page shows: always for extracting numbers, reproducing a table, or checking a figure. |
| `[PICTURE ON THIS PAGE ...]` | The page has text and also a large picture whose content is not in the text. | Read the page as an image when the task concerns the picture. |
| `[LAYOUT VIEW of page N ...]` | A second copy of a number-dense page with columns aligned by position. | Take column assignment (which year, budget or actual, which specification) from the layout view. In the running text above it, column headers run together. |

Read a page as an image:

```bash
pdftoppm -png -r 200 -f <N> -l <N> <pdf_path> <scratch_dir>/page
```

Then open the PNG with the Read tool. Without `pdftoppm`, use the Read tool on the PDF with `pages: "<N>"`, one flagged page or a short range at a time.

Numbers read from a page image are a transcription, not an extraction:

- Say which pages were read as images when reporting numbers from them.
- When a digit is unclear, render again at `-r 300` and reread it before using it.
- Where the document allows, check a transcribed value against a total printed in the same table or against the same series elsewhere in the document.
- A check that turns up a different value is not always a misread: the same series can appear in two vintages inside one PDF (a press-release table and the staff report table). Report both values with their pages; do not pick one silently.

## When the checks are off

The header lines `# Layout views:` and `# Image detection:` say whether each check ran. They need poppler (`brew install poppler`). With image detection off, only captioned pages with almost no text are flagged, so a picture table can pass unnoticed: say so when reporting numbers from that document.
