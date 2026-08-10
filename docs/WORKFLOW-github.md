# Engineer Workflow: GitHub Issues Backlog Projection

This document describes the engineer-facing loop when AET is configured to project the backlog into GitHub Issues. It assumes the repo uses `git-refs` storage (the default) and one GitHub projection.

AET is the only writer to GitHub Issues. Do not create, relabel, or close issues by hand. The only human decision in the loop is promoting a plan into the sprint.

## The loop

```
aet-pipeline-plan  →  docs/plans/foo.md (footer stage: plan-approved)

aet backlog add docs/plans/foo.md          "put it on the board"
  → creates issue #N, labeled by stage:
      plan-draft      → aet:draft
      plan-approved   → aet:backlog

aet sprint add docs/plans/foo.md           ← the human decision: "work on this"
  → AET computes the DAG and labels #N:
      blockers unmet    → aet:blocked
      no blockers       → aet:ready

aet run                                    (laptop or cloud — identical)
  → fetch refs/aet/* → queue derived from ledger → runs what AET marked ready
  → transitions relabel #N (aet:in-progress → aet:awaiting-merge)

aet ship → merge → record-merge
  → terminal ledger event + footer *Stage: merged*
  → closes #N
```

## Command reference

| Command | When to use | What it writes to GitHub |
|---|---|---|
| `aet backlog add <plan>` | A plan exists and should be visible on the board. | Creates one issue keyed by plan id; labels `aet:draft` or `aet:backlog`. |
| `aet sprint add <plan>` | You are choosing to work on an approved plan now. | Adds to the sprint; labels `aet:ready` or `aet:blocked`. No commit or push at intake. |
| `aet run` | The queue has ready work and you want the orchestrator to pick it up. | Updates labels as the task progresses (`aet:in-progress`, `aet:awaiting-merge`). |
| `aet ship` / `record-merge` | The branch is merged to `main`. | Records terminal closure and closes the issue. |

## Rules

- **One plan, one issue.** Issues are identified by plan id, not title. Running `aet backlog add` twice finds the existing issue and creates no duplicate.
- **`aet:ready` is computed, not asserted.** AET sets it only when `blocked_by` is satisfied. Do not relabel issues by hand.
- **Status travels.** Every status-writing command commits and pushes the plan file. After a `git pull`, `aet run` selects the same work in any clone.
- **Projection failures are warnings, not blockers.** If `gh` is missing, unauthenticated, or GitHub is unreachable, the command still succeeds and the ledger still writes. Run `aet reconcile` to inspect and repair drift.
- **Do not write to GitHub by hand.** Filing, relabeling, or closing issues outside AET produces drift that `aet reconcile` will report.

## What the issue labels mean

| Label | Meaning |
|---|---|
| `aet:draft` | On the board, still being planned. |
| `aet:backlog` | On the board, approved, not yet scheduled. |
| `aet:ready` | The orchestrator may run this; blockers are satisfied. |
| `aet:blocked` | Scheduled, but blockers are not yet terminal. |
| `aet:planned` | In the sprint, not yet released to run. |
| `aet:in-progress` | Being executed. |
| `aet:awaiting-merge` | Done, pending closure. |
| `aet:failed` / `aet:quarantined` | Runtime outcome. |
| *(issue closed)* | `merged` or `abandoned`. |

## See also

- PRD: `docs/prds/github-issues-backlog-projection-prd.md`
- ADR-032: GitHub Issues Is a Projection, Not a Backend
- ADR-033: Projections Fail Open; Storage Fails Closed
- ADR-034: Settled-ness Is Derived from Versioned Plan Data
