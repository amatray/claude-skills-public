## Description optimization

The `description` is the primary triggering mechanism. After the skill is otherwise done, offer to optimize it.

### Step 1: Generate trigger eval queries

20 realistic queries, mix of should-trigger and should-not-trigger. Realistic = what a real user would actually type, with backstory, file paths, column names, typos, casual phrasing.

Bad: `"Format this data"`, `"Create a chart"`.

Good: `"ok so my boss just sent me this xlsx file (its in my downloads, called something like 'Q4 sales final FINAL v2.xlsx') and she wants me to add a column for profit margin as a percentage. Revenue is column C, costs column D i think"`

**Should-trigger** (8–10): different phrasings of the same intent, formal and casual, cases where the user doesn't explicitly name the file type but clearly needs the skill, uncommon use cases, competitive cases where this skill should win over an adjacent one.

**Should-not-trigger** (8–10): the valuable ones are *near-misses* — queries that share keywords but actually need something different. Adjacent domains, ambiguous phrasing that a naive keyword match would catch. Avoid obvious negatives ("write a fibonacci function" as a negative for a PDF skill tests nothing).

### Step 2: Review with user

Use the HTML template:

1. Read `assets/eval_review.html`.
2. Replace placeholders: `__EVAL_DATA_PLACEHOLDER__` (JS array, no surrounding quotes), `__SKILL_NAME_PLACEHOLDER__`, `__SKILL_DESCRIPTION_PLACEHOLDER__`.
3. Write to `/tmp/eval_review_<skill-name>.html` and `open` it.
4. The user edits queries, toggles should-trigger, exports.
5. Downloads land in `~/Downloads/eval_set.json` (or `eval_set (1).json` if multiple).

Bad eval queries → bad descriptions. This step matters.

### Step 3: Run the optimization loop

```bash
python -m scripts.run_loop \
  --eval-set <path-to-trigger-eval.json> \
  --skill-path <path-to-skill> \
  --model <model-id-powering-this-session> \
  --max-iterations 5 \
  --verbose
```

Use the model ID from your system prompt so the triggering test matches what the user experiences.

The loop splits 60% train / 40% held-out test, evaluates the current description (3 runs per query for stable trigger rates), proposes improvements, re-evaluates, iterates up to 5 times. Selects `best_description` by test score (not train) to avoid overfitting. Opens an HTML report when done.

Periodically tail the output to report progress to the user.

### How triggering works

Claude consults skills only for tasks it can't easily handle alone. Simple, one-step queries ("read this PDF") may not trigger a skill regardless of how well the description matches, because Claude can handle them directly. Multi-step or specialized queries trigger reliably when the description matches. Design eval queries that are substantive enough to actually need a skill.

### Step 4: Apply

Take `best_description` from the JSON output, update the frontmatter, show before/after and scores to the user.

