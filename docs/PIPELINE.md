# AE Toolkit Pipeline and Work-Class Routing

This document defines the canonical pipeline stages and the work-class routing table used by the AE Toolkit skills.

## Work Classes

Every incoming request is classified into one of three work classes before any skill runs. `work_class` is also a stored, machine-readable task attribute: an optional plan-frontmatter key (`trivial`, `normal`, or `critical`) that `aet-work sync` validates and copies onto the task record, defaulting to `unclassified` when absent. The stored value is used by downstream readers (risk score, zero-review track record) rather than the routing decision itself.

| Class        | Trigger Examples                                | Pipeline                                                | Plans?           | QA Gate           |
| ------------ | ----------------------------------------------- | ------------------------------------------------------- | ---------------- | ----------------- |
| **Trivial**  | Fix typo, change button color, update copy      | Direct edit → `make validate` → ship                    | No               | Diff review only  |
| **Normal**   | Add email field, new API endpoint, simple modal | Quick plan (≤ 4 tasks) → implement → auto checks → ship | Yes, lightweight | Automated tests   |
| **Critical** | Add OAuth, migrate database, upgrade framework  | Full PRD → TDD → QA → review → `aet-verify` → ship      | Yes, full        | Observed evidence |

## Classification Decision Tree

1. **Is this a reproducible defect in existing code?**
   - Yes → **Bug** → `aet-bug-report`
2. **Does it touch auth, sessions, permissions, passwords, data models, migrations, infrastructure, or bump a dependency?**
   - Yes → **Critical** → Full PRD + TDD + QA + review + `aet-verify`
3. **Is it a copy change, color tweak, typo fix, or similarly small (≤ 3 files, ≤ 100 lines)?**
   - Yes → **Trivial** → Direct edit + `make validate` + ship
4. **Everything else** → **Normal** → Quick plan → implement → ship

## Symmetric Routing Guards

Entry-point skills enforce symmetric guards to prevent misrouted work:

- **`aet-plan` / `aet-pipeline-plan`**: If the user describes a reproducible defect, redirect to `aet-bug-report`.
- **`aet-bug-report`**: If the user describes a new capability or redesign, redirect to `aet-plan`.

## Canonical Stage State Machine

The `aet-work` orchestrator is the sole conductor of the pipeline. It reads each task's recorded `state` and `stage` from `.agents/work-queue.json`, spawns isolated agent sessions per stage group, and advances plans automatically. The plan footer `*Stage:*` is a human breadcrumb, not a scheduler input.

The stage sequence, skill bindings, evidence gates, and session grouping are **data, not engine code**. The canonical stage list is the workflow file: a repo-level `.agents/workflows/<name>.json` when present, otherwise the packaged `aet-work/workflows/software.json`; the plan frontmatter key `workflow:` selects the workflow by name (default `software`). A missing or invalid workflow file fails the run loudly at task start — there is no baked-in fallback sequence. The table below mirrors the packaged `software` workflow.

| Stage           | Skills                     | Evidence gate                                                  | Next stage    |
| --------------- | -------------------------- | -------------------------------------------------------------- | ------------- |
| `plan-approved` | `aet-tdd`, `aet-implement` | —                                                              | `implemented` |
| `implemented`   | `aet-qa`                   | passing `qa` verdict                                           | `qa-complete` |
| `qa-complete`   | `aet-review`               | passing `review` verdict                                       | `reviewed`    |
| `reviewed`      | `aet-cso`                  | passing `cso` verdict; skipped when `security_review: skipped` | `secure`      |
| `secure`        | `aet-sync-docs`            | passing `sync-docs` verdict; skipped when `docs_sync: skipped` | `synced`      |
| `synced`        | — (terminal, skill-less)   | —                                                              | `done`        |

At standard isolation the session groups are `[plan-approved, implemented]` → `[qa-complete]` → `[reviewed, secure]`. `aet-ship` merges after `synced`; `merged` is a queue state (see Legal Transitions), not a stage. The planning footers `plan-draft`, `prd-approved`, and `scope-validated` belong to the PRD pipeline (`aet-plan` / `aet-validate-scope`), upstream of the engine stage machine — they are not workflow stages.

## Recorded-Forward State

Workflow state is **recorded at transition time and trusted on read**.

- `aet-state transition` is the only writer of `tasks[].state`.
- `aet-work status`, `aet-work next`, and the orchestrator project the stored `state` directly and make **zero git calls** on the read path.
- `aet-state audit` reconciles stored state against git ground truth on demand; it is never invoked during normal operation.

## Legal Transitions

```text
sync:        ∅ → planned
sync:        planned → blocked            (pending_blockers > 0)
sync:        planned → ready              (pending_blockers == 0)
transition:  blocked → ready              (last blocker reached terminal)
transition:  ready → in_progress          (branch + worktree recorded)
transition:  in_progress.stage advances   (tdd → implement → qa → review → cso → sync-docs)
transition:  in_progress → awaiting_merge (pipeline exited 0; NOT terminal)
transition:  awaiting_merge → merged      (TERMINAL; merge_commit verified once)
transition:  any → abandoned (reason)     (TERMINAL)
transition:  in_progress → failed         (needs inspection; may re-enter)
```

Terminal states are `merged` and `abandoned`. Only terminal states satisfy blockers. `awaiting_merge` deliberately does **not** satisfy blockers.

## Intake Contract

Atomic plan files must carry a validated YAML frontmatter contract:

```yaml
---
id: { ticket-id }
size: S/M/L
blocked_by:
  - { blocker-id }
---
```

- `id` must match the filename stem and be unique within the PRD family.
- `blocked_by` is the authoritative dependency DAG; prose dependency sections are ignored by `aet-work sync`.
- `size` is the S/M/L complexity label.
- `stage` lives only in the task record, never in plan frontmatter.

`aet-work sync` validates every plan and fails closed on missing, duplicate, or mismatched IDs, unknown blockers, or invalid size values.

## Live / Settled Partition

`.agents/work-queue.json` holds only non-terminal tasks. When a task reaches a terminal state, the writer appends its final record plus history to `.agents/work-history.jsonl` and removes it from the live file atomically. The orchestrator, `status`, and `next` never load settled history for scheduling.

## Diff Budget for Bug Fixes

`aet-bug-report` enforces a diff budget to keep fixes proportional:

- **Budget**: ≤ 3 files and ≤ 100 lines
- **Exceeding the budget** requires explicit justification:
  - Why a smaller change is insufficient
  - Why the scope expansion is necessary to fix the root cause
- **Weak justification** → redirect to `aet-plan`; the issue likely requires redesign, not a targeted fix.
