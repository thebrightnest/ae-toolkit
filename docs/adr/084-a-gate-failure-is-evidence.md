---
subject: gate-failure-evidence
relates: [23, 30, 65, 69, 71]
---

# A Gate Failure Is Evidence, and Retries Are Bounded

## Status

Proposed. Amends ADR-030 decisions 2 and 3 and extends the ADR-065 decision 1
pattern list. PRD: `docs/prds/gate-failure-is-evidence-prd.md`.

## Context

ADR-030 classifies every terminating session and counts identical failure
signatures: three on one task quarantine it. The classification runs only when
a session exits non-zero. A checking stage can also fail after a session that
exits 0: `_require_passing_verdict` (`src/aet/cli/orchestrator.py`) finds a
failing, missing or malformed verdict, prints `Gate fail-closed` and returns
False. That path records no signature and no tail. Triage then finds
"insufficient evidence", falls back to the default action for `environment`,
and requeues. The breaker never counts the failure, and no other cap exists.

Run telemetry from three client projects showed the cost. One project had five
tasks requeued 112, 41, 30, 24 and 12 times after gate failures: 230 attempts,
about $107 and 6.4 hours of stage time. Four loops ended only when the operator
stopped the run. Two other projects had the same unbounded loop on provider
errors before ADR-065.

Two inputs feed the loop. `aet gate submit --stage review` runs the
boundary-contract and identity-conflation lenses before it writes a verdict; a
tripped lens refuses both `pass` and `fail`, so the session exits 0 with no
verdict, and the one recovery session meets the same refusal. The lenses also
read `AET_REPO_ROOT`, the main checkout, while the verdict attests to
`AET_WORKTREE`. And provider or host errors outside the ADR-065 patterns, a
bare `API Error: 529 Overloaded` and "computer went to sleep mid-response", are
classed `flaky` and requeued at once.

## Decision

1. **A gate failure records a failure signature.** Before
   `_require_passing_verdict` returns False, it records a countable entry on
   the task. The class follows the verdict state: a `fail` verdict is
   `design`; a missing, malformed or invalid verdict is `environment`. The
   signature is computed from the fixed key `gate:<kind>:<state>` and the
   stage, so repeated failures of one kind collide. The verdict detail and
   summary go into the tail preview for triage, not into the signature.
2. **Retries are bounded per run.** A task that fails five times in one run is
   quarantined, whatever its signatures or classes. The cap is a constant next
   to the breaker threshold. Throttled failures stop the run first (ADR-065)
   and canceled failures are not failures of the task, so neither counts.
3. **A tripped review lens writes a fail verdict.** `aet gate submit --stage
   review` writes a `fail` verdict that carries the lens findings, and exits
   non-zero with the remedy. The gate always finds a verdict to judge. A later
   `pass` submission, after the cause is fixed and the lenses clear, replaces
   it.
4. **The lenses read the task worktree.** The lens root and the changed paths
   come from the tree the verdict attests to (`AET_WORKTREE`), the same root
   that `_verdict_tree_root` already uses for the tree hash.
5. **Two more transient errors are classified.** A 529 with an `API Error` or
   `api_error_status` qualifier, or `529 Overloaded`, is `throttled`, as
   ADR-065 intends for an overloaded provider. "computer went to sleep
   mid-response" is `environment`: countable, so triage may requeue it and
   the breaker stops it after three.

## Consequences

- A gate failure reaches triage with evidence, and three identical gate
  failures quarantine the task.
- No task loops more than five times in a run. A loop whose signature changes
  each attempt is bounded too.
- A review that trips a lens leaves a verdict, so verdict recovery is no longer
  spent on it.
- The review lenses judge the code the task changed, not the root checkout.
- The `design` default action is quarantine. A gate `fail` whose triage
  session errors quarantines at once instead of requeueing.
- Run summaries still count a requeue as no failure; that telemetry defect is
  outside this decision.

## Alternatives Considered

- **Every gate failure is `design`.** Rejected: a one-off missing verdict would
  quarantine a task whose work may be correct.
- **Every gate failure is `environment`.** Rejected: a real `fail` verdict is a
  judgment on the work, and mislabelling it hides it from triage.
- **A configurable attempt cap.** Rejected for now: the breaker threshold is a
  constant, and no project has asked for a different cap.
- **Let `--verdict fail` bypass the lenses.** Rejected: a session that submits
  only `pass` would still leave no verdict.
- **A seventh failure class for host interruptions.** Rejected: it needs a
  taxonomy change for an event that `environment` and the breaker already
  bound.
