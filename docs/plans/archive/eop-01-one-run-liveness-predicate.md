---
id: eop-01-one-run-liveness-predicate
size: M
work_class: critical
blocked_by: []
pipeline: standard
security_review: skipped
security_review_reason: Reads process metadata already readable by the invoking user; adds no input path and no privilege.
docs_sync: required
docs_sync_reason: Establishes the liveness contract two subsystems and the lease depend on.
---

# Plan: One Run-Liveness Predicate, Reading Evidence

## Context

PRD: docs/prds/evidence-over-proxy-prd.md
Decision: ADR-072 (A Proxy Is Not Evidence), decision 2 — identity must be
checked, not assumed. Generalises ADR-064.

Three copies of the same predicate ask whether *a* process holds a PID, never
whether it is *the* process the run started:

| Site | Consumer |
| --- | --- |
| `src/aet/queue.py` `_pid_alive` | `check_lease` — is the lease reclaimable |
| `src/aet/cli/status.py` `_is_process_alive` | `_active_runs` — the active-run list |
| `src/aet/cli/main.py` `_is_process_alive` | `_wait_for_run` — the `--follow` wait |

Every run directory records `started` beside `pid`. No site reads it. Observed on
2026-08-29: `aet status` listed five runs from 2026-08-19 as active; two of the
PIDs belonged to `QuickLookUIService` and `chrome_crashpad_handler`, both started
days after the runs they were attributed to.

`src/aet/liveness.py` is the home for the shared predicate. Its
`_all_processes()` sets the portability pattern to follow: `/proc` when present,
`ps` as fallback, an empty result rather than a crash. The module's existing
classes answer a different question — whether an agent session is doing work —
so the new predicate shares the file, not the definition.

## Intake Triage

- [x] The individual misreads are demonstrable defects and were recorded as such
      in `content/backlog/debt-liveness-is-a-bare-pid-check.md`
- [x] Routed here rather than to `aet-bug-report` because the deliverable is a
      shared contract across three consumers plus the lease, with an ADR behind
      it, not a targeted fix to one call site

## Task List

1. Add a process start-time reader to `src/aet/liveness.py` following
   `_all_processes`'s fallback shape: `/proc/<pid>/stat` field 22 against boot
   time where available, `ps -p <pid> -o lstart=` otherwise, `None` when neither
   answers — S (traces: R-1)
2. Add the run-liveness predicate beside it: a recorded returncode settles the
   question; otherwise the PID must be held and its process start time must not
   be later than the run's recorded `started`. An unreadable start time resolves
   live and emits a diagnostic, per the PRD's open question — S (traces: R-1)
3. Replace the three bare checks with calls to the predicate, deleting the
   duplicated helpers in `status.py` and `main.py` — S (traces: R-1)
4. Route `check_lease` through the predicate so a lease whose owning run is not
   live is reclaimed without `--force` — S (traces: R-2)
5. Unit tests for the predicate: returncode present, PID absent, PID held by a
   later-started process, PID held by the recorded process, unreadable start
   time — M (traces: R-1, R-2)
6. Regression test that a lease left by a run whose PID has been recycled does
   not refuse a mutating queue command — S (traces: R-2)
7. Merge branch to main and verify integration — S

### Floor Check

- [ ] Expected diff is below the calibrated floor threshold
- [ ] The change is limited to one subsystem and maintains no architectural invariant
- [ ] `Files to Modify` substantially overlaps a sibling it is ordered against
- [ ] This is docs-only and its sole consumer is a single sibling

No boxes checked. The predicate is the invariant the ADR records, and it crosses
the queue, status and run-wait subsystems.

## Rejected Alternatives

- **Compare against the process's own command line instead of its start time** —
  rejected: an orchestrator re-spawned with an identical command line is
  indistinguishable, and the comparison is not portable across the two
  enumeration paths.
- **Write a heartbeat file and treat staleness as death** — rejected: new
  mechanism, and it converts a crash into a timed wait. The evidence needed is
  already on disk in `started`.
- **Take a psutil dependency** — rejected: `_all_processes` already demonstrates
  the repo's answer to this, and a runtime dependency for one field is a poor
  trade.
- **Fail-dead on an unreadable start time** — rejected in the PRD: it risks two
  orchestrators against one board, while fail-live risks only a lease an operator
  can reclaim explicitly.

## Files to Modify

- `src/aet/liveness.py`
- `src/aet/queue.py`
- `src/aet/cli/status.py`
- `src/aet/cli/main.py`
- `tests/orchestrator/test_liveness.py`
- `tests/queue/test_lease_reclaim.py` (new — covered by `test_lease_reclaim.py`)

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: every in-scope R-id is covered by ≥ 1 task or explicitly deferred with a reason; no task cites an unknown R-id
- [ ] No `os.kill(` liveness check survives outside `src/aet/liveness.py`
- [ ] `aet status` on a run directory whose PID belongs to a later-started
      process omits that run from the active list
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. The three bare checks return, which is the pre-existing state:
stale runs render as active and a recycled PID can hold the lease. Nothing else
depends on the predicate.

## Pipeline

`standard` — this changes the predicate the run lease consults.
