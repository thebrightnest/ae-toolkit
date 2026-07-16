---
id: twe-03-desk-actions-merge-abandon
size: M
blocked_by:
  - twe-02-desk-view-risk-rank
pipeline: standard
security_review: required
security_review_reason: introduces two commands that resolve a task id and then trigger a real merge/closure or a terminal `abandoned` transition. A weak id check could merge or abandon the wrong task; fail-closed resolution (reject unknown or non-`awaiting_merge` ids before any action) is the security-critical guard and must be verified.
docs_sync: required
docs_sync_reason: `aet desk merge <id>` / `aet desk abandon <id> --reason` are new user-facing actions on the review cockpit; user docs and the desk's command surface change.
status: approved
---

# Plan: `aet desk` Actions — `merge` (→ Closure Path) + `abandon`

## Context

- PRD: `docs/prds/roadmap-p4-two-human-ends-prd.md` (G1; R-3).
- The **write** half of the desk: once the human has read a task's evidence in the twe-02 view, they act on it in place rather than switching tools.
- **Ground truth (re-grounded 2026-07-15):** the single closure writer is `aet-state record-merge`, driven post-merge by `aet-ship/bin/ship` (verifies via git ancestry / `gh pr view` / diff-equivalence, then writes `merged`, updates the plan footer, removes the task from the live queue). The actual PR merge is skill-driven today (`aet-ship/SKILL.md`). `abandon` records the terminal transition via `aet-state` (`aet-work/lib/aet_queue.py` `awaiting_merge → {merged, abandoned}` at `:282`). **No second closure writer is introduced** (Non-Goals) — `desk merge` drives the same `aet-ship`/`record-merge` path; the exact merge invocation is this plan's implementation choice.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Locked design

- Extend `aet-work/bin/desk` with two argparse subcommands (same subparser shape ewl-01's `gate` established):
  - `aet desk merge <task_id>` — resolves the id against the **live queue**, confirms state is `awaiting_merge`, then drives the existing merge + `aet-ship`/`aet-state record-merge` closure path.
  - `aet desk abandon <task_id> --reason <r>` — resolves likewise, then records the terminal `abandoned` transition via `aet-state` with the reason.
- **Fail closed on identity:** both exit non-zero with a **named** error for an unknown id or a task not in `awaiting_merge`, *before* any merge or state write. The desk never acts on something it cannot positively identify as review-ready.
- `--reason` is required on `abandon` (missing reason → fail-closed error), consistent with the toolkit's recorded-reason discipline.

## Rejected Alternatives

- **A new merge/closure implementation inside `desk`** — rejected: Non-Goals forbid a second closure writer; reusing `aet-ship`/`record-merge` keeps `merged` single-writer and inherits its ancestry/diff-equivalence verification.
- **Interactive confirm prompt before merge** — rejected: the desk is deliberately non-interactive (explicit subcommands), preserving the toolkit's zero-`input()`/`stdin` posture; the P3-deferred fail-closed-confirm helper stays deferred (PRD Open Question 3).
- **Resolve the id from history/archive as well as the live queue** — rejected: only a live `awaiting_merge` task is actionable; widening resolution invites acting on a settled task. Fail-closed on anything not live-and-awaiting.

## Task List

1. [x] Add the `merge` subcommand to `aet-work/bin/desk`: live-queue id resolution, `awaiting_merge` precondition, drive the `aet-ship`/`record-merge` closure path, fail-closed named errors — M (traces: R-3)
2. [x] Add the `abandon` subcommand: id resolution, required `--reason`, terminal transition via `aet-state`, fail-closed named errors — S (traces: R-3)
3. [x] Tests: `tests/test_desk_actions.py` (new) — M (traces: R-3, R-11)
4. [ ] Merge branch to main and verify integration — S [Deferred: runs at `aet-ship`]

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions at the plan level (merge and abandon share the id-resolution guard but are distinct actions with distinct closure paths — batched within this one plan, not across plans)
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with twe-02 — this mutates state through the closure path; twe-02 is strictly read-only

## Files to Modify

- `aet-work/bin/desk`
- `tests/test_desk_actions.py` (new)

## Validation Steps

- [x] `make validate` passes; full suite passes
- [x] New source coverage — `tests/test_desk_actions.py`:
  - `test_merge_drives_closure_path_to_merged`
  - `test_abandon_records_terminal_transition_with_reason`
  - `test_merge_unknown_id_fails_closed_nonzero`
  - `test_merge_non_awaiting_merge_task_fails_closed`
  - `test_abandon_missing_reason_fails_closed`
  - `test_no_second_closure_writer` (asserts `merged` still routed through `record-merge`)
- [x] R-trace coverage: R-3 by tasks 1–2; R-11 (this slice) by task 3; no unknown R-ids cited
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit. Actions are removed; the read-only desk (twe-02) and the existing skill-driven `aet-ship` review flow remain. No state migration.

## Pipeline

`pipeline: standard` with `security_review: required` — a new command that can trigger a merge; the added review stage scrutinizes the fail-closed id guard specifically.

---

*Stage: qa-complete*
*Next step: run `aet-review`*
