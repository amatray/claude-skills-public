#!/usr/bin/env python3
"""
Validate a skill folder against the Agent Skills specification and house conventions.

Usage: python3 quick_validate.py <skill_directory> [<skill_directory> ...]

Prints every finding, sorted into ERROR, WARN and NOTE. Exits 1 if any skill has an
error, 0 otherwise. Warnings and notes never change the exit code.

Standard library only: runs on any python3 with nothing installed. When PyYAML happens
to be available it is used for one extra warning (frontmatter a strict YAML parser
rejects); otherwise a conservative check stands in for it.

`validate_skill(path)` returns (ok, message) for callers such as package_skill.py.
`collect_findings(path)` returns the full list of findings.
"""

import os
import re
import sys
from pathlib import Path

# Frontmatter keys: the specification's, plus the Claude Code keys this setup uses.
SPEC_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
CLAUDE_CODE_KEYS = {"argument-hint", "model", "disable-model-invocation"}
ALLOWED_KEYS = SPEC_KEYS | CLAUDE_CODE_KEYS

# Size limits from the specification: SKILL.md under 500 lines, body under ~5,000 tokens.
MAX_SKILL_LINES = 500
MAX_BODY_TOKENS = 5000
CHARS_PER_TOKEN = 4  # rough proxy; no tokenizer dependency

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
KEY_LINE = re.compile(r"^([A-Za-z0-9_-]+):(?:\s+(.*)|\s*)$")
# A machine-specific path: home-relative or absolute under /Users.
MACHINE_PATH = re.compile(r"(?:~|\$HOME|\$\{HOME\}|/Users/[^/\s`'\"]+)/[^\s`'\")\]>,;]*")
HOME_PREFIX = re.compile(r"^(?:~|\$HOME|\$\{HOME\}|/Users/[^/\s`'\"]+)/")
PARENT_REF = re.compile(r"(?<![\w./])\.\./[\w.-]+")
EXEMPT_PREFIXES = (".claude/plans/", ".claude/projects/")
SKILL_ROOTS = (".claude/skills/", ".claude-fed/skills/", "claude-core/skills/")


class Finding:
    def __init__(self, level, message):
        self.level = level  # "ERROR", "WARN" or "NOTE"
        self.message = message

    def __repr__(self):
        return f"{self.level}: {self.message}"


# ---------------------------------------------------------------------------
# Frontmatter parsing (lenient, standard library)
# ---------------------------------------------------------------------------

def split_frontmatter(content):
    """Return (frontmatter_text, body, frontmatter_line_count) or None."""
    if not content.startswith("---"):
        return None
    lines = content.split("\n")
    if lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:]), i + 1
    return None


def _unquote(value):
    v = value.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        inner = v[1:-1]
        if v[0] == '"':
            inner = inner.replace('\\"', '"').replace("\\\\", "\\")
        else:
            inner = inner.replace("''", "'")
        return inner, True
    return v, False


def _flow_list(value):
    inner = value.strip()[1:-1]
    items = [p.strip() for p in re.split(r",(?=(?:[^\"']*[\"'][^\"']*[\"'])*[^\"']*$)", inner)]
    return [_unquote(p)[0] for p in items if p]


