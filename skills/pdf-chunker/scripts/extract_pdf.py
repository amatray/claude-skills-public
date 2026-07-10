#!/usr/bin/env python3
"""
PDF Chunker — structural + optional semantic chunking.

The old version of this script dumped flat page text, which forces a reader to
scroll a whole document to find one section and gives an LLM no notion of where a
piece of information sits. This version turns a PDF into *chunks that carry their
own context*, so any single chunk is self-explanatory and the document is
navigable.

How it works (two ideas, borrowed from two chunking libraries):
  1. STRUCTURAL (default) — reconstruct the heading hierarchy from font sizes and
     an academic-section regex, then split on headings. Each chunk is prefixed
     with its parent-header breadcrumb (so "Table 3 shows..." still makes sense out
     of context) and bounded by soft/hard word (and optional token) caps. Tiny
     sections merge; oversized ones split on paragraphs/sentences. Inspired by
     ChunkNorris.
  2. SEMANTIC (--semantic) — for a long stretch with no sub-headings, split by
     meaning instead of by length: embed each sentence, track the running chunk's
     centroid, and start a new chunk when a sentence drifts off-topic. Ported from
     the semantic_chunker gem. Needs sentence-transformers (local, no API).

Extraction prefers pdfplumber (per-character font sizes), then PyMuPDF, then a
flat pypdf fallback (regex-only headings). tiktoken and sentence-transformers are
optional; the script degrades gracefully if they are absent.

CLI (backward compatible — the old `--output` contract still works):
  python extract_pdf.py <pdf_path> [--output out.txt]
  python extract_pdf.py <pdf_path> --semantic
  python extract_pdf.py <pdf_path> --flat                 # old page-dump behaviour
  options: --max-words 350 --min-words 40 --max-tokens N --model all-MiniLM-L6-v2
  no args: batch-process every PDF in ./pdfs/ into ./extracted_pdfs/
"""
from __future__ import annotations

import argparse
import os
import re
import statistics as st
import sys
from pathlib import Path

# ----------------------------------------------------------------------------- #
# 1. Extraction: a PDF -> list of lines, each {text, page, size, bold}.
#    Font size + boldness are what let us tell a heading from body text.
# ----------------------------------------------------------------------------- #

def _lines_pdfplumber(pdf_path: str) -> list[dict]:
    """Column-aware line extraction: most academic PDFs are two-column, and reading
    across columns garbles the text. Split each page into columns first, then read
    each column top-to-bottom, so lines stay coherent."""
    import pdfplumber
    out: list[dict] = []
    with pdfplumber.open(pdf_path) as pdf:
        for pno, page in enumerate(pdf.pages, 1):
            try:
                words = page.extract_words(extra_attrs=["size", "fontname"],
                                           use_text_flow=False, keep_blank_chars=False)
            except Exception:
                words = []
            if not words:
                continue
            for col in _detect_columns(words, float(page.width or 612)):
                for line in _group_lines(col):
                    line["page"] = pno
                    out.append(line)
    return out


def _detect_columns(words: list[dict], width: float) -> list[list[dict]]:
    """Split words into left/right columns if the page is clearly two-column."""
    mid = width / 2.0
    left = [w for w in words if (w["x0"] + w["x1"]) / 2 < mid]
    right = [w for w in words if (w["x0"] + w["x1"]) / 2 >= mid]
    if min(len(left), len(right)) > 0.15 * len(words):        # both sides substantial -> two columns
        return [left, right]
    return [words]


def _group_lines(words: list[dict]) -> list[dict]:
    """Group words on the same visual line (similar 'top'), in reading order."""
    words = sorted(words, key=lambda w: (round(w["top"]), w["x0"]))
    lines: list[dict] = []
    cur: list[dict] = []
    top = None
    for w in words:
        sz = w.get("size", 10) or 10
        if top is None or abs(w["top"] - top) <= max(2.0, sz * 0.6):
            cur.append(w)
            top = w["top"] if top is None else top
        else:
            lines.append(_finish_line(cur))
            cur, top = [w], w["top"]
    if cur:
        lines.append(_finish_line(cur))
    return lines


def _finish_line(words: list[dict]) -> dict:
    words = sorted(words, key=lambda w: w["x0"])
    text = " ".join(w["text"] for w in words).strip()
    sizes = [w["size"] for w in words if w.get("size")]
    fonts = [str(w.get("fontname", "")) for w in words]
    size = st.median(sizes) if sizes else 0.0
    bold = sum(_is_bold_font(f) for f in fonts) > len(fonts) / 2
    return {"text": text, "size": round(size, 1), "bold": bold}


