---
subject: settled-ness
---

# Settled-ness Is Derived from Versioned Plan Data

## Status

Accepted. Revises ADR-013 (Work Queue Is an Ephemeral Sprint Board, Plans Are the Source of Truth).

## Context

ADR-013 decision 3 states that `.agents/work-history.jsonl` "remains an optional, gitignored execution log… It is not used to determine whether a task is closed." At the same time, `aet-work/bin/init-queue` contained logic that derived settled-ness from the history log:

```python
settled_files = {t.get("plan_file") for t in history if t.get("plan_file")}
settled_ids = {t.get("id") for t in history if t.get("id")}
```

This contradiction had no visible effect while one machine held both the gitignored history and the plans, but it becomes immediate as soon as a second clone or teammate lacks the same local history file. A clone without the history would treat previously settled work as live, and a projection would mirror finished tasks back onto the board.

The PRD resolves the contradiction by making `status` a required, validated plan frontmatter field over the canonical lifecycle. A plan with a terminal `status` (`merged` or `abandoned`) is settled; a plan with no `status` field is grandfathered as settled because the `status` field postdates the legacy corpus.

## Decision

Settled-ness is determined from **committed plan data**, never from the gitignored history log.

1. **Plan `status` is the authoritative liveness signal.** A plan is live when it has a `status` field and that status is not terminal. A plan is settled when its `status` is `merged` or `abandoned`, or when it has no `status` field at all (legacy grandfathering).
2. **`init-queue` and related commands read plan status, not history, to decide settled-ness.** `.agents/work-history.jsonl` may still be written for reporting, but it is not consulted for scheduling or projection decisions.
3. **Status writes are committed and pushed.** Every command that advances `status` (`aet backlog add`, `aet sprint add`, `record-merge`) commits the plan file and pushes it, so the settled signal travels with the repo.
4. **The queue remains an ephemeral cache.** It is derived from committed plan status on demand and is not a source of truth.

## Consequences

- **Easier:** A second clone or environment sees the same live/settled partition after a `git pull`, with no dependency on a local-only history file.
- **Easier:** Projections mirror only genuinely live work, because they derive liveness from the same committed plan status.
- **Easier:** ADR-013 decision 3 becomes true rather than aspirational.
- **Harder:** Every plan created from here must carry a valid `status` field. Intake and plan templates must be updated to write and validate it.
- **Harder:** Closure now requires a pushed commit of the plan file. A push failure leaves the local commit intact but must be surfaced and retried.

## Relation to ADR-013

ADR-013 established that plan files are the durable source of truth and that the history log is not authoritative for closure. This ADR realizes that principle by binding settled-ness to a versioned field in the plan file itself. The queue remains ephemeral; only the signal it derives from changes.

## Alternatives Considered

1. **Keep history-derived settled-ness and commit `work-history.jsonl`.** Rejected: it would make a gitignored execution log part of the shared truth, violating ADR-013 and adding runtime noise to the working tree.
2. **Derive settled-ness from git ancestry alone.** Rejected: squash merges and deleted branches make ancestry a lossy signal, and it cannot distinguish `merged` from `abandoned`.
3. **Add a separate `settled` file in `docs/plans/`.** Rejected: it fragments the source of truth. The plan file already carries `status`; duplicating it adds a new surface to keep consistent.
