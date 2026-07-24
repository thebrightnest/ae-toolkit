---
id: epi-10-epic-durability-and-closure
size: M
blocked_by: [epi-09-serialized-integration]
pipeline: standard
status: queued
security_review: required
security_review_reason: pushes the integration branch to origin on every integration and changes merge verification — outbound git operations and a fail-closed gate
docs_sync: required
docs_sync_reason: changes how `aet ship` is used at epic level and what merge verification means in single-pr
---

# Plan: Epic durability, gate evidence at integration, and epic-level closure

## Context

- PRD: `docs/prds/non-trunk-integration-workflow-prd.md` (R-20, R-21, R-22)
- ADR: `docs/adr/045-epic-integration-branch-and-task-integration-mode.md`
  (decision 3, durability risk)

Three properties that make `single-pr` safe to run unattended: work is durable
as it integrates (R-20), quality gates still bite even though task branches
never leave the machine (R-22), and the epic closes with the same fail-closed
merge evidence a task closes with today (R-21).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Locked design

- **Push on every integration, open the PR once** (R-20). In `single-pr`, work
  exists only locally until pushed; ADR-027's durability reasoning — unpushed
  work is work that can be lost — applies to the integration branch. The push
  happens inside the serialized integration step (after the squash-merge), so
  `origin` always reflects the last integrated tip. PR opening stays an
  operator action (`aet ship` at epic level) per the PRD open question — this
  plan does not auto-open.
- **Gate evidence moves to integration time** (R-22). The pre-push hook refuses
  task branches missing recorded `pass` verdicts — but in `single-pr` task
  branches never reach `origin`, so that enforcement never fires. The
  integration step verifies the required verdicts (`qa` and `review` always;
  `cso` unless `security_review: skipped`; `sync-docs` unless
  `docs_sync: skipped`) **before the squash-merge lands**, inside the lock.
  The check reuses the verdict logic in `src/aet/cli/hooks.py:180-198`
  (required-stage resolution mirroring `stage_enabled`, `_verdict_status`),
  factored into a shared helper — do not reinvent it; task-branch detection,
  required-stage resolution, and verdict paths must stay single-sourced.
- **Merge verification moves up a level, not away** (R-21). ADR-029's trunk
  merge-verification runs once per epic, when the integration branch's PR
  merges into trunk, retaining fail-closed (no done without verified merge
  evidence) and no-self-merge. What changes is granularity — once per epic
  instead of once per task — because in this mode the epic is the unit that
  reaches trunk.
- **Per-task completion still fires at integration** (R-16, `epi-08`). This
  plan does not move task-level done back to trunk; it adds the epic-level
  verification above it.

## Task List

1. Push the integration branch to `origin` after each successful integration,
   inside the lock — S (traces: R-20)
2. Factor the gate-verdict check out of `hooks.py` into a shared helper and
   enforce it at integration time before the squash-merge — M (traces: R-22)
3. Run ADR-029 merge verification once per epic at the integration branch's PR
   merge, retaining fail-closed and no-self-merge — M (traces: R-21)
4. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 100 lines; M ≤ 1 day / ≤ 200 lines; L must be
re-evaluated.

### Batching Check

- [x] Not one of several near-identical additions — durability, gate evidence,
      and closure, batched because all three live at the integration/closure
      boundary and share the epic-level test fixture
- [x] The diff is expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with `epi-09` — it builds directly on the lock and
      the failure class; stacking them would make the lock unreviewable

## Rejected Alternatives

- **Push only when the epic PR opens** — rejected: it strands the whole epic on
  one laptop for the duration of the run, which is exactly the loss window
  ADR-027 eliminated for tasks.
- **Keep gate enforcement at the epic PR only** — rejected: a missing `review`
  verdict discovered at PR-open time sends the whole epic back instead of one
  task. Integration-time enforcement fails at the granularity that can fix it.
- **Duplicate the verdict logic into the orchestrator** — rejected: two
  implementations of required-stage resolution will drift; the hooks check and
  the integration check would disagree about what `skipped` means.
- **Auto-open the epic PR after the last task integrates** — rejected for now:
  the PRD leaves this open deliberately. Operator action (`aet ship`) is the
  assumed path until the mode has been used.

## Files to Modify

- `src/aet/cli/orchestrator.py`
- `src/aet/cli/hooks.py`
- `src/aet/cli/ship.py`
- `tests/orchestrator/test_integration_push.py` (new)
- `tests/gate/test_integration_gate_evidence.py` (new)
- `tests/ship/test_epic_merge_verification.py` (new)

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] New source coverage: `tests/orchestrator/test_integration_push.py` asserts
      the integration branch tip exists on `origin` after each integration and
      exactly one PR is opened across the epic (PRD acceptance criterion, R-20)
- [ ] New source coverage: `tests/gate/test_integration_gate_evidence.py`
      asserts a task missing a required gate's `pass` verdict is refused at
      integration, that a `skipped` gate key is honoured, and that
      `pr-per-task` enforcement via the pre-push hook is unchanged (R-22)
- [ ] New source coverage: `tests/ship/test_epic_merge_verification.py` asserts
      epic-level verification refuses to self-merge and refuses to mark done
      without verified merge evidence (PRD acceptance criterion, R-21)
- [ ] The factored verdict helper has one implementation; `hooks.py` and the
      orchestrator both call it
- [ ] R-trace coverage: R-20 by task 1; R-22 by task 2; R-21 by task 3
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. Pushed integration-branch history on `origin` remains and is
harmless — it is the operator's own feature branch. Gate enforcement returns to
pre-push only, which in `single-pr` means unenforced; that is the gap this plan
exists to close, so rollback should ship with a hold on `single-pr` use.

## Pipeline

`standard`.

---

*Stage: reviewed*
*Next step: run `aet-cso`*
