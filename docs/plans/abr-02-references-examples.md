# abr-02: Write References and Examples

## Story

As an AE Toolkit user, I want detailed reference material and usage examples so that I understand how to use `aet-bug-report` effectively and what output to expect.

## Acceptance Criteria

- [ ] `references/bug-report-template.md` exists with full output template structure
  - Symptoms
  - Reproduction Steps
  - Root Cause
  - Fix Summary
  - Lessons Learned
- [ ] `references/diagnostic-techniques.md` exists with investigation patterns
  - Binary search / git bisect
  - Logging and tracing
  - Isolation and minimization
  - Hypothesis-driven debugging
- [ ] `examples/README.md` exists with at least 2 usage scenarios
  - Example 1: Simple runtime error (reproducible, localized fix)
  - Example 2: Subtle logic bug (requires bisect, non-obvious root cause)
- [ ] `SKILL.md` links to `references/` and `examples/` where appropriate
- [ ] Skill remains under 400 lines total in `SKILL.md`

## Technical Notes

- Reference docs can be verbose; they are not loaded into context unless needed
- Examples should be realistic and specific to agentic engineering workflows
- Keep examples agent-agnostic (no tool-specific syntax)

## Blocked by

- abr-01-scaffold-core.md

---

_Stage: synced_
_Next step: run `aet-ship`, then `post-ship-verify` to reach `merged`_
