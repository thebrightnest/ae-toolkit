---
id: nsr-05-stall-watchdog
size: M
blocked_by:
  - nsr-01-failure-taxonomy-signature
pipeline: standard
status: draft
security_review: skipped
security_review_reason: reuses frh-03's existing process-group kill primitive (`_terminate_process_group`) on a new liveness trigger; no new trust boundary, network, or writer. The watchdog only ever terminates a stalled child, never spawns or grants.
docs_sync: required
docs_sync_reason: adds the operator-facing `--stall-timeout` flag and changes the meaning of `--task-timeout` from primary control to coarse backstop; both are documented in `docs/PIPELINE.md` and `aet run` help.
---

# Plan: Stall Watchdog on Event Silence (wall-clock retained as backstop)

## Context

- PRD: `docs/prds/roadmap-p5-night-shift-runtime-prd.md` (G3; R-9, R-10). Records ADR-031's event-silence half.
- Replaces the wall-clock timeout as the *primary* liveness control with silence detection, so a slow-but-alive session is never killed for being slow — only a session that has stopped emitting is.
- **Ground truth (2026-07-15):** `_run_with_live_tee` (`aet-work/bin/orchestrator:536`) reads the child's stdout line-by-line and already sees every line — the natural place to stamp a `last_output` clock. Today the only timeout is wall-clock in `run_batch` (`:1483`, `now - spawn_times > task_timeout`). The batch parent spawns children **without** a stdout pipe (`:1452`), so silence can only be observed inside the single-plan child's tee loop. The kill primitive `_terminate_process_group` (`:82`, frh-03) already exists.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- In the single-plan session runner (`_run_with_live_tee`), maintain a monotonic `last_output` timestamp updated on every line. Because the read loop blocks on `for line in proc.stdout`, a blocked (silent) read cannot self-check the clock — so a lightweight **watchdog thread** monitors `last_output` and, when `now - last_output > stall_timeout`, calls `_terminate_process_group(proc)` and records the cause as a stall.
- The resulting failure is classified `timeout` (nsr-01) — the same class as a wall-clock kill, so downstream (breaker/triage) treats both identically.
- `--stall-timeout` (default 300 s, PRD Open Question 5: single global to start) is added to the parser and threaded to the session runner.
- **Wall-clock backstop retained (R-10):** `--task-timeout` stays in `run_batch` for the pathological case (a wedged process holding the pipe open but emitting nothing, or a runaway streaming forever), with its default raised well above `--stall-timeout` so the silence watchdog is what fires in normal operation. Both kills route through the same `timeout` classification and `_terminate_process_group`.

## Rejected Alternatives

- **Replace the wall-clock timeout entirely** — rejected: a process that keeps the pipe open but never emits, or one that streams noise forever, is invisible/immune to silence detection; the wall-clock floor is the backstop for exactly those. Demote it, don't delete it.
- **Poll the pipe with `select`/`read(timeout=...)` in the reader loop** — rejected: reworks the proven tee reader and its bounded-buffer semantics; a separate watchdog thread leaves the reader untouched and is easier to test in isolation.
- **Watch telemetry/wire events instead of stdout lines** — rejected: adds a cross-process channel where the tee already has per-line visibility in-process; stdout silence is the cheapest honest liveness signal at this layer.

## Task List

1. Stamp `last_output` in `_run_with_live_tee` and add a watchdog thread that terminates the process group on silence, tagging the cause as a stall — M (traces: R-9)
2. Classify a stall kill as `timeout` via nsr-01 and route it through the normal finalize path — S (traces: R-9)
3. Add `--stall-timeout` (default 300 s) to the parser; raise the `--task-timeout` default so the watchdog is primary and the clock is the backstop — S (traces: R-9, R-10)
4. Docs: document `--stall-timeout` and the demoted `--task-timeout` backstop in `docs/PIPELINE.md` and `aet run` help — S (traces: R-10)
5. Tests: `tests/test_stall_watchdog.py` (new) — M (traces: R-9, R-10, R-13)

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch — orthogonal to the breaker/triage surface; only shares the nsr-01 `timeout` class

## Files to Modify

- `aet-work/bin/orchestrator` (`_run_with_live_tee` watchdog thread + parser + backstop retune)
- `docs/PIPELINE.md`
- `tests/test_stall_watchdog.py` (new)

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] New source coverage — `tests/test_stall_watchdog.py`:
  - `test_silent_session_killed_after_stall_timeout` (classified `timeout`)
  - `test_emitting_session_spared_past_stall_timeout` (still-alive not killed)
  - `test_silent_session_killed_by_wallclock_backstop` (emits nothing, exceeds `--task-timeout`)
  - `test_stall_kill_routes_through_finalize` (integration)
- [ ] R-trace coverage: R-9 by tasks 1–3; R-10 by tasks 3–4; R-13 by task 5; no unknown R-ids
- [ ] Distinguish test types: unit (watchdog timing with a fake clock/process) + integration (finalize routing)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. Timeout handling falls back to wall-clock-only exactly as today; `--stall-timeout` disappears with no persisted state.

## Pipeline

`pipeline: standard` — a concurrency-sensitive change (watchdog thread + process-group kill); `standard` grouping with focused timing tests covers it.

---

*Stage: reviewed*
