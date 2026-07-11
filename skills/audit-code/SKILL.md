---
name: audit-code
description: Use when the user asks to audit, review, or check Stata dofiles for macro definitions, undefined paths, internal consistency, or unused variables. Triggers on "audit code", "audit dofiles", "check my Stata code", "audit my Stata project", or "/audit-code".
argument-hint: "[path-to-dofiles-directory]"
---

# audit-code

## Working principles

**Work modularly — one module at a time.** Stop after each module and wait for confirmation. Reason: code audits compound noise fast. If module 1 surfaces 30 issues and the user catches a false positive, you want to recalibrate before module 2 generates 30 more in the same wrong direction.

**Flag unknowns explicitly instead of guessing.** Stata code is full of context-dependent behavior (locals vs globals, scoping inside `program`, version-specific defaults). A guess that sounds confident is worse than an unknown that prompts the user to clarify.

**Report only problems.** Don't list what you checked or what was already fine. The user already trusts that you ran the audit; padding the report with "Module 1: no issues found in `01_clean.do`" buries the actual findings.


## Workflow

Three modules, run strictly in order, each ending at a STOP checkpoint: Module 1 (paths and macros), Module 2 (per-dofile internal consistency), Module 3 (unused variables). Full instructions in each module's section below.


---

## Module 1: Check Paths and Macros

Carefully review the dofiles and make sure that all the macros that are called in later dofiles are defined at some point. Similarly, make sure that all the paths are correctly specified.

**Before proceeding, confirm:**

- [ ] All the macros are well defined
- [ ] No macros are never used

**Present for review:**

1. All the instances where macros are not well defined
2. List of macros that are defined but never used and the dofile where the macro is defined

**STOP and wait for approval to proceed to Module 2**


---

## Module 2: Carefully Audit Each Dofile Separately

### Structure of the audit

For each dofile, produce an audit where you separate **critical** problems from **suggestions**.

**OUTPUT ORDER REQUIREMENT:**
- All Critical issues must be listed in order of line number (lowest to highest)
- All Suggestions must be listed in order of line number (lowest to highest)
- Never jump backwards in the code within a category

For each problem identified (whether critical or suggestion), report:

1. The line where the problem occurs
2. The actual code causing the issue
3. A solution to fix it

Make sure to label each problem "Critical 1, Critical 2, ..." or "Suggestion 1, Suggestion 2, ... Suggestion n" so that I can easily refer to them when interacting with you.


### Things for you to remember when considering if a problem is critical in Stata

Remember that Stata does NOT have a problem of "Reference to tempfile outside its scope". As long as the dofile runs, tempfiles are stored in the temporary memory by Stata and these files can be called outside the loop they are defined in.

**gtools and ftools commands are valid:** Since gtools and ftools packages are installed, the following commands are VALID and should NOT be flagged as errors:
- **gtools**: `gegen`, `gcollapse`, `gduplicates`, `greshape`, `gisid`, `glevelsof`, `gquantiles`, `gstats`, `gtop`, `gunique`, `hashsort`, `gsort`
- **ftools**: `fmerge` (faster merge), `reghdfe`, `ppmlhdfe`, `ivreghdfe`

Do NOT suggest replacing these commands with base Stata equivalents.


### Things that should always be included as suggestions

- Assume I have the **gtools** and **ftools** packages installed. Flag any instance where a base Stata command is used but a gtools/ftools equivalent exists and would be faster (e.g., egen should be gegen, collapse should be gcollapse, duplicates should be gduplicates, etc.)
- Try as much as possible to suggest code that is compact and clean


### Things that should NEVER be included as suggestions

- Missing `compress` before `save` — this is a stylistic preference, not a problem
- Missing `quietly` or `qui` — verbosity is not an error
- Adding comments or documentation — do not suggest documentation improvements
- **Replacing `merge` with `fmerge`** — `fmerge` is far less versatile than `merge` and can prevent code from running in many cases. **ONLY** suggest replacing `merge` with `fmerge` if:
  - The exact same merge has already been performed with `fmerge` earlier in the code, AND
  - A later instance uses `merge` for that same merge (suggesting inconsistency)
  - Otherwise, assume `merge` is used for a good reason and do NOT suggest replacing it


### How to write the audit

- **Think first, write second.** Before writing ANY suggestion, verify it is an actual problem requiring a change.
- **Never withdraw or revise suggestions mid-response.** If you write a suggestion and then realize it's not valid, you have already failed. Do not write "I withdraw this" or "actually this is fine" — those phrases should never appear.
- **Each suggestion you write is final.** If you are unsure whether something is a problem, do not include it.
- **Every numbered item MUST contain a code change.** If you cannot write "Solution: [new code]" with actual different code, do not create the item.


### Before submitting each dofile audit

Re-read each item and delete any whose Solution code is identical to the Original, or that merely confirms existing code is correct ("no change needed", "this is fine"). Never describe the review process ("I checked X and it was fine"). If a dofile has no issues, state only "No critical issues" and "No suggestions", nothing else.


### MANDATORY STOP AFTER EACH DOFILE

After completing the audit of ONE dofile:

1. Present your findings (critical issues + suggestions)
2. **STOP COMPLETELY**
3. **WAIT for my response** — I may have questions, comments, or requests for clarification about your audit
4. **DO NOT proceed to the next dofile** until I explicitly say **"next"**

**Any other response from me (including "ok", "yes", "thanks", "I understand", corrections, or questions) is NOT permission to proceed.** Stay on the current dofile and respond to my input.

When you stop, always write:

```
STOPPED - AWAITING YOUR INPUT

To move to next dofile, say "next"
```


### CRITICAL: Maintaining Consistency Based on User Feedback

**If you provide ANY corrections, clarifications, or modifications to my audit approach at any stop point, I MUST apply those same corrections/modifications consistently to ALL remaining dofiles in the audit.**

This includes but is not limited to:

- **Classification changes**: If you say "this should be a suggestion, not critical," I must apply that classification to identical issues in all future dofiles
- **Scope clarifications**: If you say "don't flag X as an issue," I must never flag X in any remaining dofiles
- **Pattern approvals**: If you clarify that a certain coding pattern is intentionally correct, I must not flag that same pattern anywhere else
- **Threshold adjustments**: If you say "only flag variables unused for 100+ lines," I must apply that threshold throughout
- **Variable/macro exceptions**: If you say "variable X is intentionally unused," I must not flag similar intentionally unused variables later
- **Style preferences**: If you indicate a preference for a certain coding style, I must use that standard for all remaining audits

**Before auditing each new dofile, I must review all feedback you have provided on previous dofiles and ensure I apply it consistently.**

**I must NEVER flag the same issue type again after you have indicated it should not be flagged.**


---

## Module 3: Identify Unused Variables

Go again through all the code and identify all the variables that are created but never used later.

**Present for review:**

1. List of variables created but never used
2. The dofile and line where each unused variable is created

**STOP and wait for final approval**