def _lines_pymupdf(pdf_path: str) -> list[dict]:
    import fitz  # PyMuPDF
    out: list[dict] = []
    doc = fitz.open(pdf_path)
    for pno, page in enumerate(doc, 1):
        for block in page.get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                text = "".join(s.get("text", "") for s in spans).strip()
                if not text:
                    continue
                size = max((s.get("size", 0) for s in spans), default=0)
                bold = any((s.get("flags", 0) & 16) or _is_bold_font(s.get("font", "")) for s in spans)
                out.append({"text": text, "page": pno, "size": round(size, 1), "bold": bold})
    doc.close()
    return out


def _lines_pypdf(pdf_path: str) -> list[dict]:
    from pypdf import PdfReader
    out: list[dict] = []
    for pno, page in enumerate(PdfReader(pdf_path).pages, 1):
        for ln in (page.extract_text() or "").split("\n"):
            ln = ln.strip()
            if ln:
                out.append({"text": ln, "page": pno, "size": 0.0, "bold": False})
    return out


def _is_bold_font(font: str) -> bool:
    f = font.lower()
    return "bold" in f or f.endswith("-bd") or ",bold" in f or "black" in f or "heavy" in f


def extract_lines(pdf_path: str) -> tuple[list[dict], str]:
    """Try the richest extractor available; return (lines, extractor_name)."""
    for name, fn in (("pdfplumber", _lines_pdfplumber),
                     ("pymupdf", _lines_pymupdf),
                     ("pypdf", _lines_pypdf)):
        try:
            lines = fn(pdf_path)
            if lines:
                return lines, name
        except ImportError:
            continue
        except Exception as e:  # a corrupt page etc. -> try the next backend
            print(f"   ({name} failed: {e}; trying next backend)", file=sys.stderr)
            continue
    return [], "none"


# ----------------------------------------------------------------------------- #
# 2. Heading detection: which lines are section titles, and at what depth.
# ----------------------------------------------------------------------------- #

# A named section is a short standalone line ("Introduction", "3.2 The model").
NAMED_RE = re.compile(
    r"^(?:abstract|introduction|background|related\s+work|literature\s+review|"
    r"motivation|methods?|methodology|materials?\s+and\s+methods?|the\s+data|data\b|"
    r"empirical\s+(?:strategy|framework)|results?|main\s+results?|findings?|"
    r"discussion|robustness|conclusions?|conclusion|references?|bibliography|"
    r"acknowledge?ments?|appendix|supplementary)\b", re.IGNORECASE)
# A numbered heading needs a CAPITAL after the number, so body lines that merely start
# with a figure/year ("5 while...", "1994 to 2015", "4 4 4") don't qualify.
NUMBERED_RE = re.compile(r"^\d+(?:\.\d+)*\.?\s+[A-Z(]")
ROMAN_RE = re.compile(r"^[IVX]{1,4}\.\s+[A-Z]")

_SENT_END = re.compile(r"[.!?:;,]\s*$")


def _looks_like_title(text: str) -> bool:
    """A section title is short, mostly letters, contains a real word, and is not a
    sentence. This gate is what separates true headings from body fragments and math."""
    words = text.split()
    if not (1 <= len(words) <= 14):
        return False
    nonspace = sum(not c.isspace() for c in text)
    letters = sum(c.isalpha() for c in text)
    if nonspace == 0 or letters / nonspace < 0.45:            # kills "4 4 4", "0 β", "-0.3 -0.2 ..."
        return False
    if not any(len(re.sub(r"[^A-Za-z]", "", w)) >= 3 for w in words):
        return False
    return not _SENT_END.search(text)


def _body_size(lines: list[dict]) -> float:
    """Most common font size, weighted by characters — i.e. the body-text size."""
    from collections import Counter
    c: Counter = Counter()
    for ln in lines:
        c[round(ln["size"])] += len(ln["text"])
    return float(c.most_common(1)[0][0]) if c else 0.0


def _numbering_depth(text: str) -> int | None:
    m = re.match(r"^(\d+(?:\.\d+)*)", text.strip())
    if not m:
        return None
    return min(m.group(1).count(".") + 1, 4)


