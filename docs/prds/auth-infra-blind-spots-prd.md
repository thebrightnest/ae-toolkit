# PRD: Test Coverage Completeness & API Integration Gaps

## Executive Summary

Three retros (2026-06-07) revealed that the aet-\* pipeline allowed 9+ distinct bugs to reach manual testing. The domain-specific bugs (double-hashed passwords, missing sessions table, wrong storage path, Sanctum misconfiguration) are symptoms of one root cause: **entire modules had zero test coverage**. If the auth flow, upload controller, and queue job had each had a single integration test, every one of those bugs would have failed a test before reaching manual QA.

The fix is not more domain-specific checklists. It is closing the coverage completeness gap across the four skills that together own test planning, test writing, validation, and review.

A secondary gap: for vertical-slice plans that introduce both a backend endpoint and frontend code that consumes it, no skill mandates a test at the API boundary. Mismatched endpoint URLs, wrong payload keys, and unhandled response shapes all fall through this gap.

## Mission

Make zero-coverage files and untested API contracts impossible to ship through the aet-\* pipeline by enforcing coverage completeness at every stage: plan → TDD → QA → review.

## Target Users

AET users building features across any full-stack project where backend and frontend layers communicate over an API.

## Scope

### In Scope

- `aet-plan`: validation strategy in plan.md must name specific tests per new module — vague "we'll add tests" is an incomplete plan
- `aet-tdd`: coverage completeness gate before `tdd-complete`; API boundary integration test mandate for vertical slices
- `aet-qa`: coverage report as part of QA procedure; zero-coverage on any new/modified file is a tier failure
- `aet-review`: strengthen the `Tests` lens from "are there tests?" to a hard rule — every new file in the diff must have at least one test that references it

### Out of Scope

