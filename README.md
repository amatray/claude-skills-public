# Claude Code Skills for Academic Economists

Custom skills for Claude Code, focused on academic research workflows: paper auditing, literature review, LaTeX compilation, code review, and model solving.

## Installation

```bash
# 1. Clone this repo
git clone https://github.com/amatray/claude-skills-public ~/claude-skills

# 2. Symlink into Claude Code
ln -s ~/claude-skills/skills ~/.claude/skills

# 3. Restart Claude Code (required for new skill directories)

# 4. Verify: type / in Claude Code and confirm skills appear
```

**Important:** Each skill is a directory containing `SKILL.md`. Do NOT copy flat `.md` files into `~/.claude/skills/`; they will be silently ignored.

If you already have skills in `~/.claude/skills/`, merge the contents rather than replacing the directory:

```bash
# Alternative: copy individual skills instead of symlinking the whole directory
cp -r ~/claude-skills/skills/* ~/.claude/skills/
```

## Available Skills

| Skill | Description |
|-------|-------------|
| `/prompt` | Reformats rough, dictated requests into structured prompts before executing |
| `/prompt-only` | Same as /prompt but output only (does not execute) |
| `/audit-paper` | Comprehensive paper audit (typos, grammar, style, apparatus, structure) |
| `/audit-code` | Systematic code review against project conventions |
| `/review-plan` | Stress-test any plan with structured expert critique |
| `/review-plan-auto` | Automated iterative plan review with convergence detection and deterioration safeguards |
| `/review-plan-codex` | External second opinion on a plan from GPT-5.5 via the codex CLI, sandwiched between two internal auto-review passes (requires the `@openai/codex` CLI and a ChatGPT Pro login) |
| `/compile-latex` | Compile LaTeX documents, fix errors, re-compile until clean |
| `/lit-review-verify` | Verify literature review claims against sources |
| `/simulate-referee` | Simulate referee reports on a draft paper |
| `/solving-model` | Guided workflow for solving economic models |
| `/skill-creator` | Create, modify, and evaluate new skills |
| `/pdf-chunker` | Reliable chunked extraction from PDF files |
| `/overleaf` | Sync and compile Overleaf projects |
| `/restart` | Snapshot the current session to `restart.md` before clearing context, so a fresh conversation can resume work |
| `/memory` | Maintain a durable `PROJECT_MEMORY.md` at the project root (research question, decisions, data sources, workstreams, lessons) |

## Updating

```bash
cd ~/claude-skills && git pull
```

Skills update live within an active session (no restart needed for edits to existing skills).

## License

MIT
