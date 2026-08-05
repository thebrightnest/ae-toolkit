---
id: lop-01-unpublished-plan-intake-and-hygiene
size: M
work_class: critical
blocked_by: []
pipeline: standard
status: queued
security_review: required
security_review_reason: removes a durability gate that has guarded every unattended run since ADR-027, and changes git-state handling at queue intake; the hygiene narrowing must not admit a stale-base run
docs_sync: required
docs_sync_reason: `aet sprint add` loses the `--allow-untracked` flag (user-facing CLI removal), the base-hygiene contract changes, and ADR-027's gate is superseded for plan paths
---

# Plan: Stop Publishing Plans at Intake, Narrow Hygiene to Code Paths

## Context

- PRD: `docs/prds/local-only-plans-prd.md` (R-1, R-2, R-4, R-8, R-9)
- ADR: `docs/adr/054-plan-documents-are-outside-the-durability-gate.md` —
  decisions 1, 2 and 5 govern this plan.
- ADR-027 (`docs/adr/027-main-hygiene-halts-unattended.md`) is the gate this
  plan narrows. Its Alternatives section rejected a surgical per-plan check as
  "more code for the same coverage" — an economy argument, not a safety one.
- ADR-034 (`docs/adr/034-settled-from-versioned-plan-data.md`) decision 3 is
  revised by ADR-054: mid-sprint `status: queued` stops being durable; the
  closure-written settled status is unchanged. Neither ADR is edited in place.

**Verified current behaviour (2026-08-05):**

- `check_base_hygiene` (`src/aet/worktree.py:445`) runs `git status --short
  --untracked-files=all` and filters only through `AET_IGNORED_PATHS`
  (`worktree.py:417`), which covers `.agents/` and `.worktrees/` — not
  `docs/plans/`. An untracked plan therefore reads as "Working tree is dirty".
- The ahead-of-origin check (`worktree.py:481-498`) counts commits with
  `rev-list --count origin/<b>..<b>` and does not inspect their paths.
- `enforce_base_hygiene` (`src/aet/cli/orchestrator.py:324-339`) is fail-closed
  in **both** execution modes. The 2026-07-14 learning about unattended
  warn-and-continue is outdated.
- `aet sprint add` refuses untracked plans at `src/aet/cli/sprint.py:127`
  unless `--allow-untracked` is passed, then calls `commit_and_push_status`
  unconditionally at `:172` — so the flag never actually prevents publishing.
- `copy_untracked_files` (`worktree.py:255`) already mirrors untracked plans
  into the worktree before the plan-existence check
  (`orchestrator.py:1226`, `:1260`), so untracked plans already reach the agent.
  This plan does not need R-3's overlay to deliver a working end-to-end path.
- `working_tree_hash` (`src/aet/verifier.py:81-121`) seeds a temp index from
  HEAD and runs `git add -A`, so untracked plans are already included in the
  verdict `tree_hash`. R-8 pins this rather than changing it.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
  — the hygiene gate behaves exactly as ADR-027 specified; this changes the
  specification, it does not fix a deviation from it.

## Locked design

- **The choke point gates on status terminality, not on path alone.** R-2 names
  `commit_and_push_status` (`src/aet/queue.py:685`) as the single gate, but that
  function serves *both* intake (`status: queued`) and closure
  (`status: merged`, `src/aet/cli/aet_state.py:1118`) — and both operate on
  `docs/plans/*.md`. A purely path-based skip would silently disable closure's
  durability write, which the PRD explicitly preserves. The gate is therefore:
  **for a path in the deferred set, commit and push only when the status is
  terminal (`merged`, `abandoned`); otherwise write the file and return.**
  This expresses the ADR-034 revision exactly — mid-sprint status is local,
  settled status is durable — and keeps one point of control.
- **Hygiene narrowing is path-classified, never count-based.** The
  ahead-of-origin check resolves the changed paths of the diverging commits
  (`git diff --name-only origin/<b>..<b>`) and passes only when *every* path is
  in the deferred set. A commit mixing a plan and a source file is a violation,
  which is the whole point of narrowing rather than removing the check.
- **One constant, four consumers.** The deferred path set is defined once and
  read by intake, hygiene, and (in `lop-02`) materialization and cleanup. It is
  deliberately separate from `copy_untracked_files`' six-directory mirror,
  which is an unrelated concern and stays as it is.
- **`--allow-untracked` is removed, not defaulted to true.** Untracked is now
  the normal case, so a flag asserting it is noise. Per project policy there is
  no deprecation window.
- **Hygiene stays fail-closed in both execution modes.** Narrowing the check's
  *scope* must not touch its *strictness*; ADR-027's unattended contract for
  non-plan paths survives intact.

