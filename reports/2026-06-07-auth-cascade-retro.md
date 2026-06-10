# Retro: 2026-06-07 — Auth Infrastructure Cascade Failure

## Summary

A basic login attempt revealed **6 distinct bugs in a chain**, all of which should have been caught by planning, tests, or review. This retro focuses on **why the aet-\* pipeline allowed them through**, not just what the bugs were.

## The Cascade

| #   | Bug                                                                                                                   | Root Cause                                                    | Where It Should Have Been Caught                                                                         |
| --- | --------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| 1   | **Double-hashed password** — `UserFactory` used `Hash::make()` while `User` casts `password` => `hashed`              | Laravel 11 migration gap; factory not updated for new cast    | TDD: factory test verifying `Auth::attempt()` works. Review: auth-specific lens.                         |
| 2   | **Missing `sessions` table** — `SESSION_DRIVER=database` but no migration existed                                     | Infrastructure never planned; added ad-hoc                    | Plan: infrastructure validation checkpoint. TDD: login → authenticated-request integration test.         |
| 3   | **Sanctum stateful domains missing `localhost:5183`** — SPA auth couldn't establish sessions                          | Vite port changed (Makefile: 5183) but Sanctum config drifted | Plan: env/dev topology alignment checkpoint. QA: cross-service integration test (React proxy → Laravel). |
| 4   | **Frontend swallowed all errors as "Invalid password"** — `LoginPage.tsx` catch block showed generic message for 500s | No frontend error-handling standard in planning or review     | Review: conditional error-handling lens. Plan: UI/UX acceptance criteria for error states.               |
| 5   | **Seeded user had no workspace** — `DatabaseSeeder` created user but not workspace                                    | Invariant ("every user has a workspace") never codified       | TDD: observer/feature test. Plan: data model invariants section.                                         |
| 6   | **DashboardController crashed on null workspace** — `personas()` called on null                                       | Relied on implicit assumption that workspace always exists    | TDD: stats endpoint test with minimal seeded data. Review: null-safety in relationship chains.           |

## Systemic Analysis: Why the aet-\* Pipeline Missed Them

### aet-plan: No Auth Foundation, No Infrastructure Checkpoint

**Finding:** Not a single plan in `docs/plans/` owns the auth infrastructure (Sanctum setup, session handling, `AuthController`, `UserFactory`). All 37 plans build _on top_ of auth without validating it. The `sessions` table migration is absent from every plan. Sanctum config changes are unplanned.

**Gap:** `aet-plan` has no checkpoint for:

- Dev topology alignment (ports, domains, proxies)
- Infrastructure prerequisites (session driver, cache driver, queue driver)
- Auth mechanics (Sanctum SPA mode, cookie domains, CSRF flow)
- Data model invariants ("every X must have a Y")

**Impact:** Auth was treated as "already works" when it was never properly set up.

### aet-tdd: No Auth-Specific Test Mandate

**Finding:** Existing tests (`AdminAuthAndStatsTest`, `StatsEndpointTest`, `OnboardingTest`) cover role responses and endpoint counts, but **no test verifies that a factory-created user can actually log in**. Logout is completely untested. `UserObserver` (workspace auto-creation) has zero tests. The factory itself has no test.

**Gap:** `aet-tdd` mandates behavior-focused tests and vertical tracer bullets, but has **no requirement for auth-specific tests** (login validity, session persistence, token handling, role gates). The tracer bullet can pass through "happy path" without touching auth mechanics.

**Impact:** The most basic auth flow — factory → seed → login → authenticated request — was never exercised in tests.

### aet-qa: Auth Is a "Quick Tier" Mention, Not a Checklist

**Finding:** `aet-qa` lists auth as a "critical path" in the Quick tier, but provides **no auth-specific checklist**. There's no validation of:

- Session establishment after login
- Cookie propagation across requests
- CSRF token flow
- Cross-origin request behavior
- Frontend error message accuracy vs backend status codes

**Gap:** The "completeness check" cross-references frontend API calls with backend routes, but doesn't test whether the _auth mechanism_ between them works.

**Impact:** The frontend calling `/api/stats` and getting 401/500 was never caught because no test exercised the full React → Laravel → DB → response cycle with real cookies.

### aet-review: No Auth/Security Lens, No Infrastructure Lens

**Finding:** `aet-review` has lenses for Project Structure, Architecture, SQL Safety, Conditional Side Effects, Error Handling, Completeness, Tests, and Removal Safety. **No lens for auth correctness, session handling, or infrastructure alignment.**