- Domain-specific lenses (auth, infrastructure, data invariants) — better test coverage makes these unnecessary
- Project-specific fixes in downstream projects
- New skills beyond modifications to the four listed above
- Changes to `aet-implement`, `aet-ship`, `aet-work`, or pipeline skills
- Browser-level E2E tests (those belong in `aet-qa`'s browser tier, already covered)

## Root Cause Analysis

| Bug (retro) | Actual root cause | Would a test have caught it? |
|-------------|-------------------|------------------------------|
| Double-hashed password | `AuthController` + `UserFactory` had zero tests | Yes — any `factory → HTTP login` test |
| Missing `sessions` table | Login flow never tested end-to-end via HTTP | Yes — same test |
| Sanctum stateful domains wrong | No test crossed the React → API boundary | Yes — API boundary integration test |
| Frontend shows generic error for 500 | Frontend error handling never tested | Yes — API boundary test with mocked 500 response |
| Seeded user missing workspace | `UserObserver` had zero tests | Yes — any observer unit test |
| DashboardController null crash | Stats endpoint never tested with minimal seed data | Yes — any endpoint test |
| File upload wrong storage path | `DocumentController` + `ParseDocumentJob` had zero integration coverage | Yes — any upload integration test |
| Queue job swallowed exception | Job failure path never tested | Yes — any job failure test |

Every bug maps to a file with zero test coverage. None required a special lens.

## User Stories

### Story 1 — aet-plan: Concrete Validation Strategy

**As an AET user reviewing a plan**, I want the validation strategy to name specific tests for each new file or module, so that "no tests" is caught at planning time rather than after implementation.

**Acceptance Criteria:**
- `aet-plan` `plan` command requires the validation strategy section to explicitly list: for each new file or module in the plan, at least one named test that will cover it
- A validation strategy that says only "add unit tests" or "write tests" is flagged as incomplete — the plan must not be marked `plan-draft` until tests are named per module
- The validation strategy distinguishes: unit tests (within one layer) vs integration tests (cross-layer) vs API boundary tests (frontend ↔ backend contract)

### Story 2 — aet-tdd: Coverage Completeness Gate + API Boundary Mandate

**As an AET user running aet-tdd on a vertical slice**, I want the skill to enforce that every new file has at least one test before declaring TDD complete, and to mandate an API boundary integration test when the slice introduces both a backend endpoint and frontend code that calls it.

**Acceptance Criteria:**
- Before marking `tdd-complete`, `aet-tdd` runs (or instructs the user to run) coverage and lists any new source file at 0% coverage — zero-coverage files are a blocking failure, not a warning
- `plan-tests` enumerates every new file or class being introduced and produces a test plan that maps each one to at least one test — the list is derived from the plan, not from the agent's imagination
- For vertical slice plans where both a backend endpoint and frontend consumer are introduced: mandate an API boundary integration test (e.g., using MSW or equivalent HTTP interceptor) that verifies: correct endpoint URL, correct request payload shape, correct handling of success response, correct handling of error response (at minimum 4xx and 5xx separately)
- The API boundary test is in addition to — not a replacement for — backend feature tests and frontend component tests

### Story 3 — aet-qa: Coverage as a First-Class QA Gate

**As an AET user running aet-qa**, I want coverage to be part of the QA procedure so that a zero-coverage new file fails QA before reaching review.

**Acceptance Criteria:**
- `aet-qa` `qa` command includes a coverage step after the test suite run: generate a coverage report and check all new or modified source files
- Any new source file with 0% coverage is a QA failure at all tiers (Quick, Standard, Exhaustive) — not a warning, not a note
- Any modified source file where the changed lines have 0% coverage is flagged for human review
- The QA report includes a coverage section listing: files checked, coverage %, files that failed the 0% gate

### Story 4 — aet-review: Tests Lens as a Hard Coverage Check

**As an AET reviewer**, I want the `Tests` lens to check coverage completeness rather than just asking whether tests exist, so that a new file with no test is a hard fail rather than a soft flag.

**Acceptance Criteria:**
- The `Tests` lens in `aet-review` `review` changes from "are there tests for new behavior?" to: for each new file in the diff, verify at least one test file imports or references it — if none exists, that is a **hard fail** (fix-now, not flag-for-human)
- The lens explicitly checks for API boundary tests when the diff introduces both a backend route/controller and frontend API client code that calls it — if both sides exist but no boundary test exists, that is a hard fail
- The lens does not require 100% line coverage — it requires that no new file is completely untouched by any test

## Technical Notes

### Coverage tooling

Skills must not hardcode a specific coverage tool. Use language-appropriate defaults: `php artisan test --coverage` for Laravel, `vitest --coverage` or `jest --coverage` for JS/TS. Skills refer to "run the test suite with coverage reporting" and let the project's tooling handle the rest.

### "New file" definition

A "new file" for coverage purposes is any source file introduced by the current diff that is not a test file, config file, migration, or type definition. Skills must apply judgment: a new `types.ts` exporting only interfaces does not need a test; a new `DocumentController.php` does.

### API boundary test vs E2E test

The API boundary test introduced in Story 2 is a **unit/integration-level test**:
- It runs without a real backend server (uses HTTP mocking: MSW, `nock`, Laravel's `Http::fake()`, etc.)
- It tests the frontend API client layer: correct URL construction, correct payload, correct response handling
- It does NOT open a browser or require both servers running

This is distinct from `aet-qa`'s browser-tier tests, which test the full user flow end-to-end.

### Line count

Current sizes: `aet-plan` ~140 lines, `aet-tdd` ~120 lines, `aet-qa` ~80 lines, `aet-review` ~100 lines. All well under the 400-line limit. Reference detail (examples of coverage tools, API boundary test examples) goes in `references/` files to keep skill instructions readable.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Coverage gate slows down small/trivial changes | Low | Low | Apply only to new source files — config, types, migrations are excluded |
| "Name specific tests per module" in aet-plan adds friction | Medium | Low | Frame as a planning quality check, not a bureaucratic gate; a one-line test name per module is sufficient |
| API boundary test mandate doesn't apply to non-SPA stacks | Low | Low | Trigger only when diff includes both a new backend endpoint and new frontend API client code |

## Open Questions

1. Should the coverage gate in `aet-tdd` be a hard block (skip it = skill aborts) or a checklist item the agent must explicitly sign off on?
2. Should `aet-review`'s hard fail on zero-coverage files auto-generate a stub test, or only flag and stop?

---

*Stage: scope-validated*
*Next step: run `aet-pipeline-implement` (single task) or `aet-work` (multi-task queue)*
