# Bug Report Template

Use this template as the output of every `aet-bug-report` session. Replace the
placeholders with investigation findings.

---

## Bug Report: {short description}

## Metadata

- **Reported:** {ISO-8601 timestamp}
- **Severity:** {critical / high / medium / low}
- **Status:** {open / resolved / wontfix}

## Symptoms

{Describe what went wrong from the user's perspective. Include error messages,
stack traces, or observed misbehavior. Be specific — "the page crashes" is not
enough; "the page returns a 500 when submitting the form with an empty email
field" is.}

## Reproduction Steps

{Minimal, reliable steps to trigger the bug. A good reproduction is:

1. Start from a known clean state
2. List each action precisely
3. End with the observed failure

If the bug is intermittent, note the frequency and any conditions that increase
or decrease the likelihood.}

## Root Cause

{Evidence-based explanation of why the bug occurs. Not a guess — cite logs,
code paths, git history, or data that supports the diagnosis.

Structure:

- What assumption was wrong?
- What code path led to the failure?
- Why did existing tests or checks not catch it?
  }

## Fix Summary

{What changed and why. Keep it focused on the root cause.

- Files modified: {list}
- Key change: {one-sentence summary}
- Side effects: {any behavior changes beyond the bug fix}}

## Regression Test

{Existing test that now passes, or new test added to prevent recurrence. If no
test was added, explain why (e.g., "covered by existing integration test X" or
"test requires external dependency not available in CI").}

## Validation

- [ ] Reproduction steps no longer trigger the bug
- [ ] Existing test suite passes with no new failures
- [ ] No regressions observed in related functionality

## Lessons Learned

{What should the team watch for in the future? This feeds into `aet-evolve`.

- Pattern: {what type of bug was this?}
- Prevention: {what process, test, or guardrail would have caught it earlier?}
- Reference: {link to any updated rules, templates, or ADRs}}
