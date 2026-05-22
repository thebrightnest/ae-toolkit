# abr-01: Scaffold Skill Structure and Core Workflow

## Story

As an AE Toolkit user, I want to invoke `aet-bug-report` so that the agent follows a structured but lightweight bug investigation process.

## Acceptance Criteria

- [ ] `aet-bug-report/` directory exists at repo root
- [ ] `SKILL.md` exists with valid YAML frontmatter (`name: aet-bug-report`, explicit trigger description)
- [ ] `SKILL.md` defines the 4-step workflow: Reproduce → Root-Cause → Fix → Validate
- [ ] Step 1 includes the hard gate: cannot reproduce → redirect to `aet-plan`
- [ ] Step 3 includes human confirmation for high-risk changes
- [ ] `SKILL.md` stays under 400 lines
- [ ] `examples/` and `references/` directories exist (can be empty for this ticket)
- [ ] `make validate` passes skill-structure checks

## Technical Notes

- Follow `docs/CONVENTIONS.md` for skill structure and naming
- Use imperative voice in instructions
- Keep the description explicit about trigger phrases: "fix this bug," "investigate this error," "something is broken," "debug this"
- Do not duplicate deep detail here; move verbose content to references in abr-02

## Blocked by

None — can start immediately.

---

_Stage: merged_
_Next step: none — pipeline complete_
