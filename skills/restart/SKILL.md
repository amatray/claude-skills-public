---
name: restart
description: Use when the user says "restart", "wrap up", "snapshot before clearing", "pickup notes", "session recap", "session log", or wants to clear context and resume current work in a fresh conversation. Writes a structured restart.md to the project root, led by a Created / Sent / Waiting / Next recap and keeping goal, decisions, open items, files touched, and verification commands, appends that recap to a running SESSION_LOG.md, then instructs the user to type /clear.
argument-hint: "none"
allowed-tools: ["Write", "Read", "Edit", "Bash"]
---

# Restart — Pre-Clear Conversation Snapshot

Write a `restart.md` to the project root that captures the current conversation's state so the user can clear context with `/clear` and resume in a fresh conversation without losing anything important.

This skill cannot programmatically clear the conversation (`/clear` is a UI command the user types). Your job ends with the file on disk and a clear, copy-able resume prompt shown to the user, plus a one-line instruction telling them to run `/clear`.

## Why this exists

A naive end-of-session note loses context for two reasons: (1) it captures *what was done* but not the *reasoning* behind decisions, so a fresh Claude re-litigates settled choices, and (2) it omits the *do-not* list, so the fresh Claude re-tries dead ends. This skill fixes both by enforcing a schema that includes decisions-with-reasoning, abandoned approaches, and an explicit Do-NOT section.

## Step 1 — Detect project root

```bash
git rev-parse --show-toplevel 2>/dev/null || pwd
```

Store as `$PROJECT_ROOT`. Record whether this is a git repo.

## Step 2 — Check for existing restart.md

If git repo: run `git ls-files --error-unmatch restart.md 2>/dev/null`. If exit code is 0, `restart.md` is a tracked project file. Abort with:

> "`restart.md` is a tracked project file; writing a snapshot here would overwrite it. Rename or remove the tracked file first."

If `restart.md` exists but is NOT tracked (previous snapshot): move it to `batch_logs/restart_archive/` (create directories if needed), renamed with timestamp:

```bash
mkdir -p batch_logs/restart_archive
mv restart.md "batch_logs/restart_archive/restart_$(date -u +%Y%m%d_%H%M%S).md"
```

Inform the user the old snapshot was preserved.

## Step 3 — Capture git state (git repos only)

Run and record:

- `git branch --show-current`
- `git log -1 --oneline`
- `git status --short` (cap at 20 lines; if more, note "... and N more files"; if clean, record "working tree clean")
- `git diff --name-only` (cap at 20 lines; if more, note "... and N more files")
- `git diff --cached --name-only` (cap at 20 lines; if more, note "... and N more files")
- `git stash list` (include only if non-empty; cap at 5 entries)

Do NOT run `git diff` (full content). Name-only lists plus your own conversation recall are sufficient. Full diffs waste context budget and rarely add value the file paths alone don't already provide.

If not a git repo, omit the whole Git State section.

## Step 4 — Guard against thin conversations

