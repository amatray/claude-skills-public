---
name: lit-review-verify
description: Use when the user wants to verify whether the citations in a LaTeX or markdown manuscript actually support the claims they're attached to, or wants a citation audit against their .bib. Triggers on "check my citations", "verify references", "citation audit", "do my citations actually support what I wrote", "audit bibliography against claims", or "/lit-review-verify". Not for producing a literature review or finding related papers (use /lit-review), and not for cleaning bib metadata (use /clean-bib).
argument-hint: "[path-to-tex-or-md-file] [--bib path-to-bib] [--section intro|litreview|all]"
allowed-tools: ["Read", "Write", "Edit", "Glob", "Grep", "Bash", "Agent", "AskUserQuestion", "mcp__bib-cleaner__scopus_abstract_retrieval", "mcp__bib-cleaner__scopus_search", "mcp__bib-cleaner__crossref_doi_lookup", "mcp__bib-cleaner__crossref_fuzzy_match", "mcp__bib-cleaner__openalex_search", "mcp__bib-cleaner__openalex_citing_papers", "mcp__bib-cleaner__semantic_scholar_search", "mcp__bib-cleaner__semantic_scholar_paper", "mcp__bib-cleaner__repec_ideas_search", "mcp__bib-cleaner__resolve_bibtex"]
---

# Citation Verification

Read a manuscript (.tex or .md), extract every substantive claim paired with a citation, and verify whether the cited paper actually supports that claim. Also suggest better or more appropriate references where the current citation is weak. The goal is to catch misattributions, stale references, and unsupported claims before a referee does.

## Input Parsing

Parse `$ARGUMENTS` for:
- **Path to manuscript** (required): A `.tex` or `.md` file to check.
- **`--bib` path** (optional): Explicit path to the .bib file. If omitted for .tex files, look for `\bibliography{...}` or `\addbibresource{...}` and resolve relative to the .tex file's directory. For .md files, look for a .bib file with the same base name in the same directory.
- **`--section` filter** (optional): `intro`, `litreview`, or `all` (default: `all`). For .tex files, section boundaries are detected by `\section{...}` commands; match liberally. For .md files, use `## Section Name` headers.

If no arguments provided, search the current working directory for `.tex` and `.md` files and ask which one to process.

## Workflow

### Phase 1: Extract Claim-Citation Pairs

**Step 1: Read the manuscript and detect format**

Determine if the file is LaTeX (.tex) or Markdown (.md).

**For .tex files:** Identify all sentences containing a citation command (`\cite`, `\citet`, `\citep`, `\citeauthor`, `\citeyear`, `\citealt`, `\citealp`, or natbib/biblatex variants). Extract the claim text, citation key(s), and line number.

**For .md files:** Identify all sentences containing inline citations in academic format:
- "Author (Year)" or "Author (Year, Journal)" e.g., "Hsieh and Klenow (2009, QJE)"
- "Author and Author (Year)" e.g., "Midrigan and Xu (2014, AER)"
- "Author, Author, and Author (Year)" e.g., "Gopinath, Kalemli-Ozcan, Karabarbounis, and Villegas-Sanchez (2017, QJE)"
- "Author et al. (Year)" e.g., "Bai et al. (2024)"
- Parenthetical: "(Author, Year)" or "(Author and Author, Year)"

For each citation, extract:
- The **claim text**: the sentence or clause making a substantive assertion.
- The **citation metadata**: author name(s), year, and journal (if present). These are used for DOI resolution.
- The **location**: line number in the file.

**Step 2: Filter out non-substantive citations**

Skip citations that don't make a verifiable claim:
- Parenthetical "see also" lists with no specific claim
- Self-citations to the current paper
- Citations in acknowledgments, appendix references to data sources, or bibliographic metadata

When in doubt, include rather than exclude.

**Step 3: Classify each pair**

| Type | What it means | Example |
|------|--------------|---------|
| **FINDING** | Attributes a specific empirical result, direction, or magnitude to the cited paper | "Hsieh and Klenow (2009) find that misallocation reduces TFP by 30-50% in India" |
| **FACTUAL** | States a fact or statistic and cites a source | "20% of new firms exit within five years (Dunne et al., 1988)" |
| **METHOD** | Cites a paper for its methodology | "Following Bartik (1991), we construct a shift-share instrument" |
| **GENERAL** | Broad reference to a literature or idea | "There is a large literature on financial frictions and misallocation" |

**Step 4: Proceed directly to verification**

Do NOT stop for user review. The extraction is internal bookkeeping. Proceed immediately to Phase 2.

### Phase 2: Resolve Citations

**Step 1: Parse the .bib file (if available)**

Read any .bib file(s). For each citation key, extract: title, author, year, journal, DOI, abstract (if present). If no .bib file exists (common for .md lit reviews), proceed with the metadata extracted from inline citations in Phase 1.

**Step 2: Query Zotero**