def mark_headings(lines: list[dict]) -> None:
    """Annotate each line in place with hd_level (int level) or None."""
    from collections import defaultdict
    body = _body_size(lines)
    big = body * 1.12 if body else 0.0
    # First pass: is this line a heading, and by which signal (regex vs font)?
    for ln in lines:
        t, words = ln["text"], ln["text"].split()
        title = _looks_like_title(t)
        # Footnotes also start "<number> <Capital>", but they cite years, hyphenate at the
        # line break, and are set in a smaller font than the body. Rule those out.
        not_ref = not re.search(r"\(\d{4}[a-z]?\)", t) and not t.rstrip().endswith("-")
        big_enough = ln["size"] == 0 or ln["size"] >= body * 0.98
        multiword = len(words) >= 2                           # single-word font fragments are usually noise
        numbered = title and bool(NUMBERED_RE.match(t)) and len(words) <= 12 and not_ref and big_enough
        roman = title and bool(ROMAN_RE.match(t)) and not_ref and big_enough
        named = title and bool(NAMED_RE.match(t)) and len(words) <= 6
        by_size = title and multiword and ln["size"] >= big and ln["size"] > 0 and len(words) <= 12
        by_bold = title and multiword and ln["bold"] and len(words) <= 10 and not_ref
        ln["_kind"] = "regex" if (numbered or roman or named) else ("font" if (by_size or by_bold) else None)
    # Density fallback: if font-based headings are pathologically dense (a magazine with many
    # type sizes, say), the font signal is unreliable — keep only the regex-based headings.
    n_head = sum(1 for ln in lines if ln["_kind"])
    if n_head > 40 and n_head / max(len(lines), 1) > 0.25:
        for ln in lines:
            if ln["_kind"] == "font":
                ln["_kind"] = None
    # Suppress running heads/footers: the same candidate on >= 3 pages is page furniture.
    pages_of: dict[str, set] = defaultdict(set)
    for ln in lines:
        if ln["_kind"]:
            pages_of[ln["text"].lower()].add(ln["page"])
    for ln in lines:
        if ln["_kind"] and len(pages_of[ln["text"].lower()]) >= 3:
            ln["_kind"] = None
    # Level assignment: numbered headings nest by their number; others by font-size rank.
    heads = [ln for ln in lines if ln["_kind"]]
    sizes = sorted({round(h["size"]) for h in heads if h["size"] > 0}, reverse=True)
    size_level = {s: min(i + 1, 4) for i, s in enumerate(sizes)}
    for ln in lines:
        if not ln.pop("_kind", None):
            ln["hd_level"] = None
            continue
        depth = _numbering_depth(ln["text"]) if NUMBERED_RE.match(ln["text"]) else None
        if depth is not None:
            ln["hd_level"] = depth
        elif ln["size"] > 0 and round(ln["size"]) in size_level:
            ln["hd_level"] = size_level[round(ln["size"])]
        else:
            ln["hd_level"] = 1


# ----------------------------------------------------------------------------- #
# 3. Segments: contiguous body text under a heading path (breadcrumb).
# ----------------------------------------------------------------------------- #

def build_segments(lines: list[dict]) -> list[dict]:
    segs: list[dict] = []
    stack: list[tuple[int, str]] = []                        # (level, title)
    cur: dict | None = None

    def flush():
        nonlocal cur
        if cur and cur["body"].strip():
            segs.append(cur)
        cur = None

    for ln in lines:
        lvl = ln["hd_level"]
        if lvl:
            flush()
            while stack and stack[-1][0] >= lvl:
                stack.pop()
            stack.append((lvl, ln["text"]))
            cur = {"crumb": [t for _, t in stack], "page_start": ln["page"],
                   "page_end": ln["page"], "body": ""}
        else:
            if cur is None:                                  # text before the first heading (title/abstract)
                cur = {"crumb": [], "page_start": ln["page"], "page_end": ln["page"], "body": ""}
            cur["body"] += ln["text"] + "\n"
            cur["page_end"] = ln["page"]
    flush()
    return segs


# ----------------------------------------------------------------------------- #
# 4. Chunking: enforce size caps; carry the breadcrumb; split/merge as needed.
# ----------------------------------------------------------------------------- #

def _wc(s: str) -> int:
    return len(s.split())


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'])", text.replace("\n", " "))
    return [p.strip() for p in parts if p.strip()]


def _paragraphs(text: str) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return paras or [text.strip()]


def _pack(units: list[str], max_words: int) -> list[str]:
    """Greedily pack text units (paragraphs or sentences) into <= max_words chunks."""
    chunks: list[str] = []
    cur: list[str] = []
    n = 0
    for u in units:
        w = _wc(u)
        if cur and n + w > max_words:
            chunks.append("\n\n".join(cur))
            cur, n = [], 0
        cur.append(u)
        n += w
    if cur:
        chunks.append("\n\n".join(cur))
    return chunks


