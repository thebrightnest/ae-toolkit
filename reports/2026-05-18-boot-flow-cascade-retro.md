# Retro: BOOT-1 Boot Flow "Fix" Cascade

## What Happened

A production bug was reported: the renderer boot sequence crashed with `TypeError: Cannot read properties of undefined (reading 'installed')` because the `.catch()` fallback in `main.tsx` was missing the `python` field. Additionally, HTTP auth calls were fired before the backend server was ready, causing auth failures that were masked as setup-page errors.

The fix should have been **~3 lines**: add `python` to the fallback object, and wait for the backend-ready signal before firing HTTP requests.

Instead, the agent treated this as a feature and produced:

- A 120-line PRD for "Boot Flow with Backend Readiness"
- A 200-line plan for extracting an `AppReadinessProvider`
- New IPC broadcast logic (`backend-ready` to all windows)
- New preload APIs (`onBackendReady`, `isBackendReady`) — later removed
- A 500-line test file for the provider
- Three follow-up fix commits to repair the damage:
  1. Proxy object couldn't serialize across `contextBridge.exposeInMainWorld` → broke the entire preload
  2. Dev/port detection mismatch between main (`app.isPackaged`) and preload (`process.defaultApp`) on macOS
  3. StrictMode double-run wasn't guarded, causing duplicate boot sequences

**Total churn: 1,165 insertions, 187 deletions across 14 files. The original bug: 2 lines.**

And the app **still has a race condition**: `getLocalToken()` is set _before_ `fastifyApp.listen()` completes, so the renderer treats the token as "backend ready" and fires HTTP requests at a server that isn't listening yet. The timeout also no longer starts immediately when entering `waiting_for_backend` — it only starts after `getLocalToken()` resolves, creating a potential infinite-hang window.

## Root Cause

**Layer 1: Scope discipline failure (AGENTS.md / planning)**
The agent violated the AGENTS.md rule "Make MINIMAL changes to achieve the goal." A bug fix was escalated into a "boot flow rewrite" with new abstractions, new IPC surface area, and new state machine phases. Every new line of code was a liability that manifested as a new bug.

**Layer 2: Missing Electron preload guardrails (`.agents/reference/electron-notes.md`)**
There was no documented rule that `contextBridge.exposeInMainWorld` cannot serialize Proxy objects. The agent introduced a Proxy-based shim without knowing this Electron constraint. The entire preload script failed, breaking `window.atelierNative` and `window.claudeApi` globally.

There was also no documented rule about dev-mode detection mismatches on macOS (`app.isPackaged` vs `process.defaultApp`), causing the main process and preload to disagree about which port to use.

**Layer 3: Test coverage gap**
The `AppReadiness.test.tsx` file tests the React provider in isolation with mocked IPC. It does not test the actual integration with the main process. The Proxy serialization bug, the dev port mismatch, and the `getLocalToken()` / `listen()` race were all integration-level issues invisible to unit tests. No manual smoke test was performed before declaring "pipeline complete."

## What Went Well

- The follow-up fix commits did eventually identify and document the Proxy and port-detection issues
- `make check` passes (lint + typecheck)
- The preload unit tests now verify the shim is a plain object

## What Could Be Better

1. **Bug fixes must stay minimal.** The PRD/plan template should force a "minimal fix" alternative to be considered before any new abstraction is introduced.
2. **Electron preload constraints must be documented.** Proxy serialization, `contextBridge` cloneability, and dev-detection edge cases should be in `electron-notes.md`.
3. **Integration smoke test before merge.** A provider that gates the entire app boot cannot be validated by unit tests alone. `make dev` + visual confirmation of cold-start boot should be a hard gate.
4. **Timeout guards must be robust.** The `backend_timeout` phase regressed because the timeout was moved inside an async `.then()` instead of starting immediately on phase entry.
5. **Don't use side-effect tokens as readiness proxies.** `getLocalToken()` being truthy does not mean `fastifyApp.listen()` has completed. Backend readiness must be signaled explicitly after the server callback confirms the port is bound.

## Action Items

| Action                                                                                     | Owner | Due |
| ------------------------------------------------------------------------------------------ | ----- | --- |
| Add "Bug Fix Scope Discipline" rule to AGENTS.md                                           | Agent | Now |
| Add Electron `contextBridge` serialization rules to `.agents/reference/electron-notes.md`  | Agent | Now |
| Fix `backend-ready` broadcast to occur after `fastifyApp.listen()` callback, not before    | Agent | Now |
| Restore immediate timeout in `AppReadinessProvider.waitForBackend()`                       | Agent | Now |
| Add loading state for `auth` phase so `AuthScreen` isn't shown during auth check in-flight | Agent | Now |

## Rules Updated

- `AGENTS.md` — new "Bug Fix Scope Discipline" critical rule
- `.agents/reference/electron-notes.md` — new "Preload Serialization" section

## Learning

Over-engineering a bug fix into a feature rewrite multiplies bug count. The correct response to a 2-line bug is a 2-line fix, not a 1,000-line rewrite. Every new abstraction, IPC channel, and preload API is a liability that must be justified against the cost of getting it wrong.
