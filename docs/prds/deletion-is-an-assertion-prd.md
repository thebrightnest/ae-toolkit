# PRD: Deletion Is an Assertion, Not an Absence

## Overview

The `git-refs` backend encodes "this task is no longer live" as the *absence* of
`refs/aet/tasks/<id>`. Absence does not replicate. A refspec push creates and
updates refs but never removes one whose local counterpart is gone, and a fetch
learns only what the remote advertises — so a ref deleted anywhere survives
everywhere else. In this incident `owb-01` stayed live on one clone for hours
after being sealed on another, and `sst-01` did the same in the opposite
direction.

Two fixes have landed (`6084a56`, `6736865`): `save()` and `seal()` now record
removed refs and `push()` sends explicit `:refs/aet/tasks/<id>` refspecs. They
stop the leak **from the machine that seals**. They cannot help a clone that
already holds a stale ref, and they leave correctness depending on a delete
reaching every clone — a delivery guarantee the design does not have.

The proposed hardening — `fetch --prune` — is unsafe, and measurably so. A
locally created task whose push did not land is indistinguishable from a task
deleted upstream, so pruning destroys it:

```
$ git fetch --prune origin '+refs/aet/*:refs/aet/*'
 - [deleted]         (none)     -> refs/aet/tasks/offline-task
```

ADR-055 makes pushes best-effort except at closure, and the shadow posture
(open-work-board PRD R-16) forbids pushing at all — under which `--prune` would
delete the entire board on the first fetch.

This PRD removes the class instead of patching its symptoms: **a task leaves the
board because something says so, never because something is missing.**

## Goals

- A sealed task disappears from every clone without any deletion having to
  arrive anywhere.
- A task created offline, or in a posture that never pushes, is never destroyed
  by a read.
- Two machines sealing different tasks never conflict.
- A clone stranded by the old scheme can be reconciled by one command.

## Non-Goals

- **`fetch --prune`.** Rejected on the evidence above, not on taste. The
  reproduction is in the technical notes so this does not get re-proposed.
- **Reverting `6084a56` / `6736865`.** They stay. Under tombstones, deleting the
  remote ref becomes housekeeping rather than the correctness mechanism, which
  is exactly the demotion that makes them safe to keep.
- **Changing what `seal` means to `aet-state`.** The forward-only state model and
  settled history are unchanged; only the replication of "no longer live" moves.
- **A ref-count budget.** Tombstones accumulate; if that ever matters it is a
  separate measured decision, as ADR-046 did for plan size.

## Requirements

- **R-1**: Sealing a task writes a durable per-task tombstone that says the task
  left the board. The tombstone is data, not the absence of data.
- **R-2**: Tombstones are per-task and additive, never a shared list. Two clones
  sealing different tasks must merge without conflict — the commutativity
  ADR-055 required when it rejected a chained `content_hash`.
- **R-3**: `load()` treats a tombstoned task as not live, and reaps the local
  task ref as local housekeeping. A clone converges by *reading*, with no
  deletion having had to reach it.
- **R-4**: `fetch()` never prunes. A task created locally and not yet pushed
  survives every read, in every posture, including one that never pushes.
- **R-5**: Correctness does not depend on a deletion being delivered. A push that
  fails, a clone that never fetched, or a posture that never pushes may leave a
  stale *ref*, but must not produce a stale *board*.
- **R-6**: One command reconciles a clone stranded by the pre-tombstone scheme,
  replacing the manual `update-ref -d` / `push :ref` checklist. It reports what
  it would remove before removing it.
- **R-7**: A tombstone for a task this clone has never seen is inert, not an
  error — a fresh clone fetching a year of tombstones must start cleanly.
- **R-8**: An ADR records the principle and amends ADR-055: absence is not a
  fact; a task leaves the board by assertion.

## User Stories

- As an operator with two machines, I want a task I sealed on one to be gone
  from the other the next time I look, without running anything by hand
  (satisfies: R-1, R-3).
- As an operator working offline, I want a task I just created to still be there
  after the next command (satisfies: R-4, R-5).
- As an operator on a client project that must never push, I want the board to
  survive reads (satisfies: R-4).
- As an operator whose clone is already stale, I want one command rather than a
  checklist (satisfies: R-6).
