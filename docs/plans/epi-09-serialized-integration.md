---
id: epi-09-serialized-integration
size: M
blocked_by: [epi-08-single-pr-completion-loop]
pipeline: standard
status: queued
security_review: skipped
security_review_reason: adds a local advisory lock and a failure class over existing git and test invocations; no new external surface
docs_sync: required
docs_sync_reason: documents the Integration Failure outcome category in docs/CONVENTIONS.md and CONTEXT.md
---

# Plan: Serialize integration behind a lock, re-validate, and classify failures

## Context

- PRD: `docs/prds/non-trunk-integration-workflow-prd.md` (R-18, R-19)
- ADR: `docs/adr/045-epic-integration-branch-and-task-integration-mode.md`
  (decision 5)

`pr-per-task` gets merge serialization free from the forge. `single-pr` makes
AET own it. This is the one genuinely new mechanism in the epic; everything
else generalizes existing code. It is deliberately the same shape as the
existing queue lock (`src/aet/queue.py:25-85`, `FileLock`) — local,
single-operator, advisory. It orders one operator's own concurrent pipelines;
it is not a claim-check, not a lease, and not visible to anyone else.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [ ] If a reproducible defect was described, redirected to `aet-bug-report`

## Locked design

- **The lock covers the integration step only**: rebase onto current tip →
  re-validate → squash-merge. Implementation stages stay concurrent up to
  `--max-jobs`. Serializing implementation would trade the feature's main
  benefit to avoid building the lock (ADR-045, alternatives).
- **Re-validation after rebase is mandatory, not belt-and-braces.** In
  `pr-per-task` the forge re-runs checks on the merge result; `single-pr`
  removes the forge from the per-task path, so without this step AET would
  integrate combinations nothing has tested. A task that passed against an
  older tip has not been shown to pass against the tip it lands on.
- **Integration failure is its own outcome category, not a failure class.** A
  rebase conflict or a post-rebase validation failure is not a task failure —
  the task passed; the combination did not. The ADR-030 **Failure Class** menu
  (`environment`/`flaky`/`design`/`timeout`/`canceled`) is a fixed,
  agent-session-scoped list and stays unchanged. **Integration Failure** is an
  engine-level outcome (CONTEXT.md, Branch Model): it is never triaged as a
  task failure, never requeued, and does not consume the per-task circuit
  breaker's identical-signature count. The task is marked failed with the
  integration signature so a human decides. `docs/CONVENTIONS.md` (Runtime
  Failure Handling) documents the category next to the taxonomy, not in it.
- **Tests assert ordering, never sleep.** The suite pins orchestrator tests to
  one xdist worker (`--dist=loadgroup`); these tests land in that group and
  must not add wall-clock time to an already-serialized group (PRD technical
  notes). Prove serialization by asserting lock acquisition order, not by
  timing.

## Task List

1. Add the local advisory integration lock and gate the integration step
   (rebase → re-validate → squash-merge) behind it — M (traces: R-18)
2. Re-run task validation inside the lock after the rebase; a failure aborts
   the integration before the squash-merge — M (traces: R-18)
3. Add the Integration Failure outcome category, route it outside task triage
   and the circuit breaker, and document it in `docs/CONVENTIONS.md`
   — S (traces: R-19)
4. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 100 lines; M ≤ 1 day / ≤ 200 lines; L must be
re-evaluated.

### Batching Check

- [x] Not one of several near-identical additions — a lock, a re-validation,
      and a failure class around one step
- [x] The diff is expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with `epi-08` — see epi-08's Rejected Alternatives;
      the lock reviews best against a stable completion loop

## Rejected Alternatives

- **Serialize with `--max-jobs 1` in `single-pr`** — rejected in ADR-045: it
  removes the need for the lock by removing concurrency, trading the feature's
  main benefit for a mechanism the queue lock already demonstrates is cheap.
- **Re-validate only the diff intersection (changed files' tests)** — rejected:
  a rebase can break a test neither task touched (semantic conflict). The forge
  runs the full gate on the merge result in `pr-per-task`; parity means the
  full task validation.
- **Treat integration conflicts as task failures with `requeue`** — rejected:
  the retry cannot change the combination it lands on, so requeue spends money
  re-running a task that already passed. This is ADR-027's "halt rather than
  churn" reasoning applied one level up.
- **Rebase the whole queue of pending integrations in one lock hold** —
  rejected: a long-held lock stalls all pipelines behind the slowest
  re-validation; per-task holds keep implementation concurrent.

## Files to Modify

- `src/aet/cli/orchestrator.py`
- `src/aet/integration_lock.py` (new)
- `docs/CONVENTIONS.md` (failure taxonomy)
- `tests/orchestrator/test_integration_serialization.py` (new)

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] New source coverage: `tests/orchestrator/test_integration_serialization.py`
      asserts with `--max-jobs 3` that integration steps do not interleave
      while implementation stages do, by lock acquisition order with no sleeps
- [ ] The same test module asserts a post-rebase validation failure is reported
      as an Integration Failure, is not triaged as a task failure, and does
      not increment the task's requeue count (PRD acceptance criterion, R-19)
- [ ] `tests/orchestrator/test_integration_serialization.py` covers
      `src/aet/integration_lock.py`: contended acquisition is ordered, and the
      lock is released on rebase conflict, validation failure, and crash
- [ ] `docs/CONVENTIONS.md` documents Integration Failure next to the taxonomy;
      the five-value ADR-030 menu is unchanged
- [ ] R-trace coverage: R-18 by tasks 1–2; R-19 by task 3
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. The lock file (`.agents/integration.lock`) may linger; it is
advisory and ignored, same as the queue lock sidecar. Integrations in flight at
revert are protected by the squash-merge being atomic per task.

## Pipeline

`standard`.

---

*Stage: plan-approved*
*Next step: run `aet-work`*