def _semantic_pack(text: str, max_words: int, model, threshold: float) -> list[str]:
    """Centroid-drift split: grow a chunk until a sentence drifts off its running mean."""
    import numpy as np
    sents = _split_sentences(text)
    if len(sents) <= 3:
        return _pack(_paragraphs(text), max_words)
    emb = model.encode(sents, normalize_embeddings=True, show_progress_bar=False)
    chunks: list[str] = []
    cur, cur_emb, words = [sents[0]], [emb[0]], _wc(sents[0])
    for i in range(1, len(sents)):
        centroid = np.mean(cur_emb, axis=0)
        sim = float(np.dot(emb[i], centroid) / (np.linalg.norm(centroid) + 1e-9))
        drift = sim < threshold and words >= max_words * 0.4     # don't cut a chunk that's barely started
        if drift or words >= max_words:
            chunks.append(" ".join(cur))
            cur, cur_emb, words = [sents[i]], [emb[i]], _wc(sents[i])
        else:
            cur.append(sents[i]); cur_emb.append(emb[i]); words += _wc(sents[i])
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def _resplit_oversized(pieces: list[str], hard_max: int) -> list[str]:
    out: list[str] = []
    for p in pieces:
        if _wc(p) <= hard_max:
            out.append(p)
        else:
            out.extend(_pack(_split_sentences(p), hard_max))
    return out


def chunk_segments(segs: list[dict], max_words: int, hard_max: int, min_words: int,
                   semantic: bool, model, threshold: float) -> list[dict]:
    raw: list[dict] = []
    for seg in segs:
        body = seg["body"].strip()
        if _wc(body) <= hard_max:
            pieces = [body]
        elif semantic and model is not None:
            pieces = _semantic_pack(body, max_words, model, threshold)
        else:
            pieces = _resplit_oversized(_pack(_paragraphs(body), max_words), hard_max)
        for j, p in enumerate(pieces):
            raw.append({"crumb": seg["crumb"], "page_start": seg["page_start"],
                        "page_end": seg["page_end"], "text": p,
                        "part": (j + 1, len(pieces)) if len(pieces) > 1 else None})
    return _merge_tiny(raw, min_words)


def _merge_tiny(chunks: list[dict], min_words: int) -> list[dict]:
    """Fold a below-minimum chunk into the previous one when they share a breadcrumb."""
    out: list[dict] = []
    for c in chunks:
        if out and _wc(c["text"]) < min_words and out[-1]["crumb"] == c["crumb"] and c["part"] is None:
            out[-1]["text"] += "\n\n" + c["text"]
            out[-1]["page_end"] = c["page_end"]
        else:
            out.append(c)
    return out


