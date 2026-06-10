# Plan: Foundation Smoke Checks, Gate Calibration, and Mock-Boundary Policy

## Context

PRD: `docs/prds/conditional-live-verification-prd.md`

## Goal

Implement the foundation smoke contract, gate calibration procedure, and mock-boundary policy across affected skills.

## Tasks

### Task 1: Create smoke check scaffold

- [x] Add `.agents/smoke/` directory convention to aet-setup
- [x] Document standard smoke checks: login, boot, primary CRUD, dev services
- [x] Add `make smoke` target generation to aet-setup scaffold
- [x] Document session-level execution (once per session, not per task)

### Task 2: Update aet-setup with gate calibration

- [x] Add calibration procedure: plant trivial error, confirm validation fails, revert, record
- [x] Document authoritative validation commands in `.agents/validation-commands.json`
- [x] Run calibration as part of setup completion

### Task 3: Update aet-tdd and aet-review with mock-boundary policy

- [x] Add lens: "test mocks a first-party module" → review flag
- [x] Document the boundary rule: mock system boundaries (network, external services); execute first-party code for real
- [x] Add example of acceptable vs. unacceptable mocking

### Task 4: Update aet-ship to gate on critical-class evidence

- [x] Add check: if task is critical-class, require aet-verify evidence attachment [Changed: uses `critical` to match existing plan footer convention, not `critical-class`]
- [x] Document the evidence file path convention

## Validation

- [x] `make validate` passes [Changed: repo-wide fails on pre-existing untracked docs/plans/ + docs/prds/; skill files pass lint/format/structure checks]
- [x] A new project scaffolded by aet-setup includes `make smoke`
- [x] Gate calibration produces `.agents/validation-commands.json`
- [x] aet-review flags a test that mocks a first-party module

## Divergence Summary

_Recorded: 2026-06-10 — Branch: clv-02_

### Changed from plan

- _Task 4 terminology:_ aet-ship checks for `*Work class: critical*` (the value used in existing plan footers and the triage-front-door PRD), not `critical-class` (the wording in this plan's task description). This keeps aet-ship consistent with the work-class routing convention already in use.
- _aet-setup AGENTS.md section:_ Condensed the existing AGENTS.md subsection from a multi-line checklist into a single paragraph so the new Smoke Checks and Validation Calibration sections fit under the 400-line SKILL.md limit. No semantic content was removed.
- _`make validate` scope:_ Repo-wide `make validate` continues to fail due to pre-existing untracked plan/PRD files from parallel work. The modified skill files individually pass markdownlint, prettier, and skill-structure validation.

### Deferred

- _aet-verify skill implementation:_ The aet-ship gate documents the evidence convention (`.agents/verify/{ticket}-evidence.md`) but the actual `aet-verify` skill directory does not exist on this branch. That work is tracked in `clv-01-aet-verify-skill.md` (stage `synced` on branch `clv-01`).

## Rollback

Revert affected skill files from git.

---

_Stage: synced_
_Work class: normal_
_Next step: run `aet-ship`, then `post-ship-verify` to reach `merged`_
