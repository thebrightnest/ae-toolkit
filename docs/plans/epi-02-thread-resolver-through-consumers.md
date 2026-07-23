---
id: epi-02-thread-resolver-through-consumers
size: M
blocked_by: [epi-01-base-branch-resolver]
pipeline: standard
status: queued
security_review: skipped
security_review_reason: replaces literal git refs with resolved ones in existing git invocations; no new command surface
docs_sync: required
docs_sync_reason: renames two public functions and changes what the hygiene gate reports
---

# Plan: Replace every hardcoded `main` with the resolved refs

## Context

- PRD: `docs/prds/non-trunk-integration-workflow-prd.md` (R-4)
- ADR: `docs/adr/044-base-branch-is-configured-not-assumed.md`
- Bug: `docs/bugs/2026-07-22-orchestrator-base-branch-hardcoded.md`

This is the change that makes `epi-01` matter. All five consumers move together
by design — see Locked design.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

Two of the five hardcodings produce reproducible defects (documented in the bug
report). They are planned here because they are the same edit as the
generalization; splitting them would produce two designs for one signature.

## Locked design

- **All five sites change in one plan.** They are:
  1. `create_worktree` (`src/aet/worktree.py:16`) — the `origin/main` default
  2. `remove_worktree` (`:154`) — `rev-list --count main..HEAD`
  3. `check_main_hygiene` (`:377`, `:386`) — renamed `check_base_hygiene`
  4. `_session_diff_stats` (`src/aet/cli/orchestrator.py:428`, `:437`)
  5. `is_ancestor_of_main` (`src/aet/cli/aet_state.py:69`) — renamed
- **Site 5 is the reason this cannot be partial.** `derive_status`
  (`aet_state.py:181-185`) decides `merged` from it. Fix the git plumbing and
  leave the state machine trunk-bound, and a merged task in a `dev` repo never
  derives as `merged` — dependents never unblock and heal's primary repair
  (`:518`) is unreachable. A loud failure becomes a silent deadlock. Do not
  defer site 5 to a follow-up.
- **Renames, not aliases.** Per the project's no-backward-compat rule, delete
  `check_main_hygiene` and `is_ancestor_of_main`; do not keep wrappers.
  `is_ancestor_of_main` is renamed to name the check, not the branch.
- **Site 2 is a behavior fix, not just a rename.** With `main..HEAD` on a
  non-`main` base every worktree counts as ahead, so `remove_worktree` refuses
  and `.worktrees/` accumulates for a whole run. It must count against the
  resolved integration branch.
- **Site 3 takes both refs**, not one: it checks the integration branch for
  dirty/ahead/behind and needs the trunk to know what "in sync" means when they
  differ.
- **Mode-keyed selection is not here.** In `single-pr` mode the hygiene and
  telemetry consumers read the integration branch rather than the trunk
  (ADR-045 decision 6, PRD R-4 final sentence). That selection lands with the
  mode in `epi-08`; this plan only guarantees both resolved refs reach every
  consumer.
- The orchestrator's three `create_worktree` call sites (`:1042`, `:2036`,
  `:2332`) resolve once per run and pass the value down. Do not resolve
  per-call — three resolutions can disagree if config changes mid-run.

## Task List

1. ✓ Take the resolved integration branch in `create_worktree` and pass it from
   all three orchestrator call sites, resolved once per run — M (traces: R-4)
2. ✓ Count against the resolved integration branch in `remove_worktree` so
   cleanup works off-trunk — S (traces: R-4)
3. ✓ Rename `check_main_hygiene` to `check_base_hygiene` taking both resolved
   refs, and update its callers — S (traces: R-4)
4. ✓ Use the resolved integration branch in `_session_diff_stats` so telemetry
   excludes the base-vs-trunk delta — S (traces: R-4)
5. ✓ Rename `is_ancestor_of_main` to take the resolved trunk, and update
   `derive_status` and the heal path that read it — M (traces: R-4)
6. [Deferred: merge and final integration verification happen at the ship stage]
   Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 100 lines; M ≤ 1 day / ≤ 200 lines; L must be
re-evaluated.

### Batching Check

- [x] Not one of several near-identical additions — five distinct call sites
      whose only shared property is the value they read
- [x] The diff is expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with `epi-01` — the resolver is reviewable alone;
      this is the wide rename and benefits from being isolated

Deliberately batched despite touching three modules: a partial migration leaves
two sources of truth for the base, which is the condition ADR-044 exists to
remove.

## Rejected Alternatives

- **Ship sites 1–4 and defer site 5** — rejected, and this was the tempting
  split. Site 5 is invisible in testing on a `main`-based repo and converts the
  reported loud failure into a silent one off-trunk.
- **Keep `check_main_hygiene` as a deprecated alias** — rejected by the
  project's no-backward-compat rule; two names for one gate is how the second
  source of truth returns.
- **Have each consumer call the resolver itself** — rejected: three
  resolutions per run can disagree, and the resolver reads config that an
  operator could edit mid-run.
- **Pass a single `base` everywhere** — rejected: site 3 genuinely needs both
  refs, and collapsing them re-creates the conflation.

## Files to Modify

- `src/aet/worktree.py`
- `src/aet/cli/orchestrator.py`
- `src/aet/cli/aet_state.py`
- `tests/worktree/test_worktree.py`
- `tests/state/test_derive_status_trunk.py` (new)

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] New source coverage: `tests/state/test_derive_status_trunk.py` asserts a
      task merged into a non-`main` trunk derives as `merged` and unblocks its
      dependents — demonstrated **failing** against current `aet_state.py`
      before the rename lands
- [ ] `tests/worktree/test_worktree.py` gains a non-`main` base case covering
      creation and cleanup, and the existing 10 tests still pass unchanged
- [ ] `grep -rn "origin/main\|main\.\.\|main\.\.\." src/aet/` returns no
      hardcoded ref outside the resolver's fallback
- [ ] Telemetry on a non-`main` base reports only the task's own files
- [ ] R-trace coverage: R-4 covered by tasks 1–5
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. The renames are mechanical and self-contained; reverting
restores the `main` assumption wholesale with no data migration, because none of
the changed values are persisted.

## Pipeline

`standard`.

---

*Stage: synced*
*Next step: run `aet-ship`*
