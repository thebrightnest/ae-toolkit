---
subject: merge-evidence
amends: [11]
---

# Merge Evidence Is Recorded, Not Inferred from Ancestry

## Status

Accepted (2026-08-22). Amends ADR-011 (Forward-Only Deterministic Work State).
Motivated by the defect recorded in
`content/bugs/2026-08-22-0130-aet-empty-branch-derives-as-merged.md` and its
reproduction in the accompanying `-findings.md`.

## Context

ADR-011 decision 3 says git is consulted once, at write time, and that the merge
transition "resolves and records the real merge commit". It does not define what
makes a resolved commit *real*. The implementation filled that gap with branch
ancestry: if the branch is an ancestor of the integration branch, it is merged.

Ancestry is not merge evidence. A task branch created from the trunk tip and
never committed to is trivially an ancestor of its own base, so it satisfies the
same test a genuinely merged branch does. The two cases are indistinguishable to
every check in `aet_state.py`:

- `derive_status` returns `merged` for a zero-commit branch, with `merge_commit`
  still `None`.
- `resolve_merge_commit` resolves that branch's tip — which is the trunk tip —
  as its merge commit, with strategy `regular`. Positive evidence is
  manufactured out of the absence of work.
- `validate_transition` and the `_apply_transition` repair guard admit the
  transition on the same test.

Measured consequence: `aet state heal --apply` seals a task that wrote nothing as
`merged`, with a fabricated `merge_commit`, whenever the task is stored
`awaiting_merge` — the exact state a worker reaches when it declares completion
without committing. A merged record satisfies blockers for dependent tasks, so
one bad heal dispatches a dependency chain against code that does not exist.

No pure-git test separates the two cases. Both leave the branch tip an ancestor
of the trunk with zero commits ahead of it — a merged branch has nothing ahead
*because* its commits are in the trunk. The proposed guard in the original bug
report (`rev-list --count <trunk>..<branch> > 0`) measures 0 for both and would
reclassify every merged task as unmerged. The discriminator cannot be recovered
from git after the fact; it has to be recorded when the branch is created.

## Decision

1. **A branch's origin is recorded, not reconstructed.** Creating a task branch
   or worktree records `base_commit` on the task record: the commit the branch
   was created at. It is written once, by the code that creates the branch, and
   never recomputed.

2. **Merge evidence is a commit the task authored.** A branch tip counts as
   merge evidence only when it differs from that task's `base_commit`. A branch
   whose tip is still its base has produced nothing, and nothing it has
   produced can be on the trunk.

3. **`resolve_merge_commit` returns nothing for a branch that carries no work.**
   Resolution may not report a commit the task did not author. A branch sitting
   at its base has no merge commit, and the absence is reported as absence, not
   as the base commit.

4. **Absent evidence fails closed.** A task record with no `base_commit` — one
   written before this ADR, or by a path that failed to record it — derives to
   its non-terminal state, never to `merged`. Consistent with ADR-011 decision 4
   and with ADR-059: the absence of a recorded origin is not evidence that a
   merge happened.

5. **Reconciliation obeys the same contract as the write path.** `audit`,
   `heal`, and `reset` are the paths that consult git after the fact, and they
   apply this evidence rule unchanged. Repair mode bypasses lifecycle legality;
   it does not bypass evidence.

## Consequences

- **Easier:** a task that never committed cannot be recorded as shipped. The
  failure mode that produced the `e37-01` and `e40-07` incidents becomes
  structurally unreachable rather than guarded by operator discipline.
- **Easier:** `merge_commit` means something. A recorded merge commit is a
  commit the task authored, so downstream gates reading the record are reading
  evidence rather than a coincidence of ancestry.
- **Harder:** branch creation gains a mandatory write. A path that creates a
  task branch without recording `base_commit` produces a task that can never
  derive `merged` — loud and safe, but it must be found and fixed rather than
  tolerated.
- **Harder:** task records written before this ADR have no `base_commit` and
  will not auto-heal to `merged` from branch ancestry. They are closed by
  recording the merge commit explicitly —
  `aet state record-merge --merge-commit <sha>` — which passes positive
  evidence and is unaffected by decision 3. Note that plain `aet ship close`
  is *not* a substitute: it resolves through the same ancestry path this ADR
  closes, so for a record with no `base_commit` it falls back to the squash
  and diff paths, which match on content the task actually produced, and
  reports no match when neither applies.
- Amends ADR-011 by defining the evidence its decision 3 requires. It does not
  reopen derive-on-read: reads still trust the record, and this rule binds the
  write and reconciliation paths only.

## Alternatives Considered

1. **Require a recorded `merge_commit` as the sole evidence, with no
   `base_commit`.** Rejected as insufficient on its own: `resolve_merge_commit`
   manufactures the `merge_commit` from ancestry before it is recorded, so the
   rule would validate a value the same defect produced. It becomes sound only
   with decision 3, at which point `base_commit` is already needed to implement
   decision 3.
2. **Test whether the branch tip lies on the trunk's first-parent chain.** A
   branch that never committed sits on that chain; a `--no-ff` merged branch's
   tip does not. Correct for this repository's merge style and requires no new
   field, but it is wrong under fast-forward merges, silently couples state
   derivation to merge strategy, and walks history on every check.
3. **Compare committed content — treat a branch whose diff against the trunk is
   empty as unmerged.** Rejected: a genuinely merged branch also has an empty
   diff against the trunk. It reproduces the original error in a more expensive
   form.
4. **Refuse to derive `merged` at all; require every closure to go through
   `aet ship close`.** Rejected as too strict: reconciliation after an
   interrupted run is exactly what `audit`/`heal` exist for, and removing the
   capability trades a false-positive class for an unrecoverable-state class.
