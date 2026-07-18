---
id: gib-04-versioned-membership-closure-push
size: M
blocked_by:
  - gib-03-status-liveness-contract
pipeline: standard
status: merged
security_review: required
security_review_reason: changes which work `aet run` selects (membership derived from committed status, not a local file) and adds a network `git push` to the closure/commit path. A wrong derivation runs unscheduled work or silently empties the sprint; a push that half-applies could leave a task closed locally but live remotely. Both are correctness boundaries requiring verification.
docs_sync: required
docs_sync_reason: `aet run` selection semantics change (queue derived from committed status) and closure now pushes; the behavior is documented in CONTEXT.md / `docs/PIPELINE.md` and the aet-work/aet-ship skill docs.
---

# Plan: Versioned Sprint Membership + Closure Push

## Context

- PRD: `docs/prds/github-issues-backlog-projection-prd.md` (R-8, R-9, R-12).
- **Ground truth (2026-07-17):** membership is curated in `.agents/work-queue.json` (gitignored), so the sprint cannot travel. `ready` is already computed — `aet-state:309` releases dependents (`append_history(dep, dep_state, "ready", "release")`) and `pending_blockers` falls back to `len(blocked_by)`. `record-merge` commits at `aet-state:889` and never pushes; `git push` lives only in `aet-ship` prose. `aet desk merge` → `record-merge` therefore leaves `status: merged` local-only.
- The load-bearing change: takes ADR-013 ("queue is an ephemeral cache rebuilt from plan truth") to its conclusion. Blocked by gib-03 (needs the committed-status signal).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**; folds in the closure-push defect (R-8) as a scoped fix

## Locked design

- **Membership derives from committed status.** The queue is (re)built from plans where `status == queued` (in the sprint), reading their queue `state` for the live runtime position. `status ∈ {draft, approved}` is on-the-board-but-not-in-sprint; terminal/statusless is excluded. `aet run`/`next` select from the derived queue, so two clones select identically after a pull.
- **`ready`/`blocked` stay computed.** No human or label sets them; `pending_blockers` over `blocked_by` remains the sole source (R-12). Unchanged, asserted by a guard test.
- **Closure pushes.** `record-merge` pushes the status commit after committing. A push failure prints a recoverable error, leaves the local commit intact, and is idempotent on re-run (never half-closes). Generalized as a small `commit_and_push_status(plan_file, status)` helper so gib-06's `aet add`/promote reuse the exact path.

## Rejected Alternatives

- **Keep membership in the local queue file, mirror it to GitHub** — rejected (PRD): a mirror of a local-only truth shows teammates something they cannot reproduce; membership must be versioned first.
- **Push from a git hook instead of the command** — rejected: hooks are Mode-1 client-side and bypassable; the command owning the push is explicit and testable.
- **Let `ready` be set by promotion** — rejected: `ready` is a DAG fact (ADR-011 determinism); promotion sets `status: queued`, the engine computes readiness.

## Task List

1. Derive queue membership from committed `status` (queued) in `init-queue`/`sync`/`next`; keep queue `state` as the runtime axis — M (traces: R-9)
2. Add `commit_and_push_status(plan_file, status)` helper; wire `record-merge` to push after commit, recoverable + idempotent — M (traces: R-8)
3. Guard: `ready`/`blocked` remain computed from `blocked_by` only — S (traces: R-12)
4. Docs: `aet run` selection + closure-push behavior in CONTEXT.md / `docs/PIPELINE.md` — S (traces: R-8, R-9)
5. Tests: `tests/test_versioned_membership.py`, extend `tests/test_aet_state.py` — M (traces: R-8, R-9, R-12)

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not near-identical additions
- [x] Diff exceeds 3 files / 50 lines
- [x] Cannot share a branch — selection + closure surface

## Files to Modify

- `aet-work/bin/init-queue`, `aet-work/bin/sync`, `aet-work/bin/next`
- `aet-work/bin/aet-state` (record-merge push), `aet-work/lib/aet_queue.py` (helper)
- `CONTEXT.md`, `docs/PIPELINE.md`
- `tests/test_versioned_membership.py` (new), `tests/test_aet_state.py`

## Validation Steps

- [ ] `make validate` passes; `frh-14` parity suite still green (derivation flip safety net)
- [ ] New source coverage — `tests/test_versioned_membership.py`:
  - `test_queue_membership_derived_from_status_queued`
  - `test_two_clones_select_same_task_after_pull` (simulated second checkout)
  - `test_ready_blocked_still_computed_from_blocked_by` (R-12 guard)
  - extend `test_aet_state.py`: `test_record_merge_pushes_status_commit`, `test_push_failure_is_recoverable_and_idempotent`
- [ ] R-trace coverage: R-8 (t2), R-9 (t1), R-12 (t3); no unknown R-ids
- [ ] Distinguish test types: unit (derivation, blocker math) + integration (record-merge commit+push; two-checkout selection)
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. Membership returns to local-file curation; closure returns to commit-without-push (regressing the desk-merge gap). No stored data migration — the queue is rebuildable either way (ADR-013).

## Pipeline

`pipeline: standard` — selection semantics + a new network write in the closure path; standard grouping is warranted.

---

_Stage: merged_