This is a self-judgment heuristic, not a literal message count (you can't introspect the message log). If you cannot recall at least 3 distinct decisions or substantive actions from this session, ask:

> "The session looks thin. Write the restart anyway?"

Proceed only if the user confirms.

## Step 5 — Summarize the conversation

**Total word budget for sections 3–13 (Goal through Verification Commands), excluding Files Touched: 600 words.** If exceeded, trim "What was done" first, then "Decisions made". Each bullet: single line, max ~20 words.

**Source priority for recall:**

1. `git diff --name-only` and `git diff --cached --name-only` (from step 3)
2. Project memory files at `~/.claude/projects/<encoded-dir>/memory/` (if they exist and are relevant)
3. Any existing `handoff.md` in the project root (read but do not modify)
4. Your own recall of this conversation (earlier turns may have been compacted; if uncertain, omit rather than guess)

**Compaction awareness:** If you detect conversation summary/compaction markers (earlier turns replaced by a summary block), state this explicitly at the top of Goal and rely primarily on git state and memory files.

**Honesty rule:** If you cannot recall a decision or event with confidence, omit it. Note the gap with "(earlier context unavailable)".

**Escaping:** Escape literal backticks or pipe characters in interpolated values so they do not break the markdown.

### Sections to produce (in order)

| # | Section | Required? | Cap | Notes |
|---|---|---|---|---|
| 1 | Resume prompt block at top | required | — | Tells fresh Claude what to read |
| 2 | Git State | required if git repo | 20 files per list | Omit whole section if not a git repo |
| 3 | **Goal(s)** — 1–3 sentences, OR a bullet list if the session spanned multiple unrelated topics | required | — | The "why", not just the "what" |
| 4 | **Acceptance Criteria** — how to know the goal is done | optional | 5 bullets | Omit if the goal is self-evidently complete |
| 5 | **What Was Done** — actions and outcomes | required | 15 bullets | Single line each, max ~20 words |
| 6 | **Decisions Made** — choice + reasoning (the "why") | optional | 10 bullets | Format: `Choice — why` |
| 7 | **Constraints (This Task)** — overrides of CLAUDE.md defaults | optional | 5 bullets | e.g. "OLS not 2SLS in this script because…" |
| 8 | **What's Still Open** — actionable next steps in priority order | required | 10 bullets | First bullet = the immediate next action |
| 9 | **Blocked / Waiting On** — items NOT yet actionable | optional | 5 bullets | External deps, pending replies, awaited data |
| 10 | **Abandoned Approaches** — tried and rejected, with reason | optional | 5 bullets | Format: `Approach — reason it failed` |
| 11 | **Do NOT** — dead ends + off-limits, with one-line reason | optional | 5 bullets | Prevents fresh Claude from re-trying failed paths |
| 12 | **Key Variables / State** — runtime values, intermediate results | optional | 5 bullets | Backtick-wrap names |
| 13 | **Verification Commands** — quick checks of current state | optional | 5 commands | e.g. `git status`, `ls data/temp/`, `tail -n 20 batch_logs/run.log` |
| 14 | **Files Touched** — created / modified / deleted, with role | required | 30 files total | Source: `git diff --name-only` + recall |

**Omit-if-empty rule:** Any optional section with zero bullets is dropped entirely (header + body), not shown as "(none)". This keeps the file tight.

### The Session recap block (headline)

restart.md leads with a short, scannable `## Session recap` that groups the session into four buckets, sourced from the same recall. It is a summary view; the detailed sections below carry the depth for a fresh Claude.

- **Created**: new files or artifacts produced this session, each with a one-line purpose. Source: `git diff --name-only` plus recall; overlaps Files Touched (Created), kept terse here.
- **Sent**: external messages dispatched this session (email via the gmail MCP, Slack), with the returned message ID when there is one. Omit the group entirely if nothing was sent.
- **Waiting on {party}**: external dependencies and pending replies. Same items as Blocked / Waiting On, named by the party (for example "Waiting on IDB").
- **Ready, not started**: the immediate next actions, the same first entries as What's Still Open.

Close the block with one short sign-off line (for example "Everything is on disk; nothing is lost on clear."). The same block, dated, is prepended to `SESSION_LOG.md` in Step 6.

## Step 6 — Write restart.md

Write the file to `$PROJECT_ROOT/restart.md` using the template below. Replace all `{placeholders}` with actual values. Use `date -u +"%Y-%m-%d %H:%M UTC"` for the timestamp. The resume prompt must include the absolute path in double quotes. Do not stage or commit the file.

### Template

```
# Restart
<!-- Generated by /restart. Safe to delete after pickup. -->

**Session window:** {start_ts UTC} → {end_ts UTC}

> **Resume prompt** (copy into your next conversation):
>
> I'm continuing a session on this project. Read "{ABSOLUTE_PATH}/restart.md" for full context: goal, acceptance criteria, what's done, decisions, constraints, blockers, and what's still open. Also check `~/.claude/projects/<encoded-dir>/memory/MEMORY.md` for any project-specific memory. If restart.md is not at the path above, check the current working directory. Then confirm you've read it and ask which open item to start with.

---

## Session recap
<!-- Scannable headline; details in the sections below. -->

**Created**
- `{path}`: {purpose}

**Sent** (omit this group if nothing was sent)
- {recipient / subject}: ID {message-id}

**Waiting on {party}**
- {item}

**Ready, not started**
- {immediate next action}

{one-line sign-off}

---

## Git State
- **Branch**: {branch}
- **Last commit**: {hash} {message}
- **Working tree**: {clean | list, ≤20}
- **Staged**: {list, ≤20 | omit if empty}
- **Stash**: {list, ≤5 | omit if empty}

## Goal
{1–3 sentences, OR a short bullet list if multi-topic}

## Acceptance Criteria
- {bullet}

## What Was Done
- {bullet}

## Decisions Made
- {choice} — {why}

## Constraints (This Task)
- {bullet}

## What's Still Open
1. {highest priority — immediate next action}
2. ...

## Blocked / Waiting On
- {bullet}

## Abandoned Approaches
- {approach} — {reason it failed}

## Do NOT
- {action} — {one-line reason}

## Key Variables / State
- `{name}`: {value or description}

## Verification Commands
- `{cmd}` — {what it checks}

## Files Touched
**Created:**
- `path/to/file` — purpose

**Modified:**
- `path/to/file` — what changed

**Deleted:**
- `path/to/file` — why

---
*Generated by `/restart` on {YYYY-MM-DD HH:MM UTC}.*
```

For the `{encoded-dir}` placeholder in the resume prompt, derive it from the current working directory: replace `/` with `-` (e.g., `/Users/adrienmatray` → `-Users-adrienmatray`). If unsure, leave the literal `<encoded-dir>` in the prompt; the fresh Claude can resolve it.

### Prepend the recap to SESSION_LOG.md

After restart.md is written, add the same recap to a running log so it accumulates across sessions. `SESSION_LOG.md` is a persistent CHANGELOG-style file (newest entry on top), the narrative companion to `PROJECT_MEMORY.md`, and is exempt from Hard Rule #13.

1. If `$PROJECT_ROOT/SESSION_LOG.md` does not exist, create it with a header:

```
# Session Log: {project name}

Newest session on top. Each entry is a session recap: what was created, what was sent, what we are waiting on, and what is ready next. Running narrative companion to PROJECT_MEMORY.md. CHANGELOG style, so it accumulates.
```

2. Prepend a new dated entry directly under the header, above any existing entries, using the Session recap block with a `## {YYYY-MM-DD}` header (`date -u +%Y-%m-%d`):

```
## {YYYY-MM-DD}

**Created**
- `{path}`: {purpose}

**Sent** (omit if nothing was sent)
- {recipient / subject}: ID {message-id}

**Waiting on {party}**
- {item}

**Ready, not started**
- {immediate next action}
```

Read the existing file first, then write it back with the new entry inserted after the header block. Do not rewrite or dedupe older entries; the log is append-only at the top.

## Step 7 — Check .gitignore coverage

Check whether `restart.md` and `batch_logs/` are covered by `.gitignore`. If either is NOT covered, display the exact lines the user should add:

```
restart.md
batch_logs/
```

Do not modify `.gitignore` automatically.

`SESSION_LOG.md` is persistent project documentation, so it is not gitignored by default; it is meant to live alongside the code. For a project flagged as confidential, note that `SESSION_LOG.md` can reference external correspondence and should be reviewed before it reaches any remote.

## Step 8 — Confirm and prompt the user to clear

Tell the user, in this order:

1. The absolute path where `restart.md` was written, and that the recap was prepended to `SESSION_LOG.md`.
2. The resume prompt, displayed in a copy-able block (the same block that's inside the file's `> Resume prompt` quote).
3. A one-line instruction:

> Copy the resume prompt above, then type `/clear` in this conversation, then paste the resume prompt as your first message in the fresh conversation.

That ends the skill. The user runs `/clear` themselves; the skill cannot do it.