Use immutable URI mode to avoid locking conflicts:

```bash
sqlite3 "file:/Users/adrienmatray/Zotero/zotero.sqlite?mode=ro&immutable=1"
```

For citations WITH a DOI (from .bib), batch-query by DOI. For citations WITHOUT a DOI, use title matching (normalize: strip `{}` braces, lowercase, collapse whitespace, use `LIKE`). For .md files with only author/year, query by author last name + year.

For each citation, retrieve: (1) abstract, (2) whether it exists in Zotero, (3) PDF attachment path.

Batch queries: see references/zotero-queries.md (abstracts by DOI, PDF paths by DOI, title fallback).

### Phase 2b: Resolve DOIs for Citations Without One

Many citations (especially from .md files without a .bib) will lack DOIs after Phase 2. DOIs are essential for reliable abstract retrieval. Resolve them now.

For every citation that has no DOI after Zotero lookup, use `mcp__bib-cleaner__crossref_fuzzy_match` with a bibliographic query string constructed from the citation metadata:
- Query = "AuthorLastName Title Year" (if title is known from .bib or Zotero)
- Query = "AuthorLastName1 AuthorLastName2 Year JournalAbbrev" (if only inline citation metadata)

Launch all fuzzy match queries in a single parallel batch. For each result, accept the DOI if the returned title similarity score is > 70 (CrossRef scores on 0-100 scale) AND the year matches. Record the resolved DOI for use in Phase 3.

**Example:** For an inline citation "Hsieh and Klenow (2009, QJE)", the query would be:
```
"Hsieh Klenow 2009 Quarterly Journal of Economics"
```

### Phase 3: Fetch Abstracts and Verify

For each citation that still lacks an abstract after Phase 2/2b, fetch via MCP tools. The fallback chain is designed to degrade gracefully when any API is unavailable.

**Pre-check: Scopus health test.** Before any Scopus calls, run ONE test call with a known DOI (e.g., `10.1093/qje/qjt031`). If it returns an auth error (401/403) or times out, **skip ALL Scopus calls for the rest of this run** and log "Scopus unavailable" in the report. Do not waste time on N failing calls.

**Round 1 (parallel):** For citations WITH a DOI, launch `mcp__bib-cleaner__crossref_doi_lookup` for all of them. CrossRef is free, requires no auth, and returns abstracts for ~60% of economics papers. Simultaneously, for citations still WITHOUT a DOI, launch `mcp__bib-cleaner__crossref_fuzzy_match` again with broader queries.

**Round 2 (parallel, for citations still missing abstracts):** Launch `mcp__bib-cleaner__semantic_scholar_paper` for all citations that have a DOI but no abstract. Semantic Scholar has good coverage and returns abstracts that CrossRef sometimes lacks. Also launch `mcp__bib-cleaner__semantic_scholar_search` for any citations still without a DOI.

**Round 3 (parallel, still missing, only if Scopus passed health check):** Launch `mcp__bib-cleaner__scopus_abstract_retrieval` for remaining citations with DOIs. Scopus has the best coverage for Elsevier journals (JFE, JDE, JIE) but requires a valid API key.

**Round 4 (last resort, parallel):** For any citations still without abstracts:
- Launch `mcp__bib-cleaner__openalex_search` for title-based search
- Launch `mcp__bib-cleaner__repec_ideas_search` for working papers (NBER, CEPR, Fed series)

This yields at most 4 sequential rounds, each fully parallel across citations.

**Verification logic:**

For each claim-citation pair, compare the claim against the abstract (and any Zotero notes). Apply different strictness levels based on claim type:

| Claim Type | Strictness | What to check |
|-----------|------------|---------------|
| **FINDING** | Strict | The abstract must mention a result consistent with the claimed direction, mechanism, and context. If the claim says "X causes Y", the abstract should support that causal relationship, not just a correlation or the reverse direction. |
| **FACTUAL** | Medium | The abstract should be consistent with the stated fact. Exact numbers may not appear in the abstract, so look for consistency rather than exact match. |
| **METHOD** | Low | The abstract should mention or be consistent with the cited methodology. Only flag if there is a clear mismatch. |
| **GENERAL** | Lenient | Almost always fine. Only flag if the paper is clearly about a completely different topic. |

Assign a verdict to each pair:

| Verdict | Meaning |
|---------|---------|
| **SUPPORTED** | The abstract clearly supports the claim |
| **PARTIAL** | The abstract is related but the claim overstates, understates, or slightly misrepresents the finding |
| **MISMATCH** | The abstract contradicts or is clearly inconsistent with the claim |
| **UNCERTAIN** | Cannot determine from the abstract alone |
| **UNVERIFIABLE** | No abstract available from any source |

**Be conservative with MISMATCH.** Abstracts are summaries; the full paper may contain supporting evidence not mentioned in the abstract. When there is ambiguity, prefer UNCERTAIN over MISMATCH.

