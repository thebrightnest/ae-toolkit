---
name: aet-bug-report
description: |
  Structured bug investigation and fixing for agentic engineering. Guides reproduction,
  root-cause analysis, targeted fixes, and validation without the overhead of full PRD
  planning. Use when you have a reproducible bug, error, crash, or unexpected behavior
  to diagnose and fix. Triggers on "fix this bug," "investigate this error," "something
  is broken," "debug this," "find the root cause," or "trace this crash."
---

# aet-bug-report

Lightweight, structured bug investigation. When `aet-plan` is too heavy and raw
`aet-implement` is too vague, use this skill to reproduce, diagnose, fix, and validate
bugs — without writing PRDs, user stories, or UI mockups.

## When to Use

- A bug, error, crash, or unexpected behavior needs investigation
- You want structured debugging without feature-planning overhead
- Triggers: "fix this bug," "investigate this error," "something is broken,"
  "debug this," "find the root cause," "trace this crash"

## Hard Gate: Bug or Feature?

Before proceeding, confirm this is a **bug** (unexpected behavior in existing code),
not a **feature request** or **redesign**.

**Question:** Is this a new capability or redesign?

- **Yes** → This is a feature. Stop and redirect to `aet-plan`:
  _"This appears to be a new capability or redesign, not a reproducible bug.
  Use `aet-plan` to define and plan the new work."_

**Question:** Can you demonstrate the unexpected behavior?

- **Yes** → Continue with this skill
- **No** → Stop. A non-reproducible bug cannot be validated as fixed.
  Redirect to `aet-plan` if the issue requires design work.

## Planning Lockout

This skill is **bug-investigation-only**. No speculative architecture or feature design.

- Do not create PRDs, user stories, or UI mockups
- Do not propose "while we're here, let's refactor" — stay on the bug
- If investigation reveals the issue is structural (requires redesign), stop and
  redirect to `aet-plan`

## Workflow

### Step 1: Reproduce

Establish reliable reproduction before attempting any fix.

1. Collect the error message, stack trace, or symptom description
2. Identify the minimal conditions that trigger the bug
3. Reproduce the bug at least once
4. **Gate:** If you cannot reproduce it, stop. A non-reproducible bug cannot be
   validated as fixed.

**Output:** Reproduction steps documented in the bug report.

### Step 2: Root-Cause

Diagnose the underlying cause, not the symptom.

1. Use the smallest reproduction to isolate the failure point
2. Apply diagnostic techniques (see `references/diagnostic-techniques.md`)
3. Form a hypothesis and verify it with evidence (logs, code inspection, bisect)
4. **Gate:** Do not proceed to Fix until you have evidence-based confidence in the
   root cause.

**Output:** Root cause documented in the bug report.

### Step 2.5: Fix Approval Gate (Mandatory)

Before writing any code, present your diagnosis and proposed fix to the user.

**Required presentation:**

- **Root cause:** One-sentence evidence-based diagnosis
- **Proposed fix:** What will change and why
- **Files to modify:** List of files that will be edited
- **Risk level:** Low / medium / high (agent's assessment)

**Wait for explicit user approval.** Acceptable approvals: "yes", "go ahead",
"apply it", "proceed", or similar. If the user requests changes to the approach,
revise the proposal and present again.

**Do not write, modify, or delete any source code until explicit approval is given.**

### Step 2.6: Diff Budget Gate

Before applying the fix, evaluate the estimated scope against the diff budget.

**Budget:** ≤ 3 files and ≤ 100 lines changed.

If the fix exceeds either limit:

1. Require explicit justification before writing code:
   - Why a smaller change is insufficient
   - Why the scope expansion is necessary to fix the root cause
2. If the justification is weak or the fix requires redesign, stop and redirect to `aet-plan`:
   _"This fix exceeds the bug diff budget and requires redesign. Use `aet-plan` to scope the new work."_

### Step 3: Fix

Apply the smallest change that resolves the root cause.

**Only proceed here after explicit user approval from Step 2.5.**

1. Identify all locations that need change
2. Write the fix
3. Run the reproduction steps to confirm the bug is resolved

**Output:** Fix summary documented in the bug report.

### Step 4: Validate

Confirm the fix is correct and safe.

1. Run the reproduction steps — the bug should no longer occur
2. Run existing tests — no regressions should appear
3. If tests are missing for this code path, note it in the bug report. Do not
   mandate test creation; `aet-tdd` is a separate concern.
4. If the bug touches auth, data, or trust boundaries, invoke `aet-cso`
5. Persist lessons learned with `aet learnings append --problem <...> --layer <...> --fix <...> --prevents <...> [--trigger <...>]` for `aet-evolve`

**Output:** Validation results and lessons learned in the bug report.

## Output: Bug Report

After completing the workflow, produce a concise bug report. Use
`references/bug-report-template.md` as the structure guide.

Save to `docs/bugs/{timestamp}-{slug}.md` or return inline if `docs/bugs/` does not exist.

## Integration with Other Skills

| Skill        | When to invoke                                | How                                 |
| ------------ | --------------------------------------------- | ----------------------------------- |
| `aet-tdd`    | User wants test-first bug fix                 | Call before Step 3 (Fix)            |
| `aet-cso`    | Bug touches auth, data, or boundaries         | Call during Step 4 (Validate)       |
| `aet-evolve` | Lessons learned surface a pattern             | Run `aet learnings append --problem ... --layer ... --fix ... --prevents ... [--trigger ...]` |
| `aet-plan`   | Issue is not reproducible / requires redesign | Redirect from Hard Gate             |

## Rules

- **Never write a PRD for a bug.** This skill replaces planning for bugs only.
- **Never reproduce once and assume.** Reproduce reliably before diagnosing.
- **Never fix symptoms.** If the root cause is unclear, keep investigating.
- **Never skip validation.** A fix without validation is a guess.
- **Never add scope.** Stay on the bug; resist "while we're here" refactors.
- **Keep this skill under 400 lines.** Deep detail lives in `references/`.
