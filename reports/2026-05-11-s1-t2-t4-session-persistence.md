# Retro: S1-T2 / S1-T4 — Session Persistence

## What Happened

S1-T2 (execution runner persistence) and S1-T4 (chat persistence) were implemented. `aet-review`
caught 4 blockers before merge — all were fixed in the same session. No bad code landed in main.

## Root Causes

### B1 — Wrong session ID used as FK (most dangerous)

`executionRunnerFactory.ts` used `opts.sessionId` — the provider session ID for resuming — as the
FK value for `session_messages.session_id`, which references `tracked_sessions.session_id` (the
Atelier UUID). These are different ID types. The S1-T2 plan code block wrote `opts.sessionId`
without flagging the distinction; the implement agent followed the code block verbatim.

Had this reached production with an active streaming caller, it would have caused FK violations or
orphaned rows — silent data loss.

### B2 — `destroyQueue` async `.finally()` left a zombie window

`sessions.delete(id)` was scheduled inside `.finally()` instead of called synchronously. During
the async gap, any concurrent call to `wrapOutput` for the same `sessionId` would find the old
state, chain onto it, and then have the state deleted under it by the `.finally()`. A retry
scenario (e.g. a session that errors and is re-started with the same ID) would produce sequence
numbers starting at the zombie counter.

### B3 — Test helper `flushQueue` had misleading name and comment

`flushQueue()` was named and commented as if it flushed the queue "multiple times," but it only
yields once via `setTimeout(resolve, 0)`. The helper works because `better-sqlite3` is
synchronous — all DB calls settle in the same microtask tick. Had an async DB operation been
introduced, the tests would silently become unreliable while appearing to pass.

### B4 — Silent persistence dropout not documented

When `sessionService.create()` throws in `onSessionInit`, `chatPersist.fn` is never assigned and
all subsequent events are silently dropped. The catch block only called `logger.error` — no
comment explained that this is intentional degraded-mode behavior (chat continues, persistence
skipped).

## What Went Well

- Review caught all 4 issues before merge — zero bad code in main
- All fixes were targeted and minimal (~15 lines changed across 6 files)
- Typecheck and all 23 tests passed after fixes

## What Could Be Better

- The S1-T2 plan should have explicitly called out the `sessionId` vs `atelierSessionId`
  distinction in the code block (not just in prose)
- The async Map cleanup pattern is a subtle JavaScript trap; architecture docs had no guidance

## Action Items

| Action                                                    | Owner | Done |
| --------------------------------------------------------- | ----- | ---- |
| Add "Session ID Semantics" section to `architecture.md`   | agent | ✅   |
| Add "Async Map cleanup race" section to `architecture.md` | agent | ✅   |
| Add "intentional error swallowing" rule to `AGENTS.md`    | agent | ✅   |
| Append 3 learnings to `.agents/learnings.jsonl`           | agent | ✅   |

## Rules Updated

- `.agents/reference/architecture.md` — "Session ID Semantics" section + "Async Promise Queue" section
- `AGENTS.md` — Mandatory rule: document intentional error swallowing

## Learning

The most dangerous bugs are naming ambiguities that look correct in isolation. `opts.sessionId` is
a valid field name, passes typecheck, and works in tests — but it carries the wrong ID type for
persistence. Disambiguation must happen at the type/field level (`atelierSessionId`) and be
documented in the architecture reference, not just in plan prose.
