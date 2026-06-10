# Retro: Task Detail Modal Testing Gap

**Date:** 2026-05-25
**Trigger:** User manually tested Project Tasks page, found `tasksApi is not defined` and additional runtime errors. Existing E2E tests and newly written unit tests failed to catch them.

## What Happened

1. **Original bug:** `TaskDetailModal.tsx` used `tasksApi` without importing it. E2E tests had `assertNoErrors()` only in `afterAll`, so the `ReferenceError` was collected but not tied to the specific test that caused it.

2. **Agent's first fix:** Added the missing import. Wrote 23 unit tests for `TaskDetailModal` — but **mocked all child components** (`TaskAttachments`, `TaskCommentsSection`, `TaskDependenciesSection`, `Modal`).

3. **User correction:** "Your tests are not really navigating, otherwise would have catched that easily." Opening the task in the real app still threw multiple errors.

4. **Hidden bugs revealed only after removing mocks:**

   - `TaskCommentsSection` assumed `tasksApi.getComments()` returned a raw array. Backend returns `{ success: true, comments: [...] }`. → `comments.filter is not a function`
   - `TaskDependenciesSection` assumed `fetchTaskDependencies()` returned a raw array. Backend returns `{ success: true, dependencies: [...] }`. → `dependencies.some is not a function`
   - `GET /tasks/:taskId/dependents` endpoint was missing entirely. → 404 on every modal open
   - `taskStore.ts` passed wrapped responses through instead of unwrapping them

5. **Root cause of the testing blind spot:** Mocking child components creates a "shallow test" that validates the parent's props and callbacks but never exercises the real component tree. The bugs were in the leaf components' API boundary handling and in a missing backend endpoint — none of which were rendered in the shallow test.

## Systemic Layers That Allowed This

| Layer                                               | Failure                                                                                                                                          |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `.agents/reference/renderer-patterns.md`            | No guidance on when to mock child components vs. render them for real. Agent defaulted to the easiest path (mock everything).                    |
| `AGENTS.md` Rule 11 (API boundary validation)       | Correctly bans `as` casts, but doesn't extend to component-level API consumption. Components assumed raw arrays without normalizing.             |
| E2E test pattern (`e2e/features/tasks.e2e.test.ts`) | `assertNoErrors()` only in `afterAll` delayed error detection to the end of the suite, making it hard to associate errors with specific actions. |

## Fixes Applied

1. **Surgical component fixes:**

   - `TaskDetailModal.tsx`: added missing `tasksApi` import
   - `TaskCommentsSection.tsx`: normalized `getComments` response → `(fetched as { comments?: TaskComment[] }).comments ?? []`
   - `TaskDependenciesSection.tsx`: normalized `fetchTaskDependencies` response → `(result as { dependencies?: TaskDependency[] }).dependencies ?? []`
   - `taskStore.ts`: unwrapped `fetchTaskComments` and `fetchTaskDependencies` before returning
   - `taskHandler.ts`: added missing `GET /tasks/:taskId/dependents` endpoint

2. **Tests rewritten to render real components:**

   - Removed mocks for `TaskAttachments`, `TaskCommentsSection`, `TaskDependenciesSection`
   - Kept mocks only for APIs (`tasksApi`, `filesApi`), stores (`useTaskStore`), and UI primitives (`Modal` — because Radix portals break jsdom)
   - Added explicit tests for wrapped API responses: "handles wrapped API responses in comments/dependencies section without crashing"

3. **E2E improved:**
   - Added `test.afterEach(() => assertNoErrors())` to catch runtime errors immediately after the triggering test

## Learning

**Shallow component tests are a false sense of security.** When a parent renders children that fetch their own data, mocking the children hides:

- API boundary mismatches
- Missing backend endpoints
- Runtime errors in child initialization logic
- Store selector mismatches

The minimal mock boundary for a feature test is: **mock APIs and stores, render real components.** Only mock UI primitives (portals, dialogs) when the test environment literally cannot render them.
