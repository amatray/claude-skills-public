#!/usr/bin/env bash
# codex-preflight.sh -- verifies the codex CLI is reachable and authenticated,
# then prints a machine-readable summary for the caller to parse.
#
# Usage: codex-preflight.sh <slug> <plan_path>
#
# Exit codes:
#   0   preflight passed; codex is reachable
#   1   bad arguments OR plan missing
#   2   codex is not reachable
#
# Stdout (on success): machine-readable KEY=VALUE lines including TRANSPORT,
# SLUG, PLAN_PATH, TOKEN_ESTIMATE, CODEX_VERSION.

set -euo pipefail

SLUG="${1:?usage: codex-preflight.sh <slug> <plan_path>}"
PLAN_PATH="${2:?usage: codex-preflight.sh <slug> <plan_path>}"

if [[ ! -f "$PLAN_PATH" ]]; then
  echo "FAIL: plan_path does not exist: $PLAN_PATH" >&2
  exit 1
fi

# ----------------------------------------------------------------------------
# codex reachability + version
# ----------------------------------------------------------------------------

CODEX_OK=0
if command -v codex >/dev/null 2>&1; then
  # codex may be wrapped as a shell function; use `command codex` to bypass.
  if command codex --version >/dev/null 2>&1; then
    CODEX_OK=1
  fi
fi

if [[ $CODEX_OK -ne 1 ]]; then
  echo "FAIL: codex CLI is not reachable." >&2
  echo "  Install: npm install -g @openai/codex@latest" >&2
  echo "  Authenticate: codex login" >&2
  exit 2
fi

CODEX_VERSION=$(command codex --version 2>/dev/null | head -1 | awk '{print $NF}')

# ----------------------------------------------------------------------------
# Token estimate (codex has no dry-run; estimate via char count, ~4 chars / token)
# ----------------------------------------------------------------------------

CHARS=$(wc -c < "$PLAN_PATH")
CHARS_PROMPT=$(wc -c < "$HOME/.claude/skills/review-plan-codex/references/codex-review-prompt-strict.md" 2>/dev/null || echo 0)
# Add codex's ~30k scaffolding overhead.
TOKEN_COUNT=$(( (CHARS + CHARS_PROMPT) / 4 + 30000 ))

# ----------------------------------------------------------------------------
# Machine-readable summary
# ----------------------------------------------------------------------------

echo "PREFLIGHT_OK"
echo "TRANSPORT=codex"
echo "SLUG=$SLUG"
echo "PLAN_PATH=$PLAN_PATH"
echo "TOKEN_ESTIMATE=$TOKEN_COUNT"
echo "CODEX_VERSION=$CODEX_VERSION"
echo "CODEX_SANDBOX_LOOP=workspace-write"
echo "CODEX_SANDBOX_TRIAGE=read-only"
echo "NOTE: codex adds ~30k tokens of agentic scaffolding per call."
echo "NOTE: total prompt+plan content should stay under ~150k chars to leave headroom under the codex context window."

exit 0
