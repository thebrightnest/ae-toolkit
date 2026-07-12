# Bug Report: `aet-work add` deadlocks a plan whose blockers already merged

## Metadata

- **Reported:** 2026-07-12T11:14:49Z
- **Severity:** high
- **Status:** open (workaround applied — see below)

## Symptoms

A plan added to the queue via `aet-work add` **after** its `blocked_by` blockers have
already merged and been archived to `work-history.jsonl` is inserted as `blocked`
with a `pending_blockers` count that includes the already-merged blockers. Nothing
ever decrements that count, so the task is **permanently deadlocked**: `aet-work status`
shows it `blocked`, and the orchestrator's `get_next_unblocked` (which returns "the
first stored-ready task", `aet-work/lib/queue.py:470-475`) never selects it.

No supported command reconciles it:

- `aet-work sync` — archives settled tasks and rebuilds `blocks` edges but explicitly
  "does **not** derive status or promote tasks" (`aet-work/bin/sync:6-7`); it never
  recomputes `pending_blockers`. Reports `0 drifted`.
- `aet-state heal` — reports "No healable discrepancies found" (its derived state for
  these tasks is `blocked`, since it cannot confirm archived blockers as done).
- `aet-work init-queue` — would rebuild from source, but validates the **entire**
  `docs/plans/*.md` corpus (171 files) and aborts on unrelated plans that exceed the
  complexity/`security_review` frontmatter contract.

Observed 2026-07-12 while running `aet-pipeline-plan` on Phase 3 (enforcement-walls):
`ewl-01/03/04/05` were added `blocked` on `cli-03-skills-lint` (and `ewl-01` also on
`frh-18-group-evidence-path-contract`) after both had already merged to main, and sat
deadlocked while the sibling `cli-05` — already in the queue when the same blockers
merged — was correctly `ready`.

## Reproduction Steps

1. Have a blocker task (e.g. `cli-03-skills-lint`) that has reached `merged` and been
   archived into `.agents/work-history.jsonl` (so it is no longer in the active queue).
2. `aet-work add docs/plans/<new>.md`, where `<new>`'s frontmatter `blocked_by` names
   that already-merged blocker.
3. Observe: `✓ Added <new> to the queue as blocked.` with `pending_blockers = len(blocked_by)`,
   counting the already-merged blocker.
4. Run `aet-work sync`, then `aet-state heal` — the task stays `blocked`, `pending_blockers`
   unchanged (`sync` reports `0 drifted`; `heal` reports nothing healable).
5. `aet-work status` never lists the task under "Next ready tasks" → it can never run.

Contrast: a task already in the queue when its blocker merges **is** correctly promoted
to `ready`, because the merge event walks the blocker's `blocks` reverse edges and
decrements its dependents' `pending_blockers`. The defect is purely an ordering
artifact — the dependent was added after the decrement event had already fired.

## Root Cause

`pending_blockers` is an **event-driven counter**, initialized at `add` time and
decremented only when a blocker transitions to a terminal state:

- `aet-work/bin/add` (via `new_task_from_plan`) seeds `pending_blockers` from the
  `blocked_by` list **without reconciling against `work-history.jsonl`**. A blocker that
  is already `merged`/`abandoned` in history is counted as still-pending.
- The blocked→ready decrement fires from the blocker's own merge transition (walking
  `blocks` reverse edges). If the blocker merged **before** the dependent existed, that
  event already fired and will not re-fire — the newly added dependent misses it.
- `aet-work/bin/sync` is append-only and "does not derive status or promote tasks"
  (`:6-7`), so it cannot self-heal the count. `build_blocks` (`queue.py:359`) only wires
  reverse edges among tasks **still in the active queue**, so archived blockers
  contribute no decrement path at all.
- `pending_blockers(task)` (`queue.py:348-356`) returns the stored value when present and
  only falls back to `len(blocked_by)` when it is unset — both count merged blockers.

Net: correctness depends on the order of `add` vs. blocker-merge. Add-after-merge
deadlocks, with no supported reconcile path.

## Impact

