# Idea: Gate Evidence Does Not Travel With the Task

- **Status:** Undecided (2026-08-28). Needs a decision before it needs code.
- **Origin:** Surfaced as the reason ADR-070 deliberately bounded its own fix.
  Widening `aet ship gate` to check every required verdict broke every happy-path
  test, and the tests were right.
- **Would-be artifact:** an ADR, and a PRD if the answer moves storage.

## Summary

A verdict is written to `~/.aet/reports/<project-slug>/<task-id>/<kind>.json`
(`evidence.DEFAULT_REPORTS_DIR`, overridable by `AET_REPORTS_DIR`). That location
is per-machine, outside the repository, and never pushed. Nothing replicates it.

So the answer to "did this task pass review?" exists only on the machine that ran
the stage, and only until that directory is pruned. Every consumer of gate
evidence is therefore local by construction.

## What it already cost

ADR-070 makes `aet ship gate` satisfy the workflow's `verify` requirement with
the `verify` verdict. The principled version of that change checks every kind
`gate.required_evidence` returns, since the workflow already declares them and
`gate.check_task_evidence` already implements the check.

That version was abandoned: a task shipped from a different checkout than the one
that ran its pipeline would be refused for evidence that did exist, turning one
unsatisfiable gate into another. ADR-070 records the boundary and the reason, and
the boundary is a symptom of this hole rather than a design preference.

## Why it is not obviously decided

Three plausible homes, each with a real objection:

- **Keep it local, as now.** Cheap, and honest about the fact that verdicts are
  produced by a local run. But it permanently prevents any non-local consumer:
  ship from another checkout, a second reviewer, CI, or a projection.
- **Put it on the task record.** The record already replicates by fetch/push, and
  it already carries `failure_signatures` and `cost`. But ADR-055 keeps the
  record small, and verdicts carry summaries and finding lists that would grow it
  without bound.
- **Put it in `refs/aet/*` beside the record.** Replicates with the same
  transport, stays out of the working tree, and is content-addressed. But it adds
  a ref namespace and a retention question nobody has answered.

There is also a prior question: whether a verdict is a *fact about a tree* (in
which case `tree_hash` makes it portable and cacheable) or a *fact about a run*
(in which case it is local by nature and ship should never re-check it).

## Trigger to decide

Any of: a request to ship or audit from a machine that did not run the pipeline;
a projection that wants to publish verdicts; a second attempt to widen a gate to
check evidence it cannot see.
