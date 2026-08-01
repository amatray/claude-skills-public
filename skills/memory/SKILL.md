---
name: memory
description: Use ONLY when the user types the slash command "/memory". On first run in a project, bootstraps PROJECT_MEMORY.md at the project root with research question, decisions, data sources, architecture, workstreams, open questions, and lessons learned. On subsequent runs, applies an update sourced from the current session: volatile sections auto-apply, durable sections show a unified diff and require y/N confirmation. Always archives the prior version. Do NOT trigger on natural language; this skill is slash-invoked only.
argument-hint: "none"
allowed-tools: ["Read", "Write", "Edit", "Bash"]
---

# /memory — Durable Project Memory

Maintain a `PROJECT_MEMORY.md` at the project root capturing long-term project documentation: research question, decisions, data sources, architecture, workstreams, open questions, and lessons learned. This is durable cross-session memory, distinct from the ephemeral `handoff.md` (session handoff) and from the user-level auto-memory in `~/.claude/projects/<encoded-cwd>/memory/`.

## Execution model and state-passing

The Claude Code Bash tool starts a **fresh shell on every invocation**: environment variables do NOT persist across calls. Files do persist; `cd` persists within the main session. On macOS the Bash tool runs **zsh 5.9**, not bash — snippets must be zsh-compatible.

To pass state between phases, prefer one of:
1. **Single Bash call with chaining** — preferred for race-sensitive sequences (mtime check, bootstrap collision close).
2. **Print KEY=VAL block, read it back** — Claude reads the output and substitutes literal values into the next Bash call.
3. **Temp state file** at `/tmp/memory-skill-$$.env` — only when (1) and (2) are awkward.

## Phase 0 — Detect project root and mode

Run as a single Bash call:

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)

# Safety guards: refuse to operate on dangerous roots.
# Match EXACT paths, not prefixes — `/tmp/myproject` and `/private/tmp/myproject`
# are legitimate sandbox locations and must not be blocked.
case "$PROJECT_ROOT" in
  "$HOME"|/|/Users|/tmp|/private/tmp|/var|/private/var|/etc|/usr|/System|/Library|/private)
    echo "GUARD_TRIGGERED=$PROJECT_ROOT"; exit 1;;
esac

# Also refuse home-subdirectories that are not project work:
# ~/Desktop, ~/Documents, ~/Downloads, ~/Library, ~/.Trash by themselves.
case "$PROJECT_ROOT" in
  "$HOME/Desktop"|"$HOME/Documents"|"$HOME/Downloads"|"$HOME/Library"|"$HOME/.Trash")
    echo "GUARD_TRIGGERED=$PROJECT_ROOT"; exit 1;;
esac

# Mode detection.
if [ -f "$PROJECT_ROOT/PROJECT_MEMORY.md" ]; then
  MODE=update
  START_MTIME=$(stat -f %m "$PROJECT_ROOT/PROJECT_MEMORY.md")
else
  MODE=bootstrap
  START_MTIME=
fi

# Note whether this is a git repo.
IS_GIT=$(git -C "$PROJECT_ROOT" rev-parse --is-inside-work-tree 2>/dev/null || echo "false")