- **High**: silently deadlocks queued work. The tasks appear present and correctly
  gated, but never become runnable. Especially likely for plans authored against a
  fast-moving queue (phase-gated roadmaps where the gating task merges during planning) —
  exactly the "duplicate/parallel planning" risk the Phase 3 PRD already flagged.
- A second-order case is worse: `ewl-06` was added `blocked` with `pending_blockers=4`
  when only 2 of its blockers (`ewl-03`, `ewl-05`) are live. Even after those two merge,
  the counter decrements 4→3→2 and sticks at 2 → `ewl-06` re-deadlocks later unless the
  count is corrected.

## Proposed Fix

1. **Primary — fix the source of the wrong count in `add`.** When seeding
   `pending_blockers`, resolve each `blocked_by` id against `work-history.jsonl`
   terminal states (`merged`/`abandoned`) and count only blockers that are neither
   terminal-in-history nor already-satisfied. A blocker already `merged` contributes 0.
   If that zeroes the count, insert the task as `ready` rather than `blocked`.
2. **Safety net — give `heal` (or `sync`) a history-aware `pending_blockers` recompute.**
   Derive each active task's pending count as `|{b ∈ blocked_by : b not terminal-in-history}|`
   and reconcile stored state accordingly. This self-heals drifted/late-added tasks and
   is consistent with the forward-only, derived-state model in
   `docs/adr/011-forward-only-deterministic-work-state.md`.
3. Preferred: do both (1) and (2) — fix the seed and add the reconcile as a guard.

## Regression Test (proposed)

- `test_add_ignores_merged_blockers_in_pending_count` — with a blocker recorded `merged`
  in history, `aet-work add` a plan `blocked_by` that id → task enters `ready`
  (`pending_blockers == 0`).
- `test_add_mixed_blockers` — `blocked_by = [merged-in-history, live-in-queue]` → task
  enters `blocked` with `pending_blockers == 1`.
- `test_heal_recomputes_pending_against_history` — a queued task with a stale
  `pending_blockers` counting a now-merged blocker is reconciled to `ready` by `heal`.

## Workaround Applied (2026-07-12)

Reconciled the four fully-unblocked Phase 3 tasks via the official state tool:

```
aet-state transition ewl-01-gate-submit-cli   blocked ready
aet-state transition ewl-03-hooks-install-pre-push blocked ready
aet-state transition ewl-04-git-refs-default-flip  blocked ready
aet-state transition ewl-05-git-refs-tamper-evidence blocked ready
```

`blocked → ready` is a legal transition (`queue.py:279`). This leaves a residual
`pending_blockers > 0` on a `ready` task (cosmetic; identical shape to `cli-05`, and
`get_next_unblocked` keys off `state` only). `ewl-06` was **left `blocked`** — that is
correct now (`ewl-03`/`ewl-05` are genuinely incomplete), but its overcounted
`pending_blockers=4` must be corrected to `2` by the real fix before those two merge, or
it will re-deadlock.

## Validation

- [ ] Reproduction steps no longer trigger the bug once the fix lands
- [ ] `make validate` passes with the new regression tests
- [ ] `aet-work add` of a plan whose blocker is already `merged` yields a `ready` task
- [ ] `ewl-06`'s `pending_blockers` reconciles to `2` (not `4`) under the fix

## Lessons Learned

- **Pattern:** an event-driven counter (`pending_blockers`) seeded without reconciling
  against already-settled state makes correctness **order-dependent** — it works when the
  blocker merges after the dependent is added, and deadlocks when it merges before.
- **Prevention:** derive readiness from the source of truth (`blocked_by` × terminal
  history) rather than trusting a stored counter mutated only by live events. This is the
  forward-only, derived-state contract of ADR-011 — the deadlock is where the
  implementation diverges from it.
- **Reference:** related to but distinct from
  `docs/bugs/2026-06-19-aet-work-sync-legacy-plans-block-new-tasks.md` (that was
  validation _scoping_ blocking new adds; this is `pending_blockers` _history-awareness_
  deadlocking an added task).
