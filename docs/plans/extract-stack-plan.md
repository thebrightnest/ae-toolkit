# Plan: aet-extract-stack

## Context

- PRD: [docs/prds/extract-stack-prd.md](../prds/extract-stack-prd.md)
- Brief: [docs/product-briefs/extract-stack-brief.md](../product-briefs/extract-stack-brief.md)
- This skill is the inverse of `aet-setup`: extract proven infrastructure from an existing project instead of bootstrapping from scratch.

## Tasks

1. **Write SKILL.md** — Define the skill's YAML frontmatter, discovery procedure, extraction steps, placeholder rules, and validation protocol. (M)
2. **Write examples/README.md** — Create usage examples covering: full-stack web app, minimal API extract, monorepo, and nothing-found scenarios. (S)
3. **Write references/README.md** — Document placeholder naming conventions, secret detection patterns, and category-specific stripping rules. (S)
4. **Update README.md** — Add `aet-extract-stack` to the skill table with description and link. (XS)
5. **Validate and package** — Run `make validate` and `make package` to produce `aet-extract-stack.skill`. (S)

## Dependencies

- Task 1 blocks Tasks 2 and 3 (examples and references depend on the skill instructions).
- Task 4 depends on Task 1 (need the skill directory to exist before linking).
- Task 5 depends on Tasks 1–4.

## Validation Steps

- [ ] `make validate` passes (lint + format-check + skill-structure checks for the new skill)
- [ ] `make package` produces `aet-extract-stack.skill`
- [ ] Skill directory structure matches convention: `SKILL.md`, `examples/`, `references/`
- [ ] SKILL.md has valid YAML frontmatter with `name` and `description`
- [ ] `name` matches directory name
- [ ] All relative internal markdown links in SKILL.md resolve
- [ ] SKILL.md is under 400 lines

## Rollback Plan

Delete `aet-extract-stack/` directory, remove the row from `README.md`, and delete `aet-extract-stack.skill`. Run `make validate` to confirm clean state.

---

_Stage: synced_
_Next step: run `aet-ship`_
