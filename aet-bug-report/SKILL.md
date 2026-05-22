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
not a **feature request** (missing capability).

**Test:** Can you demonstrate the unexpected behavior?

- **Yes** → Continue with this skill
- **No** → Stop. Redirect to `aet-plan`:
  _"This appears to be a feature request or enhancement, not a reproducible bug.
  Use aet-plan to define and plan the new capability."_

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

### Step 3: Fix

Apply the smallest change that resolves the root cause.

1. Identify all locations that need change
2. Write the fix
3. **Hard gate for high-risk changes:** Before applying fixes that delete data,
   modify auth logic, change database schemas, or alter API contracts, pause and
   ask for explicit human confirmation:

   ```
   ⚠️ High-risk change detected: {description}
   Approve to apply, or reject and suggest a safer approach.
   ```

4. Run the reproduction steps to confirm the bug is resolved

**Output:** Fix summary documented in the bug report.

### Step 4: Validate

Confirm the fix is correct and safe.

1. Run the reproduction steps — the bug should no longer occur
2. Run existing tests — no regressions should appear
3. If tests are missing for this code path, note it in the bug report. Do not
   mandate test creation; `aet-tdd` is a separate concern.
4. If the bug touches auth, data, or trust boundaries, invoke `aet-cso`
5. Append lessons learned to `.agents/learnings.jsonl` for `aet-evolve`

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
| `aet-evolve` | Lessons learned surface a pattern             | Append to `.agents/learnings.jsonl` |
| `aet-plan`   | Issue is not reproducible / requires redesign | Redirect from Hard Gate             |

## Rules

- **Never write a PRD for a bug.** This skill replaces planning for bugs only.
- **Never reproduce once and assume.** Reproduce reliably before diagnosing.
- **Never fix symptoms.** If the root cause is unclear, keep investigating.
- **Never skip validation.** A fix without validation is a guess.
- **Never add scope.** Stay on the bug; resist "while we're here" refactors.
- **Keep this skill under 400 lines.** Deep detail lives in `references/`.