echo "PROJECT_ROOT=$PROJECT_ROOT"
echo "MODE=$MODE"
echo "START_MTIME=$START_MTIME"
echo "IS_GIT=$IS_GIT"
```

If `GUARD_TRIGGERED` is printed: abort and tell the user to run `/memory` from a real project directory.

If `IS_GIT=false`: display the inferred `$PROJECT_ROOT` and ask the user to confirm before proceeding. Do not write without confirmation in this case.

## Phase 1A — Bootstrap (first run, MODE=bootstrap)

### Gather

- **Project name**: directory basename. If `README.md`, `CLAUDE.md`, or `main.tex` exists, use its title where more informative.
- **Top-level files**: read each (cap 200 lines): `README.md`, `CLAUDE.md`, any `*.tex` matching `main` or `paper`, top-level `*.do` files. For `*.tex`, additionally extract the first `\title{...}` and `\author{...}` lines.
- **Directory tree** (capped at 50 lines):
  ```bash
  tree -L 2 -d -I '.git|node_modules|.venv|__pycache__|.DS_Store' 2>/dev/null \
    || find . -maxdepth 2 -type d \
       -not -path '*/.*' -not -path '*/node_modules*' -not -path '*/__pycache__*' \
       | head -50
  ```
- **Conversation context**: collaborators, decisions, data sources discussed in this session. If the session shows compaction markers, flag it and rely on file evidence over recall.
- **Git state** (if git repo): branch, remote, last 5 commits with `git log -5 --oneline`.

### Show, then write

Render the proposed `PROJECT_MEMORY.md` content in chat and ask the user to confirm before writing to disk. First run is the foundation; a wrong bootstrap propagates.

On confirmation, write using a **TOCTOU-safe** pattern that aborts if the file appeared between detection and write:

```bash
ERR=$( ( set -o noclobber
cat > "$PROJECT_ROOT/PROJECT_MEMORY.md" <<'MEM_EOF'
... templated content ...
MEM_EOF
) 2>&1 1>/dev/null ) || { echo "Bootstrap aborted: $ERR"; exit 1; }
```

On zsh the collision error reads `file exists: <path>`; it is preserved in the abort message.

On bootstrap, set both `Last Updated` and `Last Verified` to the same write timestamp.

## Phase 1B — Update (subsequent run, MODE=update)

### 1. Read existing PROJECT_MEMORY.md.

### 2. Identify session deltas

Use this source priority. Use the highest-confidence source first; combine only if consistent.

**(a) Git history since the last memory write** (preferred when the file is tracked):

```bash
cd "$PROJECT_ROOT"
if git ls-files --error-unmatch PROJECT_MEMORY.md > /dev/null 2>&1; then
  LAST_MEM_COMMIT=$(git log -1 --format=%H -- PROJECT_MEMORY.md)
  git log "$LAST_MEM_COMMIT..HEAD" --oneline
  git diff --name-only "$LAST_MEM_COMMIT" HEAD
  git diff --cached --name-only -- PROJECT_MEMORY.md  # surface pending staged edits
else
  # Untracked: fall back to mtime
  git log --since="$(stat -f %Sm -t %Y-%m-%dT%H:%M:%S PROJECT_MEMORY.md)" --oneline
  git diff --name-only HEAD