### Phase 3b: Parallel PDF Re-verification

After abstract-based verification, revisit any citation with verdict **UNCERTAIN** or **PARTIAL** that has a PDF in Zotero. The goal is to upgrade the verdict using the actual paper content.

**How to resolve PDF paths:** Zotero stores paths in two formats:
- `attachments:` prefix: Replace with `/Users/adrienmatray/Library/CloudStorage/Dropbox-Matray/Adrien Matray/Zotero_Library/`
- `storage:` prefix: Find the actual file with `find /Users/adrienmatray/Zotero/storage -name "FILENAME"` where FILENAME is the part after `storage:`

**Run PDF checks in parallel using agents.** For each UNCERTAIN/PARTIAL citation with a PDF, spawn an Agent with:
- The exact claim text and its location
- The citation metadata (author, year, title, journal)
- The resolved PDF path
- The current verdict and why it was UNCERTAIN/PARTIAL
- Instruction: read pages 1-5 of the PDF. If the claim references a specific table or result, read those pages too. Return a revised verdict with a one-sentence justification.

**Batching:** Launch up to 5 agents in a single message. Prioritize FINDING claims first, then FACTUAL, then METHOD.

### Phase 3c: Search for Better References

After verification, search for potentially better or more appropriate references. This phase catches cases where a cited paper is tangentially related but a better reference exists.

**When to search:** Only for claims with verdicts PARTIAL, MISMATCH, UNCERTAIN, or UNVERIFIABLE. Do NOT search for SUPPORTED claims (if the citation is correct, leave it alone).

**How to search:**

1. **For PARTIAL/MISMATCH claims:** Use `mcp__bib-cleaner__openalex_search` with keywords extracted from the claim text to find papers whose titles/topics more directly match the claim. Also use `mcp__bib-cleaner__openalex_citing_papers` on the cited paper to find newer work that extends or refines the result.

2. **For UNCERTAIN/UNVERIFIABLE claims:** Use `mcp__bib-cleaner__crossref_fuzzy_match` and `mcp__bib-cleaner__semantic_scholar_search` with the claim keywords to find papers that might be the intended reference (typo in author name, wrong year, etc.) or a better alternative.

**Criteria for suggesting an alternative:**
- The alternative paper's abstract more directly supports the specific claim being made
- The alternative is published in a peer-reviewed journal (prefer published over working papers)
- The alternative has a meaningful citation count (not obscure)
- For "newer work" suggestions: the alternative is more recent AND makes the same or stronger point

**Do NOT suggest alternatives when:**
- The claim is SUPPORTED (the current citation works fine)
- The alternative is only marginally better
- The alternative is a working paper version of the same published paper
- The claim is GENERAL (broad literature references don't need optimization)

Launch all alternative-reference searches in parallel. Limit to 1-2 alternatives per claim.

### Phase 4: Output Report

Create the output directory if needed, then save:

```
output/citation-verification-YYYY-MM-DD.md
```

Report structure: follow templates/report-template.md exactly.

Present the report summary to the user inline as well (not just the file). Only show the issues, never list SUPPORTED citations.

### Implementing Suggestions

Each MISMATCH and PARTIAL issue is numbered as "Suggestion N" (sequentially). When the user says "implement suggestion N" (or "accept N", "apply N", etc.):

1. Read the current file to locate the exact text to replace.
2. Apply the suggested fix using the Edit tool.
3. If the fix introduces a new citation key, add the bib entry to the .bib file.
4. Confirm the change with the file path and line number.

Multiple suggestions can be implemented at once (e.g., "implement suggestions 1 and 3").

**Writing suggested fixes:**

- The suggested fix must be a drop-in replacement for the exact text shown in the "Claim" field.
- Preserve the original sentence structure and style. Only change what is necessary.
- For PARTIAL matches where the claim overstates a finding, soften the language rather than removing the citation entirely.
- Always provide a bib entry block if the fix introduces a citation key not present in the .bib file.

## Rules

- Never use em dashes. Use commas, semicolons, or parentheses instead.
- Never fabricate abstracts or paper content. Every verification must be based on actual retrieved text.
- Always use immutable URI mode for Zotero queries.
- Be conservative with MISMATCH verdicts. When in doubt, mark UNCERTAIN.
- Respect the user's domain: this is applied macro/finance. Understanding econometric terminology (DiD, IV, RDD, shift-share) helps classify claims correctly.
- If MCP tools fail or are unavailable, report which citations could not be verified rather than silently skipping them. Log API status in the report summary.
- Do NOT stop after Phase 1. Run the entire pipeline (extract, resolve, verify, search alternatives, report) in one uninterrupted pass.
- The DOI resolution step (Phase 2b) is critical. Without DOIs, most abstract-retrieval APIs are useless. Always attempt CrossRef fuzzy match before declaring a citation unresolvable.
