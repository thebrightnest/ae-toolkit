---
blocked_by:
  - ppa-02-resilient-closure-plan-archival
docs_sync: required
id: ppa-03-adr-conventions-and-skills-sync
pipeline: standard
security_review: skipped
security_review_reason: Pure documentation, templates, and conventions updates.
size: S
work_class: normal
---

## Context

PRD: `docs/prds/partitioned-plan-directory-layout-prd.md`
Relates to: ADR-054, ADR-061, and ADR-069.

To make the partitioned plan layout (`docs/plans/active/` and `docs/plans/archive/`) standard across the toolkit, we must record ADR-069, update `.gitignore` templates and scaffolding, and align the skill instructions (`skills/aet-plan/`, `skills/aet-ship/`, `docs/CONVENTIONS.md`, and `README.md`).

## Intake Triage

- [x] Confirmed this is a documentation and conventions synchronization task.

⚠️ VALIDATE ACK: scope — ADR-069 is authored during task execution.

## Task List

1. Author `docs/adr/069-partitioned-plan-directory-layout.md` and update `docs/adr/README.md` index — S (traces: R-5)
2. Update `.gitignore` and template files in `skills/aet-setup/` to ignore `docs/plans/active/` while allowing `docs/plans/archive/` — S (traces: R-4)
3. Update `skills/aet-plan/SKILL.md` to instruct agents to author plans in `docs/plans/active/<id>.md` — S (traces: R-6)
4. Update `skills/aet-ship/SKILL.md` and `docs/CONVENTIONS.md` to document the closure archival behavior and optional git-tracking posture — S (traces: R-6)
5. Run doc validation and linter checks (`aet docs lint`, `make lint-py`, `scripts/validate-skills.sh`) — S (traces: R-6)

## Verification

- `aet docs lint` and `scripts/validate-skills.sh` pass cleanly.
- `docs/CONVENTIONS.md` and `skills/` accurately describe `docs/plans/active/` and `docs/plans/archive/`.
