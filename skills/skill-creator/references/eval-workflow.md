### Test cases

**Write test cases before drafting the skill, not after.** 2–3 realistic prompts a real user would actually type, ideally pressure scenarios (time pressure, conflicting incentives, ambiguity) for discipline skills. Confirm with the user. Save to `evals/evals.json`:

```json
{
  "skill_name": "example-skill",
  "evals": [
    {"id": 1, "prompt": "User's task prompt", "expected_output": "Description of expected result", "files": []}
  ]
}
```

Assertions come later, during the runs. See `references/schemas.md` for the full schema.

---

## Baseline (RED phase)

Before drafting the skill, run each scenario *without* any skill. One baseline subagent per scenario, all spawned in the same turn:

```
Execute this task:
- Task: <eval prompt>
- Input files: <eval files, or "none">
- Save outputs to: <workspace>/baseline/eval-<ID>/outputs/
- Outputs to save: <what the user cares about>
```

Outputs go in `<skill-name>-workspace/baseline/eval-<ID>/`. Read each transcript carefully — not just the final output. Capture:

- What did the agent do that the skill should prevent or change?
- What rationalizations did it use, **verbatim**? ("I'll add the test after", "this case is different because…", "manual review is enough"). These become rows in the rationalization table for discipline skills.
- Where did it cut corners under pressure?

If the baseline already does what you want, the skill is redundant — stop and tell the user. Otherwise, the failures you observed become the targets the skill body must address. Don't write defenses against problems you didn't see.

After drafting, the loop below handles the GREEN (verify) and REFACTOR (close loopholes) phases.

**Deeper reading**: `references/testing-skills-with-subagents.md` covers pressure-scenario design (time + sunk cost + authority + exhaustion combinations), the seven pressure types, meta-testing (asking the agent why it failed even with the skill loaded), and a worked example of iterating until bulletproof. Load it for discipline skills where the agent has real incentive to rationalize.

## Running and evaluating test cases

This section is one continuous sequence. Don't stop partway.

Workspace lives at `<skill-name>-workspace/` as a sibling of the skill folder. Inside: `iteration-1/`, `iteration-2/`, … and within each, `eval-0/`, `eval-1/`, … Create directories as you go.

### Step 1: Spawn all runs in one turn

For each test case, spawn two subagents in the same turn: one with the skill, one baseline.

**With-skill:**

```
Execute this task:
- Skill path: <path-to-skill>
- Task: <eval prompt>
- Input files: <eval files, or "none">
- Save outputs to: <workspace>/iteration-<N>/eval-<ID>/with_skill/outputs/
- Outputs to save: <what the user cares about>
```

**Baseline:**
- New skill → no skill at all. Save to `without_skill/outputs/`.
- Improving existing skill → snapshot the old version first (`cp -r <skill-path> <workspace>/skill-snapshot/`), point the baseline at the snapshot, save to `old_skill/outputs/`.

Write `eval_metadata.json` per eval (assertions empty for now). Give each eval a descriptive name (not just `eval-0`):

```json
{
  "eval_id": 0,
  "eval_name": "descriptive-name-here",
  "prompt": "The user's task prompt",
  "assertions": []
}
```

### Step 2: Draft assertions while runs are in progress

Good assertions are objectively verifiable, with descriptive names that read clearly in the viewer. Subjective skills (writing style, design) need qualitative review, not assertions — don't force the wrong tool.

Update `eval_metadata.json` and `evals/evals.json` with assertions once drafted. Explain to the user what the viewer will show.

### Step 3: Capture timing as runs complete

Each subagent notification contains `total_tokens` and `duration_ms`. Save to `timing.json` in the run directory immediately — this data isn't persisted elsewhere:

```json
{"total_tokens": 84852, "duration_ms": 23332, "total_duration_seconds": 23.3}
```

### Step 4: Grade, aggregate, launch viewer

1. **Grade** — spawn a grader subagent reading `agents/grader.md`, or grade inline. Save to `grading.json` per run. Use fields `text`, `passed`, `evidence` exactly (the viewer depends on these names). For programmatic checks, write a script — faster and reusable.

2. **Aggregate**:

   ```bash
   python -m scripts.aggregate_benchmark <workspace>/iteration-N --skill-name <name>
   ```

   Produces `benchmark.json` and `benchmark.md`. Put each with_skill version before its baseline. See `references/schemas.md` for the schema.

3. **Analyst pass** — read `agents/analyzer.md`. Look for assertions that always pass (non-discriminating), high-variance evals (flaky), time/token tradeoffs.

4. **Launch the viewer**:

   ```bash
   nohup python <skill-creator-path>/eval-viewer/generate_review.py \
     <workspace>/iteration-N \
     --skill-name "my-skill" \
     --benchmark <workspace>/iteration-N/benchmark.json \
     > /dev/null 2>&1 &
   VIEWER_PID=$!
   ```

   Iteration 2+: add `--previous-workspace <workspace>/iteration-<N-1>`.

   Headless environments: use `--static <output_path>` to write a standalone HTML file. The "Submit All Reviews" button downloads `feedback.json`; copy it into the workspace for the next iteration.

   Use `generate_review.py`. Don't hand-roll HTML.

5. **Tell the user**: "Two tabs — Outputs lets you click through and leave feedback, Benchmark shows the quantitative comparison. Come back when you're done."

### What the user sees

**Outputs** tab, one test case at a time: prompt, output files (rendered inline where possible), previous output (iteration 2+, collapsed), formal grades (collapsed), feedback textbox (auto-saves), previous feedback.

**Benchmark** tab: pass rates, timing, tokens per configuration, per-eval breakdowns, analyst observations.

Arrow keys or prev/next to navigate. "Submit All Reviews" writes `feedback.json`.

### Step 5: Read feedback

```json
{
  "reviews": [
    {"run_id": "eval-0-with_skill", "feedback": "missing axis labels", "timestamp": "..."},
    {"run_id": "eval-1-with_skill", "feedback": "", "timestamp": "..."}
  ],
  "status": "complete"
}
```

Empty feedback = user thought it was fine. Focus improvements where they had specific complaints.

Kill the viewer when done: `kill $VIEWER_PID 2>/dev/null`.

---

## Improving the skill

1. **Generalize from feedback.** The skill will be invoked across many prompts. The user is iterating on a few examples because it's fast for them, but overfitting to those examples is useless. If a stubborn issue persists, try different metaphors or working patterns rather than piling on rigid constraints.

2. **Keep the prompt lean.** Read the transcripts, not just outputs. If the skill is making the model burn time on unproductive work, cut what's causing that.

3. **Explain the why.** When you reach for `ALWAYS` / `NEVER`, that's a yellow flag. Reframe with reasoning — the model handles "do X because Y" far better than rote rules.

4. **Bundle repeated work.** If the test transcripts show subagents independently writing the same helper (`create_docx.py`, `build_chart.py`), put it in `scripts/` and reference it from the skill.

### Iteration loop

1. Apply improvements.
2. Rerun all test cases into `iteration-<N+1>/`, with baselines.
3. Launch the viewer with `--previous-workspace` pointing at the previous iteration.
4. Read new feedback.
5. Repeat.

Stop when: the user says they're happy, feedback is all empty, or progress stalls.