- As a maintainer, I want two machines sealing different tasks to merge cleanly
  (satisfies: R-2).

## Acceptance Criteria

- [ ] Machine A seals a task; machine B sees it gone after a plain `aet status`,
      with no pruning fetch and no manual ref surgery (satisfies: R-1, R-3)
- [ ] A task created while the push fails survives an arbitrary number of
      subsequent reads (satisfies: R-4, R-5)
- [ ] With pushing disabled entirely, the board is unchanged after a fetch
      (satisfies: R-4)
- [ ] Two clones seal different tasks offline; after both push, each sees both
      sealed and neither resurrects (satisfies: R-2)
- [ ] The reconcile command lists the stranded refs, and removes them only when
      asked (satisfies: R-6)
- [ ] A clone fetching a tombstone for an unknown task loads cleanly
      (satisfies: R-7)
- [ ] `git ls-remote origin 'refs/aet/*'` and the local ref set may differ
      without the boards differing (satisfies: R-5)

## Technical Notes

**The reproduction that rejects `--prune`**, so it is not re-litigated: create a
task, push it; create a second task, do not push; `git fetch --prune origin
'+refs/aet/*:refs/aet/*'` deletes the second. Output above. The two cases are
indistinguishable to git because both are "local ref the remote does not
advertise".

**Why tombstones rather than tracking unpushed refs.** The alternative is to
record which local refs have never been pushed and exempt them from pruning.
That is more state, it is per-clone, and it fails the same way the current design
fails: it depends on bookkeeping surviving. A tombstone is an ordinary ref that
replicates by the same mechanism as every other ref, and it makes the sealed
fact idempotent — receiving it twice is a no-op, which is the property ADR-055
built the whole store around.

**Why per-task and not a list.** A single `refs/aet/meta/sealed` blob holding all
sealed ids is one ref instead of many, and it is exactly the shape ADR-055
removed: "a chain over a set is non-commutative, so independent writers produced
irreconcilable conflicts by construction." Two machines sealing different tasks
would clobber each other.

**Deletion becomes housekeeping.** With R-3 reaping on read, the landed
`_deleted_refs` push already on main stops being load-bearing. It is still worth
keeping: it stops the remote ref set growing without bound, and a clone that
never fetches the tombstone still gets the old behaviour. The point is that
nothing *depends* on it any more.

**Interaction with the shadow posture** (open-work-board PRD R-15/R-16): a
posture that never pushes is single-machine by construction, so convergence is
moot — but R-4 is what stops a read from destroying its board. Any future change
to fetch must be checked against that mode.

**Scope of the incident, for the record.** `owb-01` was sealed on one clone and
stayed live on another until deleted by hand; `sst-01` went the other way. Both
were diagnosed as resurrection and both were the same missing replication of
absence.

## Open Questions

- **Where do tombstones live?** `refs/aet/sealed/<id>` pointing at the sealed
  record is the obvious shape, and it keeps the whole board under one fetched
  namespace. An alternative is to keep the task ref and mark the blob terminal,
  which needs no new namespace but makes every clone carry every task forever.
- **Do tombstones ever expire?** Settled history already holds the durable
  record, so a tombstone is only needed until every clone has seen it — which is
  not knowable. Keeping them forever is simplest and cheap; saying so explicitly
  is better than leaving it undecided.
- **Should `aet status` report divergence** between the local ref set and origin,
  now that R-5 makes them legitimately different? A quiet difference is what hid
  this incident for hours.
- **Does the reconcile command (R-6) also clean the remote**, or only the clone
  it runs on? Cleaning the remote from a stale clone is how `sst-01` came back.

## Divergence Summary

_Recorded: 2026-08-17 — Branch: dia-01-tombstones-replace-absence_

### Changed from plan

- **Files modified**: The tombstone logic fit entirely within `src/aet/backends/git_refs_backend.py` and `tests/backends/test_git_refs_sync.py`; the planned edits to `src/aet/backends/base.py` and `tests/backends/test_git_refs_parity.py` were not needed.

### Deferred

- **Merge to main and integration verification**: Remains for the `aet-ship` stage; no merge has been performed yet.

---

*Stage: synced*
*Next step: run `aet-ship`*