def parse_frontmatter(text):
    """Parse frontmatter into a dict.

    Reads plain and quoted values, `|` and `>` block scalars, inline and indented
    lists, and one level of nested map. Returns (data, problems, plain_values) where
    problems are lines it could not read and plain_values maps key -> unquoted
    single-line value (used for the strict-YAML check).
    """
    lines = text.split("\n")
    data, problems, plain = {}, [], {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if line[0] in " \t":
            problems.append(f"line {i + 2}: unexpected indentation")
            i += 1
            continue
        m = KEY_LINE.match(line)
        if not m:
            problems.append(f"line {i + 2}: not a `key: value` line")
            i += 1
            continue
        key, value = m.group(1), (m.group(2) or "").rstrip()
        # Gather the indented block that belongs to this key.
        j = i + 1
        block = []
        while j < len(lines) and (not lines[j].strip() or lines[j][0] in " \t"):
            block.append(lines[j])
            j += 1
        while block and not block[-1].strip():
            block.pop()
        if value[:1] in ("|", ">"):
            indent = min((len(b) - len(b.lstrip()) for b in block if b.strip()), default=0)
            body = [b[indent:] for b in block]
            if value[0] == "|":
                data[key] = "\n".join(body).strip("\n")
            else:
                paragraphs = "\n".join(body).split("\n\n")
                data[key] = "\n".join(" ".join(p.split()) for p in paragraphs).strip()
        elif value.startswith("[") and value.endswith("]"):
            data[key] = _flow_list(value)
        elif value == "" and block:
            stripped = [b.strip() for b in block if b.strip()]
            if all(s.startswith("- ") or s == "-" for s in stripped):
                data[key] = [_unquote(s[2:])[0] for s in stripped]
            else:
                nested = {}
                for s in stripped:
                    nm = KEY_LINE.match(s)
                    if nm:
                        nested[nm.group(1)] = _unquote(nm.group(2) or "")[0]
                    else:
                        problems.append(f"under `{key}`: cannot read `{s[:40]}`")
                data[key] = nested
        else:
            scalar, quoted = _unquote(value)
            if block and not quoted:
                # Plain scalar continued on indented lines folds into one line.
                scalar = " ".join([scalar] + [b.strip() for b in block if b.strip()])
            data[key] = scalar
            if not quoted:
                plain[key] = scalar
        i = j
    return data, problems, plain


def strict_yaml_problem(text, plain_values):
    """Return how a strict YAML parser would misread the frontmatter, or None."""
    for key, value in plain_values.items():
        # Strict YAML ends a plain value at ` #` and drops the rest as a comment, silently.
        if " #" in value:
            return f"`{key}` has an unquoted ` #`, so everything after it is dropped as a comment"
    try:
        import yaml  # optional
    except ImportError:
        yaml = None
    if yaml is not None:
        try:
            yaml.safe_load(text)
            return None
        except yaml.YAMLError as e:
            mark = getattr(e, "problem_mark", None)
            where = f" (frontmatter line {mark.line + 1})" if mark else ""
            return f"it fails to parse: {getattr(e, 'problem', 'parse error')}{where}"
    for key, value in plain_values.items():
        if ": " in value or value.endswith(":"):
            return f"`{key}` has an unquoted `: ` inside its value, so it fails to parse"
        if value[:1] in "&*!%@`{":
            return f"`{key}` starts with `{value[0]}`, which strict YAML reserves"
    return None


# ---------------------------------------------------------------------------
# Shared-skill detection
# ---------------------------------------------------------------------------

def manifest_dir():
    env = os.environ.get("SKILL_MANIFEST_DIR")
    if env:
        return Path(env).expanduser()
    return Path.home() / "claude-core"


def shared_skill_names():
    """Skill names listed in PUBLIC_SKILLS.txt or LAB_SKILLS.txt. Missing files mean none."""
    names = set()
    for fname in ("PUBLIC_SKILLS.txt", "LAB_SKILLS.txt"):
        path = manifest_dir() / fname
        try:
            lines = path.read_text().splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                names.add(line.split("/")[0])
    return names


def is_shared(name):
    return name.endswith("-idb") or name in shared_skill_names()


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def _scan_paths(skill_path, name, shared):
    """Machine-specific paths and ../ references in SKILL.md and references/."""
    files = [skill_path / "SKILL.md"]
    refs = skill_path / "references"
    if refs.is_dir():
        files += sorted(refs.rglob("*.md"))
    own, core, other, parent = [], [], [], []
    for f in files:
        try:
            text = f.read_text(errors="replace")
        except OSError:
            continue
        rel = f.relative_to(skill_path)
        for n, line in enumerate(text.splitlines(), 1):
            for m in MACHINE_PATH.finditer(line):
                after = HOME_PREFIX.sub("", m.group(0))
                if after.startswith(EXEMPT_PREFIXES):
                    continue
                where = f"{rel}:{n} `{m.group(0)}`"
                if any(after.startswith(r + name + "/") or after == r + name for r in SKILL_ROOTS):
                    own.append(where)
                elif after.startswith("claude-core/") or after == "claude-core":
                    core.append(where)
                else:
                    other.append(where)
            for m in PARENT_REF.finditer(line):
                parent.append(f"{rel}:{n} `{m.group(0)}`")

    def listing(items, cap=5):
        shown = "; ".join(items[:cap])
        return shown + (f"; and {len(items) - cap} more" if len(items) > cap else "")

    out = []
    if shared:
        fix = "write it as `<this skill>/...` (the folder this SKILL.md is in), not a bare relative path"
        if own:
            out.append(Finding("ERROR", f"shared skill calls its own files by a machine path; {fix}: {listing(own)}"))
        if core:
            out.append(Finding("ERROR", f"shared skill points into ~/claude-core/, which other machines do not have: {listing(core)}"))
        if other:
            out.append(Finding("WARN", f"shared skill uses machine-specific paths; copy what it needs into the skill, drop it, or accept it works only here: {listing(other)}"))
        if parent:
            out.append(Finding("WARN", f"shared skill reaches outside its folder with `../`; it breaks if installed without that sibling: {listing(parent)}"))
    else:
        total = len(own) + len(core) + len(other) + len(parent)
        if total:
            out.append(Finding("NOTE", f"{total} machine-specific or `../` path(s); fine while the skill stays on this machine. First: {(own + core + other + parent)[0]}"))
    return out


def collect_findings(skill_path):
    """Return every finding for one skill folder."""
    skill_path = Path(skill_path).resolve()
    findings = []
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return [Finding("ERROR", "SKILL.md not found")]
    content = skill_md.read_text(errors="replace")
    split = split_frontmatter(content)
    if split is None:
        return [Finding("ERROR", "no YAML frontmatter: SKILL.md must start with a `---` block closed by `---`")]
    fm_text, body, _ = split
    data, problems, plain = parse_frontmatter(fm_text)
    for p in problems:
        findings.append(Finding("ERROR", f"frontmatter cannot be read: {p}"))

    strict = strict_yaml_problem(fm_text, plain)
    if strict and not problems:
        findings.append(Finding("WARN", f"frontmatter works in Claude Code but a strict YAML parser misreads it: {strict}. Put the value in double quotes."))

    # Keys
    for key in sorted(set(data) - ALLOWED_KEYS):
        if key == "version":
            findings.append(Finding("WARN", "top-level `version` is not a frontmatter field; move it under `metadata:` as `version`"))
        else:
            findings.append(Finding("WARN", f"unknown frontmatter key `{key}`"))

    # Name
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        findings.append(Finding("ERROR", "missing `name` in frontmatter"))
        name = skill_path.name
    else:
        name = name.strip()
        if not NAME_RE.match(name):
            findings.append(Finding("ERROR", f"name `{name}` must be lowercase letters, digits and single hyphens, not starting or ending with a hyphen"))
        if len(name) > 64:
            findings.append(Finding("ERROR", f"name is {len(name)} characters; the maximum is 64"))
        if name != skill_path.name:
            findings.append(Finding("ERROR", f"name `{name}` does not match the folder name `{skill_path.name}`"))

    # Description
    desc = data.get("description")
    if not isinstance(desc, str) or not desc.strip():
        findings.append(Finding("ERROR", "missing or empty `description` in frontmatter"))
    else:
        desc = desc.strip()
        if len(desc) > 1024:
            findings.append(Finding("ERROR", f"description is {len(desc)} characters; the maximum is 1,024"))
        if "<" in desc or ">" in desc:
            findings.append(Finding("WARN", "description contains `<` or `>`, which some clients reject"))

    comp = data.get("compatibility")
    if isinstance(comp, str) and len(comp) > 500:
        findings.append(Finding("WARN", f"compatibility is {len(comp)} characters; the specification's maximum is 500"))

    # Size
    n_lines = len(content.splitlines())
    if n_lines > MAX_SKILL_LINES:
        findings.append(Finding("WARN", f"SKILL.md is {n_lines} lines (recommended under {MAX_SKILL_LINES}); move detailed material to references/ or gotchas.md"))
    est = len(body) // CHARS_PER_TOKEN
    if est > MAX_BODY_TOKENS:
        findings.append(Finding("WARN", f"SKILL.md body is about {est:,} tokens (recommended under {MAX_BODY_TOKENS:,}, estimated at {CHARS_PER_TOKEN} characters per token); move detailed material to references/ or gotchas.md"))

    # Shared skills
    shared = is_shared(name)
    if name.endswith("-idb"):
        meta = data.get("metadata")
        if not (isinstance(meta, dict) and meta.get("version")):
            findings.append(Finding("WARN", "shared `-idb` skill has no `metadata.version`; add one so a participant can tell which copy runs"))
    findings += _scan_paths(skill_path, name, shared)

    order = {"ERROR": 0, "WARN": 1, "NOTE": 2}
    return sorted(findings, key=lambda f: order[f.level])


def validate_skill(skill_path):
    """Return (ok, message): ok is False when there is at least one error."""
    findings = collect_findings(skill_path)
    errors = [f for f in findings if f.level == "ERROR"]
    if errors:
        extra = f" (and {len(errors) - 1} more error(s))" if len(errors) > 1 else ""
        return False, errors[0].message + extra
    warns = sum(f.level == "WARN" for f in findings)
    return True, "Skill is valid!" + (f" ({warns} warning(s))" if warns else "")


def main(argv):
    if not argv:
        print("Usage: python3 quick_validate.py <skill_directory> [<skill_directory> ...]")
        return 1
    any_error = False
    for arg in argv:
        path = Path(arg)
        findings = collect_findings(path)
        counts = {lvl: sum(f.level == lvl for f in findings) for lvl in ("ERROR", "WARN", "NOTE")}
        any_error |= counts["ERROR"] > 0
        label = path.resolve().name
        if not findings:
            print(f"{label}: Skill is valid!")
            continue
        print(f"{label}: {counts['ERROR']} error(s), {counts['WARN']} warning(s), {counts['NOTE']} note(s)")
        for f in findings:
            print(f"  {f.level:<5} {f.message}")
    return 1 if any_error else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
