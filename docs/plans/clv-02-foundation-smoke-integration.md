---
id: clv-02-foundation-smoke-integration
blocked_by: []
size: M
---

# Plan: Foundation Smoke Checks, Gate Calibration, and Mock-Boundary Policy

## Context

PRD: `docs/prds/conditional-live-verification-prd.md`

## Goal

Implement the foundation smoke contract, gate calibration procedure, and mock-boundary policy across affected skills.

## Tasks

### Task 1: Create smoke check scaffold

- [ ] Add `.agents/smoke/` directory convention to aet-setup
- [ ] Document standard smoke checks: login, boot, primary CRUD, dev services
- [ ] Add `make smoke` target generation to aet-setup scaffold
- [ ] Document session-level execution (once per session, not per task)

### Task 2: Update aet-setup with gate calibration

- [ ] Add calibration procedure: plant trivial error, confirm validation fails, revert, record
- [ ] Document authoritative validation commands in `.agents/validation-commands.json`
- [ ] Run calibration as part of setup completion

### Task 3: Update aet-tdd and aet-review with mock-boundary policy

- [ ] Add lens: "test mocks a first-party module" → review flag
- [ ] Document the boundary rule: mock system boundaries (network, external services); execute first-party code for real
- [ ] Add example of acceptable vs. unacceptable mocking

### Task 4: Update aet-ship to gate on critical-class evidence

- [ ] Add check: if task is critical-class, require aet-verify evidence attachment
- [ ] Document the evidence file path convention

## Validation

- [ ] `make validate` passes
- [ ] A new project scaffolded by aet-setup includes `make smoke`
- [ ] Gate calibration produces `.agents/validation-commands.json`
- [ ] aet-review flags a test that mocks a first-party module

## Rollback

Revert affected skill files from git.

---

_Stage: plan-approved_
_Work class: normal_
_Next step: aet-pipeline-implement_
