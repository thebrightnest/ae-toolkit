---
subject: task-deletion
amends: [55]
---

# Absence Is Not a Fact

## Status

Accepted (2026-08-17). Amends ADR-055 (Settled-ness Lives in a Commutative
Provenance Ledger That Travels as Pushed Git Refs). Implements requirement R-8
of the `deletion-is-an-assertion` PRD
(`docs/prds/deletion-is-an-assertion-prd.md`).

## Context

ADR-055 made the live task set travel as forced, best-effort pushes of
`refs/aet/*`. What it did not settle was how a task *leaves* that set. The first
implementation encoded "not live" as the *absence* of `refs/aet/tasks/<id>`.
Absence replicates poorly: a wildcard push creates and updates refs but never
removes a remote ref whose local counterpart is gone, and a fetch learns only
what the remote advertises. A ref deleted on one clone survives on every other
clone, so a task sealed on machine A stayed live on machine B until the deletion
was delivered by hand.

Three sequential fixes treated this as a delivery bug:

1. `cmd_transition` was made to push after writing state.
2. The push refspec was forced so updates to blob refs were not rejected.
3. `save()` and `seal()` began tracking `_deleted_refs` and pushing explicit
   `:refs/aet/tasks/<id>` refspecs so the sealing machine could delete the ref
   on origin.

Each fix improved the symptoms but left correctness depending on a deletion
reaching every clone. The proposed hardening — `git fetch --prune` — was the
natural next step, and it is unsafe.

## Decision

1. **A task leaves the board by assertion, not by absence.** Sealing a task
   writes a durable per-task tombstone at `refs/aet/sealed/<id>`. The tombstone
   is data, not the absence of data. `load()` treats any task with a tombstone
   as no longer live and reaps the local task ref as housekeeping, so clones
   converge by reading without requiring any deletion to travel.
2. **Fetch never prunes.** A task created locally and not yet pushed is
   indistinguishable from a task deleted upstream, so `--prune` would destroy
   offline or never-pushed work. The board must survive a read in every
   posture, including one that never pushes.
3. **The `_deleted_refs` push is housekeeping, not correctness.** The explicit
   deletion refspecs pushed by `save()` and `seal()` stop the remote ref set
   growing without bound and help clones that never see the tombstone, but no
   load path depends on them. They must not be removed under the mistaken
   impression that tombstones make them redundant.
4. **Tombstones are per-task and additive.** A shared list would reintroduce the
   non-commutative set chain ADR-055 rejected. Two clones sealing different
   tasks merge by the union of their tombstones, regardless of order.
5. **A tombstone for an unknown task is inert.** A fresh clone fetching a year
   of sealed history must start cleanly; tombstones for tasks it has never seen
   are simply ignored.

This amends ADR-055's replication model: the live set still travels as pushed
`refs/aet/*`, but what travels is an *assertion* of removal (the tombstone), not
the removal itself. The rest of ADR-055 — the ledger as settled-ness authority,
the forced refspec, best-effort vs mandatory pushes — is unchanged.

## Consequences

- **Easier:** A task sealed on one clone disappears from every other clone at
  the next read, with no manual ref surgery and no pruning fetch.
- **Easier:** Offline-created tasks and never-pushing postures survive reads
  unchanged.
- **Easier:** Two machines sealing different tasks cannot conflict; their
  tombstones commute.
- **Harder:** The remote ref set accumulates tombstones. They are cheap and
  settle history already holds the durable record, so keeping them forever is
  the simplest policy; an expiry policy would require knowing every clone has
  seen every tombstone, which is not knowable.
- **Neutral:** The `_deleted_refs` push remains useful housekeeping and stays in
  place, but its role is documented so it is not mistaken for redundant.

## Why `--prune` Is Rejected

The reproduction that rejects `git fetch --prune` for this namespace:

```bash
# 1. Create and push one task.
aet sprint add docs/plans/pushed-task.md
aet state transition pushed-task ready in_progress
# (push lands)

# 2. Create a second task, but do not push it.
aet sprint add docs/plans/local-only-task.md

# 3. Run the pruning fetch that looks like the obvious hardening.
git fetch --prune origin '+refs/aet/*:refs/aet/*'
 - [deleted]         (none)     -> refs/aet/tasks/local-only-task
```

Git deleted `local-only-task` because the remote did not advertise it. To git,
"local ref the remote does not advertise" is a single case: it cannot tell the
difference between a task that was deleted upstream and a task that was created
locally and not yet pushed. Under ADR-055 pushes are best-effort except at
closure, and the shadow posture never pushes at all, so the second case is
normal operation. A read must not destroy work in either case.

## Alternatives Considered

1. **`fetch --prune`** — Rejected on the reproduction above. It makes the board
   unsafe to read.
2. **Track unpushed refs and exempt them from pruning** — Rejected. More state,
   per-clone, and fails the same way the old scheme failed: bookkeeping must
   survive. A tombstone is an ordinary ref that replicates by the same mechanism
   as every other ref.
3. **A single shared `refs/aet/meta/sealed` list** — Rejected. Reintroduces the
   non-commutative set chain ADR-055 removed; two machines sealing different
   tasks would clobber each other.
4. **Keep the task ref and mark the blob terminal** — Rejected. Every clone
   would carry every task forever; the namespace would grow without bound.
5. **Revert the landed `_deleted_refs` push** — Rejected. It is still valuable
   housekeeping: it bounds remote growth and gives clones that never fetch the
   tombstone the old deletion behaviour. The change is to demote its role, not
   remove it.
