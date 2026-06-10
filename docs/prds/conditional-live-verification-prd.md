# PRD: Conditional Live Verification and Foundation Smoke

## Overview

Six of the twelve retros in the systemic analysis share one root cause: **critical code was merged without ever being exercised in the running system.** The CSS truncation bug was "fixed" four times without seeing the render. The auth system passed plan → implement → QA → review → security with zero login attempts. The task-detail modal had 23 passing unit tests with every child mocked while the real app threw on open.

This PRD creates **`aet-verify`**, a conditional skill that captures observed evidence of behavior — but **only for critical work**. Trivial and normal tasks continue with fast automated checks. This prevents the six high-severity incidents without imposing corporate-level ceremony on every change.

It also creates the **foundation smoke contract**: a handful of executable checks that verify the substrate (auth, boot, CRUD, dev services) is solid before building on it.

## Goals

1. **Create `aet-verify` skill** — a conditional verification harness with three modes: foundation (smoke), feature (observed evidence), and reproduction (bug report step 1).
2. **Feature mode captures observed evidence** — for critical work only, exercise the changed flow in the running system and record output/HTTP response/screenshot into the QA report.
3. **Foundation mode runs smoke checks** — scaffolded by `aet-setup`, stored as `make smoke` or `.agents/smoke/`. Run once per session for everyone; before/after for critical work.
4. **`aet-ship` gates on evidence for critical work** — refuses to merge critical changes without `aet-verify` evidence attached.
5. **Mock-boundary policy** — `aet-tdd` and `aet-review` flag tests that mock first-party modules (as opposed to system boundaries like network/external services).
6. **Gate calibration** — `aet-setup` plants a trivial error, confirms each validation command fails, reverts, and records authoritative commands. A gate that cannot fail is decoration.

## Non-Goals

- Making `aet-verify` universal. Normal and trivial tasks skip it entirely.
- Replacing unit tests. Live verification complements, not replaces, fast automated checks.
- Browser automation as a hard dependency. Feature mode can use curl, CLI output, or screenshots depending on what's available.
- Post-deploy canary infrastructure. Out of scope for this PRD.

## User Stories

- As a developer shipping auth changes, I want proof that login works in the running app before merge, not just that a mocked test passes.
- As a QA reviewer, I want to see a screenshot or HTTP response in the QA report showing the feature actually rendered.
- As a toolkit maintainer, I want to know that `tsc --noEmit` actually checks the files I think it checks — confirmed once per project.
- As a test author, I want review to catch when I'm mocking a first-party module instead of executing it for real.

## Acceptance Criteria

- [ ] `aet-verify/SKILL.md` exists with valid YAML frontmatter and three modes documented.
- [ ] `aet-verify/examples/` and `aet-verify/references/` exist.
- [ ] Feature mode: given a critical task, the skill produces a QA report appendix with at least one observed evidence artifact.
- [ ] Foundation mode: `make smoke` or equivalent exists, checks login + boot + primary CRUD + dev services.
- [ ] `aet-ship` checks for `aet-verify` evidence when the task is classified as critical.
- [ ] `aet-tdd/SKILL.md` and `aet-review/SKILL.md` include the mock-boundary policy.
- [ ] `aet-setup` includes the gate-calibration procedure (plant error, confirm failure, revert, record).
- [ ] `aet-verify` is under 400 lines; deep detail lives in `references/`.

## Open Questions

1. Should feature mode require Playwright when available, or stay tool-agnostic (curl, CLI, screenshots all valid)?
2. Should the smoke check definitions live in the project repo (`.agents/smoke/`) or in the skill instructions?
3. How does `aet-verify` integrate with the QA report format — append to existing report or produce a separate evidence file?

---

*Stage: scope-validated*
*Validated: 2026-06-10*
*Notes: No conflicts. Assumes work-class routing (PRD 1) is in place to trigger conditionally. Foundation smoke scaffold should align with aet-setup conventions.*
