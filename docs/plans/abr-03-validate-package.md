# abr-03: Validate and Package

## Story

As an AE Toolkit maintainer, I want `aet-bug-report` to pass all quality gates and produce a valid `.skill` package so that it can be installed and distributed.

## Acceptance Criteria

- [ ] `make lint` passes with no markdown errors
- [ ] `make format-check` passes with no prettier issues
- [ ] `make validate` passes fully (skill-structure validator)
- [ ] `make package` produces `aet-bug-report.skill` at repo root
- [ ] `aet-bug-report.skill` is a valid zip archive containing the full skill directory
- [ ] Install with `make install-skills` works correctly

## Technical Notes

- Run `make format` before `make format-check` if needed
- The skill-structure validator checks: `examples/` and `references/` exist, YAML frontmatter is valid, `name` matches directory, `SKILL.md` is under 400 lines, all internal links resolve
- No code changes to other skills should be required

## Blocked by

- abr-02-references-examples.md

---

_Stage: merged_
_Next step: none — pipeline complete_