**Gap:** A reviewer could pass all 8 lenses and still miss:

- A factory double-hashing passwords
- A missing sessions table
- Misaligned Sanctum stateful domains
- Frontend error swallowing

**Impact:** Code that "looks correct" by all standard lenses was fundamentally broken for auth.

## Test Coverage Gaps

| What                                      | Status     | Why It Matters                                                                      |
| ----------------------------------------- | ---------- | ----------------------------------------------------------------------------------- |
| Factory password → `Auth::attempt()`      | ❌ Missing | Would have caught bug #1 immediately                                                |
| Login with invalid credentials → 401      | ❌ Missing | Would validate password hashing is correct                                          |
| Login → cookie/session → `/api/user`      | ❌ Missing | Would have caught bugs #2, #3                                                       |
| Logout → 401 on subsequent request        | ❌ Missing | Validates session invalidation                                                      |
| `UserObserver::created` creates workspace | ❌ Missing | Would have caught bug #5                                                            |
| Dashboard stats with fresh seeded data    | ✅ Partial | `StatsEndpointTest` exists but seeded user had workspace only by coincidence before |
| Frontend error handling per status code   | ❌ Missing | Would have caught bug #4                                                            |

## What the Cascade Reveals

This was not "one bug." It was a **foundational layer failure** where:

1. **Planning assumed auth worked** without ever validating it
2. **TDD tested around auth** without testing auth itself
3. **QA checked API call existence** without checking auth flow viability
4. **Review passed structurally sound code** that failed at the auth boundary

Every aet-\* skill operated correctly within its own scope, but **none of them had scope over the auth boundary**.

## Recommendations

### 1. Add an "Auth Foundation" gate to aet-plan

Any plan that touches auth (login, register, middleware, session, tokens) must include:

- Dev topology alignment (ports, domains, CORS, proxies)
- Session/cache/queue driver verification
- Sanctum/config drift check
- End-to-end auth flow test in the validation strategy

### 2. Add an "Auth Mechanics" mandate to aet-tdd

Every project with auth must have tests for:

- Factory-created user can log in
- Invalid credentials return correct status
- Authenticated request succeeds after login
- Logout invalidates session
- Role gates behave correctly

### 3. Add an "Auth Flow" checklist to aet-qa

For SPA/cookie auth specifically:

- CSRF cookie fetch → login POST → authenticated GET
- Cookie domain/path alignment
- Frontend error messages match backend status codes
- Cross-origin request with credentials

### 4. Add an "Auth & Infrastructure" lens to aet-review

New review checkpoints:

- Password hashing: factory vs model cast alignment
- Session infrastructure: migration exists for database driver
- Auth config: stateful domains, CORS, guards match dev topology
- Frontend error handling: catch blocks inspect status codes
- Data invariants: observers, null-safety, relationship existence

### 5. Project-Level: Write the Missing Tests

Create:

- `tests/Feature/AuthFlowTest.php` — login, logout, session, 401/419/500 handling
- `tests/Unit/UserObserverTest.php` — workspace auto-creation
- `tests/Unit/UserFactoryTest.php` — password hashing correctness

## Learnings

```jsonl
{"date":"2026-06-07","problem":"Auth infrastructure cascade: 6 bugs in login flow revealed that aet-plan, aet-tdd, aet-qa, and aet-review all lack auth-specific scope","layer":"aet-* skill pipeline","fix":"Retro recommends auth foundation gate (plan), auth mechanics mandate (tdd), auth flow checklist (qa), auth+infrastructure lens (review)","prevents":"Basic auth bugs passing through entire PIV loop undetected"}
{"date":"2026-06-07","problem":"No test exercises factory → seed → login → authenticated request end-to-end","layer":"aet-tdd","fix":"Mandate AuthFlowTest covering login validity, session persistence, logout, role gates","prevents":"Password hashing, session, and config bugs reaching production"}
{"date":"2026-06-07","problem":"Sessions table migration completely absent from all 37 plans; added ad-hoc","layer":"aet-plan","fix":"Add infrastructure validation checkpoint to plans: session/cache/queue drivers, migrations, dev topology","prevents":"Missing infrastructure prerequisites"}
{"date":"2026-06-07","problem":"Frontend catch block showed generic 'Invalid password' for all errors including 500s","layer":"aet-review","fix":"Add auth+infrastructure lens checking frontend error handling, status code inspection, config alignment","prevents":"Server errors being misdiagnosed as credential failures"}
```