def enforce_token_cap(chunks: list[dict], max_tokens: int) -> list[dict]:
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
    except Exception:
        return chunks
    out: list[dict] = []
    for c in chunks:
        if len(enc.encode(c["text"])) <= max_tokens:
            out.append(c); continue
        for k, piece in enumerate(_pack(_split_sentences(c["text"]), max(50, max_tokens // 2))):
            nc = dict(c); nc["text"] = piece
            nc["part"] = (k + 1, 0)                            # 0 = "further token-split"
            out.append(nc)
    return out


# ----------------------------------------------------------------------------- #
# 5. Rendering.
# ----------------------------------------------------------------------------- #

def render(chunks: list[dict], segs: list[dict], meta: dict) -> str:
    lines = [f"# {meta['name']} — chunked",
             f"# {len(chunks)} chunks · {meta['pages']} pages · extractor: {meta['extractor']} · "
             f"mode: {'semantic' if meta['semantic'] else 'structural'} · caps: "
             f"{meta['max_words']}/{meta['hard_max']} words",
             "", "## Table of contents"]
    seen = set()
    for seg in segs:
        if not seg["crumb"]:
            continue
        key = tuple(seg["crumb"])
        if key in seen:
            continue
        seen.add(key)
        lvl = len(seg["crumb"])
        lines.append(f"{'  ' * (lvl - 1)}- {seg['crumb'][-1]}  (p.{seg['page_start']})")
    lines.append("")
    bar = "=" * 80
    for i, c in enumerate(chunks, 1):
        crumb = " > ".join(c["crumb"]) if c["crumb"] else "(preamble)"
        pp = f"p.{c['page_start']}" if c["page_start"] == c["page_end"] else f"pp.{c['page_start']}–{c['page_end']}"
        part = ""
        if c["part"]:
            part = f" · part {c['part'][0]}" + (f"/{c['part'][1]}" if c["part"][1] else "")
        lines += [bar, f"### [{crumb}] ({pp}) · chunk {i}/{len(chunks)}{part}", "", c["text"], ""]
    return "\n".join(lines)


def render_flat(pdf_path: str) -> str:
    lines, _ = extract_lines(pdf_path)
    out, cur_page = [], None
    for ln in lines:
        if ln["page"] != cur_page:
            cur_page = ln["page"]
            out.append(f"\n--- Page {cur_page} ---")
        out.append(ln["text"])
    return "\n".join(out).strip()


# ----------------------------------------------------------------------------- #
# 6. Driver.
# ----------------------------------------------------------------------------- #

def chunk_pdf(pdf_path: str, *, max_words: int, hard_max: int, min_words: int,
              semantic: bool, max_tokens: int | None, model_name: str) -> tuple[str, dict]:
    lines, extractor = extract_lines(pdf_path)
    if not lines:
        return "", {"pages": 0, "extractor": extractor, "chunks": 0}
    pages = max(ln["page"] for ln in lines)
    mark_headings(lines)
    segs = build_segments(lines)

    model = None
    if semantic:
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(model_name)
        except Exception as e:
            print(f"   (--semantic requested but sentence-transformers unavailable: {e}; "
                  f"falling back to paragraph splitting)", file=sys.stderr)

    chunks = chunk_segments(segs, max_words, hard_max, min_words, semantic, model, threshold=0.55)
    if max_tokens:
        chunks = enforce_token_cap(chunks, max_tokens)
    meta = {"name": Path(pdf_path).name, "pages": pages, "extractor": extractor,
            "semantic": semantic and model is not None, "max_words": max_words, "hard_max": hard_max}
    return render(chunks, segs, meta), {"pages": pages, "extractor": extractor, "chunks": len(chunks)}


def extract_single(pdf_path: str, output: str | None, args) -> None:
    if not os.path.exists(pdf_path):
        print(f"❌ PDF not found: {pdf_path}"); sys.exit(1)
    if args.flat:
        text, info = render_flat(pdf_path), {"chunks": 0, "extractor": "flat"}
    else:
        text, info = chunk_pdf(pdf_path, max_words=args.max_words, hard_max=args.max_words * 2,
                               min_words=args.min_words, semantic=args.semantic,
                               max_tokens=args.max_tokens, model_name=args.model)
    if not text:
        print(f"⚠️  No text extracted from: {pdf_path}"); sys.exit(1)
    output = output or str(Path(pdf_path).with_suffix(".txt"))
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(text, encoding="utf-8")
    tag = "flat" if args.flat else f"{info['chunks']} chunks via {info['extractor']}"
    print(f"✅ {tag}, {len(text):,} chars: {pdf_path} → {output}")


def batch(args) -> None:
    src, dst = "pdfs", "extracted_pdfs"
    if not os.path.isdir(src):
        print(f"❌ Input folder '{src}' not found. Add PDFs there, or pass a file path."); return
    os.makedirs(dst, exist_ok=True)
    pdfs = [f for f in os.listdir(src) if f.lower().endswith(".pdf")]
    if not pdfs:
        print(f"❌ No PDFs in '{src}'."); return
    for f in pdfs:
        extract_single(os.path.join(src, f), os.path.join(dst, f[:-4] + ".txt"), args)


def main() -> None:
    ap = argparse.ArgumentParser(description="Chunk a PDF into context-carrying sections.")
    ap.add_argument("pdf_path", nargs="?", help="PDF to chunk (omit to batch-process ./pdfs/)")
    ap.add_argument("--output", help="output .txt path")
    ap.add_argument("--flat", action="store_true", help="old behaviour: flat page-by-page dump")
    ap.add_argument("--semantic", action="store_true",
                    help="split long headerless sections by embedding-centroid drift")
    ap.add_argument("--max-words", type=int, default=350, help="soft target chunk size (words)")
    ap.add_argument("--min-words", type=int, default=40, help="merge chunks smaller than this")
    ap.add_argument("--max-tokens", type=int, default=None, help="hard token cap per chunk (needs tiktoken)")
    ap.add_argument("--model", default="all-MiniLM-L6-v2", help="sentence-transformer for --semantic")
    args = ap.parse_args()
    if args.pdf_path:
        extract_single(args.pdf_path, args.output, args)
    else:
        batch(args)


if __name__ == "__main__":
    main()
