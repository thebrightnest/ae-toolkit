---
id: frh-17-queue-mutation-guard
size: M
blocked_by:
  - frh-15-curated-flow-intake
  - frh-16-live-frontier-batch-exit
pipeline: standard
status: merged
---

# Plan: Queue Mutation Guard — Run Lease and Tamper-Evident Writes

## Context

- PRD: `docs/prds/fable-review-hardening-prd.md` (G1/G5 adjunct; owner-requested 2026-07-10)
- Incident (2026-07-09 evening): while a batch was live, a second operator session added tasks and ran `sync` through the sanctioned CLI. The writes were legal, unlocked (frh-02 not yet merged), and invisible to the running orchestrator's operator. Nothing in the system models _who may mutate the sprint, or when_. Per ADR-011's principle, that rule must be code, not convention.

Two enforcement layers, both stdlib:

1. **Run lease** — the orchestrator declares "a run owns this queue"; mutating commands from outside the run refuse politely.
2. **Tamper-evident writes** — the queue carries a monotonic revision + content hash stamped by the state layer; readers fail closed on state the system didn't write (e.g., hand-edited JSON).

Out of scope (recorded for the strategic backlog): hard _prevention_ for agents requires harness-level enforcement — MCP-exposed mutations plus hooks blocking raw file/binary access (fable-review strategic item 10). This plan makes violations impossible to do accidentally and impossible to miss.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Task List

1. `lib/queue.py`: lease helpers — `acquire_lease(queue_file, run_id)` (writes `.agents/work-queue.lease` JSON: `run_id`, `pid`, `started_at`), `release_lease`, `check_lease` (no lease → ok; lease with dead PID → stale, reclaim with warning; live lease → ok only if caller's `AET_RUN_ID` matches). Lease acquisition/release under the existing `queue_lock` — S
2. `orchestrator`: `run_batch` and top-level `run_single` acquire the lease after hygiene and release it in the existing `finally`; children inherit `AET_RUN_ID` (already exported) — S
3. Guard mutating entry points — `add`, `sync`, `init-queue`, and `aet-state` mutating subcommands (`transition`, `set-stage`, `record-merge`, `heal --apply`): call `check_lease` before writing; refusal message names the live `run_id` and suggests re-running after the batch or `--force`; `--force` proceeds with a loud warning and a history/evidence note where applicable — M
4. Tamper evidence in `lib/queue.py`: `write_queue` stamps wrapper metadata with `revision` (monotonic int) and `content_hash` (sha256 over the canonical `tasks` dump); `read_queue` verifies when the fields are present — mismatch raises `QueueIntegrityError` ("queue modified outside aet-state — run `aet-state audit`"); mutating paths fail closed, read-only paths (`status`, `report`) print the warning and continue; legacy queues without stamps are accepted and stamped on first write — M
5. Tests: `tests/test_queue_guard.py` (new) — M
6. Update `aet-work/SKILL.md` (one short "mutation guard" note: what the lease is, when `--force` is appropriate) and add `.agents/work-queue.lease` + `.agents/work-queue.json.lock` to `.gitignore` (the lock sidecar was missed by frh-01's implementation) — S
7. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with related tasks

## Files to Modify

- `aet-work/lib/queue.py`
- `aet-work/bin/orchestrator`
- `aet-work/bin/aet-state`
- `aet-work/bin/add`
- `aet-work/bin/sync`
- `aet-work/bin/init-queue`
- `aet-work/SKILL.md`
- `.gitignore`
- `tests/test_queue_guard.py` (new)

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] New source coverage — `tests/test_queue_guard.py`:
  - `test_add_refused_while_lease_held_by_live_run`
  - `test_child_with_matching_run_id_allowed`
  - `test_stale_lease_dead_pid_reclaimed_with_warning`
  - `test_force_overrides_lease_with_warning`
  - `test_lease_released_on_batch_crash` (finally path)
  - `test_read_fails_closed_on_content_hash_mismatch`
  - `test_revision_increments_monotonically`
  - `test_legacy_queue_without_stamp_accepted_then_stamped`
- [ ] Manual: start a batch, attempt `aet-work add` from a second shell → refusal names the live run
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit; delete any leftover `.agents/work-queue.lease`. Stamped wrapper fields are extra keys old readers ignore (the envelope logic preserves unknown wrapper metadata), so queues written in the interim remain readable.

---

_Stage: merged_
_Next step: run `aet-ship`_