## Rejected Alternatives

- **A `plan_durability: committed|local` config toggle** — rejected: at
  plans-only scope nothing load-bearing is deferred, so there is no posture
  worth a second code path. Costed at ~13 files by the `integration_mode`
  precedent (4 source, 9 test) for no delivered behaviour. Decided 2026-08-05.
- **Path-only gating in `commit_and_push_status`** — rejected: it would disable
  closure's durability write, since closure writes `merged` to the same paths.
- **Removing the ahead-of-origin check entirely** — rejected: it protects
  against building a worktree off a stale `origin` when local commits contain
  *code*, which is a live concern unrelated to plans.
- **Keeping `--allow-untracked` as a no-op for compatibility** — rejected: no
  backward compat in AET; a flag that no longer gates anything is a lie.
- **Deferring R-8 to its own plan** — rejected: tests that pin
  `tree_hash`/lint/status behaviour under untracked plans are the evidence that
  this plan is safe, not a follow-up to it.

## Task List

1. Define the deferred-path constant (`docs/plans/`) and its membership helper
   in `src/aet/worktree.py`, exported for the intake, hygiene, and (later)
   materialization consumers — S (traces: R-1)
2. Gate `commit_and_push_status` on status terminality for deferred paths:
   write the file only for non-terminal statuses, commit and push for `merged`
   and `abandoned` — S (traces: R-2)
3. Remove the untracked-plan refusal and the `--allow-untracked` flag from
   `aet sprint add`; confirm `aet backlog` intake writes status without
   publishing — S (traces: R-2)
4. Narrow `check_base_hygiene`: exclude deferred paths from the dirty check,
   and pass the ahead-of-origin check only when every diverging path is in the
   deferred set — M (traces: R-4)
5. Report the posture: `aet sprint add` states the plan was queued without
   publishing; the orchestrator prints a one-line run-start notice that plan
   durability is deferred to the PR — S (traces: R-9)
6. Tests, including the ADR-027 regression: an untracked plan queues, runs, and
   reaches the worktree; a mixed plan+code commit still halts; a non-plan dirty
   path still halts; `tree_hash`, `aet plans lint`, and `aet status` report no
   drift for untracked plans (see Validation Steps) — M (traces: R-4, R-8)
7. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 150 lines · M ≤ 1 day / ≤ 600 lines.

### Floor Check

- [x] Stands alone: intake and hygiene must change together — relaxing intake
  alone queues a plan the run then halts on, and relaxing hygiene alone leaves
  intake refusing to queue it. Together they deliver the end-to-end outcome
  (an untracked plan queues and runs) because `copy_untracked_files` already
  mirrors untracked plans into the worktree.
- [x] Expected diff materially exceeds branch/PR overhead: two subsystems plus
  the regression suite that justifies removing a durability gate.
- [x] Cannot share a branch with `lop-02`: this plan is the behaviour change;
  `lop-02` moves the plan into the PR diff and is separately shippable on top.

## Files to Modify

- `src/aet/worktree.py` (deferred-path constant, `check_base_hygiene`)
- `src/aet/queue.py` (`commit_and_push_status` terminality gate)
- `src/aet/cli/sprint.py` (untracked refusal, `--allow-untracked`, posture line)
- `src/aet/cli/backlog.py` (confirm intake path)
- `src/aet/cli/orchestrator.py` (run-start posture notice)
- `tests/` — hygiene, intake, verifier, plans-lint, status coverage
- `docs/CONVENTIONS.md`, `AGENTS.md` (hygiene contract, CLI removal)

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: R-1, R-2, R-4, R-8, R-9 each covered by ≥ 1 task
- [ ] New source files: none introduced; the constant lives in `worktree.py`
      beside `AET_IGNORED_PATHS` and is covered by the hygiene tests
- [ ] Unit: deferred-path membership, terminality gate. Integration: intake →
      queue → run reaches worktree. Boundary: hygiene against a real git repo
      with mixed commits
- [ ] ADR-027 regression explicitly named: a plan queued against an unpushed
      tree must reach the worktree, not produce an empty one
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the branch. The constant, the terminality gate, and the hygiene
narrowing are additive edits to three functions with no data-format change and
no migration — plans already committed keep working, and reverting restores
ADR-027's gate exactly. Any plan queued while this was live remains on disk
untracked and can be committed by hand.

## Pipeline

`standard` — TDD → implement → QA, then review and CSO. Chosen over `full`
because the change is two functions and a flag removal; chosen over `minimal`
because it removes a safety gate and `work_class: critical`.

---

*Stage: plan-approved*
*Next step: run `aet-work`*