fi
```

Avoid bare mtime when the file is tracked — mtime moves on every `git checkout` or `git pull`.

**(b) JSONL transcript** of the active session. The encoding rule (empirically verified against `~/.claude/projects/`): replace each `/` in the absolute cwd with `-`; for any path segment whose first character is `_` or `.`, **strip that character and prepend `-`**.

```bash
ENCODED_CWD=$(pwd | python3 -c '
import sys
p = sys.stdin.read().strip()
parts = p.split("/")
out = []
for seg in parts:
    if not seg:
        out.append("")
    elif seg[0] in ("_", "."):
        out.append("-" + seg[1:])
    else:
        out.append(seg)
print("-".join(out))
')
LATEST_JSONL=$(ls -t "$HOME/.claude/projects/$ENCODED_CWD"/*.jsonl 2>/dev/null | head -1)
```

**Unit check (must hold)**: for `/Users/adrienmatray/Library/CloudStorage/Dropbox-Matray/_AdrienTeam/_FedStuff/Seminars`, `ENCODED_CWD` must equal `-Users-adrienmatray-Library-CloudStorage-Dropbox-Matray--AdrienTeam--FedStuff-Seminars`.

If `$LATEST_JSONL` is empty, skip this source.

**(c) Model recall** of the current conversation, with the honesty rule: **omit rather than guess.** If the conversation has been compacted and you cannot confidently recall a decision, do not include it.

If (a), (b), (c) yield no evidence for a proposed change, do not write that change.

### 3. Validate staleness

Strip fenced code blocks from the existing `Directory Structure`, `Data Sources`, and `External References` sections, then extract inline-code tokens:

```bash
grep -oE '`[^`]+`' "$PROJECT_ROOT/PROJECT_MEMORY.md"
```

For each extracted token that contains `/` or ends in a known file extension, test with `[ -e "$token" ]`. Collect missing paths. Do NOT bump `Last Verified` if any are missing.

### 4. Archive prior version

```bash
mkdir -p "$PROJECT_ROOT/batch_logs/project_memory_archive"
cp "$PROJECT_ROOT/PROJECT_MEMORY.md" \
   "$PROJECT_ROOT/batch_logs/project_memory_archive/PROJECT_MEMORY_$(date -u +%Y%m%d_%H%M%S).md"

# Rotation: keep 30 most recent.
ls -t "$PROJECT_ROOT/batch_logs/project_memory_archive"/PROJECT_MEMORY_*.md 2>/dev/null \
  | tail -n +31 | xargs -r rm --
```

### 5. Parallel-session race check (BEFORE any user prompt or write)

```bash
CUR_MTIME=$(stat -f %m "$PROJECT_ROOT/PROJECT_MEMORY.md")
[ "$CUR_MTIME" = "$START_MTIME" ] || { echo "RACE_DETECTED"; exit 1; }
```

If `RACE_DETECTED`: abort with "PROJECT_MEMORY.md was modified by another process during this run. Re-run /memory to merge." Re-check this guard a second time **immediately before** the actual write (last-chance TOCTOU close).

### 6. Apply patches in two tiers

**Volatile sections (auto-apply, no preview):**
- `Project Identity` -> only the `Status` field
- `Active Workstreams` (replace in place)
- `Open Questions / Blockers` (add new, remove resolved)
- `Directory Structure` (refresh wholesale via tree/find)
- `Last Updated` (bump to now)
- `Last Verified` (bump **only if** step 3 returned zero missing paths)

**Durable sections (show unified diff in chat, REQUIRE confirmation):**
- `Key Decisions` (append-only)
- `Data Sources` (append; flag stale)
- `Lessons Learned` (append-only)
- `External References` (append; flag stale)

Confirmation grammar: accept `y`, `Y`, `yes`, `YES` (case-insensitive). Anything else, including empty, skips the durable patch. Volatile sections still apply when durable is skipped.

**Never auto-edit without explicit user instruction:**
- `Research Question / Goal`
- `Project Identity` fields other than `Status`

### 7. Post-write summary (one line)

```
PROJECT_MEMORY.md updated: +N decisions, +M lessons, K stale paths flagged.
Restore prior: cp batch_logs/project_memory_archive/PROJECT_MEMORY_<ts>.md PROJECT_MEMORY.md
```

## Phase 2 — Report

Display: absolute path, mode (`bootstrap` or `update`), one-line change summary including the undo command.

Do **not** stage or commit. Do **not** suggest gitignoring `PROJECT_MEMORY.md` by default — it is project documentation intended to live alongside code in git. Suggest gitignore only if the user has flagged the project as containing sensitive content. Do confirm that `batch_logs/` is in `.gitignore`; if not, show the exact line to add.

## Schema for PROJECT_MEMORY.md (8 sections)

Separator is `:` or `,`. **Never** use `--` or `---` (Hard Rule #2). Each Key Decision and Lesson Learned carries an optional evidence pointer in parentheses. Paths must live inside backticks so the staleness scanner can extract them.

```markdown
# Project Memory: {project name}

<!-- Maintained by /memory. Long-term project documentation. -->
<!-- Last updated: {YYYY-MM-DD HH:MM UTC} -->
<!-- Last verified: {YYYY-MM-DD HH:MM UTC} (paths and references cross-checked) -->

## Research Question / Goal
{1 to 3 sentences}

## Project Identity
- **Status**: Active | Paused | Complete
- **Lead**: {name}
- **Collaborators**: {name (role), ...}
- **Timeline**: {start} to {target or open-ended}
- **Repository / location**: `{path or URL}`

## Key Decisions
- {decision, including methodology and identification choices}: {short why, dated YYYY-MM} (see `commit abc1234` or `handoff_20260512.md`)

## Data Sources
- `{dataset path}`: {what it covers, where stored, access notes}

## Directory Structure
{tree output, fenced, capped at 50 lines}

## Active Workstreams
- {workstream}: {phase, owner, ETA}

## Open Questions / Blockers
- {question}: {owner, next step}

## Lessons Learned
- {what was tried, why it did not work, what to do instead} (see `commit abc1234`)

## External References
- `{Overleaf URL or Dropbox path or Linear issue}`
```

Sections with no content are dropped entirely.

## Section caps

| Section | Cap |
|---|---|
| Research Question | 3 sentences |
| Key Decisions | 15 bullets |
| Data Sources | 10 bullets |
| Active Workstreams | 8 bullets |
| Open Questions | 10 bullets |
| Lessons Learned | 15 bullets |

**Global soft cap**: 400 lines. When exceeded, the skill surfaces a one-line prompt suggesting manual review. No silent eviction.

When a per-section cap is hit on auto-update, the oldest entry is moved to the archived prior version and removed from the live file. The user is notified in the post-write summary (not silent).

## Compaction awareness and honesty

If you detect that earlier conversation turns have been replaced by summary blocks, state this explicitly at the top of the chat output and rely primarily on git diff and JSONL evidence. If you cannot recall a decision or event with confidence, omit it rather than guess.

## Hard Rules this skill must follow

- **#2**: no `--` or `---` anywhere in `PROJECT_MEMORY.md`. Use `:` or `,`.
- **#6**: archives go to `batch_logs/project_memory_archive/`.
- **#9**: each Key Decision and Lesson Learned should carry an evidence pointer when possible.
