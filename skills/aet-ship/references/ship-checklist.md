# Ship Checklist

## Pre-Flight

- [ ] Branch is up to date with main (or rebased)
- [ ] No uncommitted changes (or stashed)
- [ ] Plan.md exists and all tasks are checked

## Validation Gates

- [ ] **Tests** — unit + integration pass
- [ ] **Type check** — passes
- [ ] **Lint** — passes (or zero false positives)
- [ ] **Coverage** — did not drop below threshold
- [ ] **Review** — aet-review passed (no unaddressed human flags)
- [ ] **Security** — aet-cso passed (or no auth/data changes)

## Commit Quality

- [ ] Each commit is bisectable (one logical change)
- [ ] Commit messages follow project convention
- [ ] No "fix typo" or "address review" commits mixed with feature work

## Artifacts

- [ ] CHANGELOG entry generated
- [ ] VERSION bumped (patch auto, minor/major human decision)
- [ ] PR description links plan.md and PRD
- [ ] PR has appropriate labels

## Post-Ship (Not Part of This Skill)

- [ ] aet-canary runs post-deploy (future skill)
