# Idea: Do Per-Branch Verdicts Compose Across a Parallel Batch?

- **Status:** Parked (2026-08-27). Undecided by any accepted ADR, and it
  contests an assumption inside one.
- **Origin:** Surfaced while triaging
  `docs/bugs/20260827-ship-checks-the-ambient-checkout.md`. The bug's mechanical
  half — `aet ship merge` running its checks against the ambient checkout rather
  than the resolved task ref — is a conformance defect and stays in that report.
  This is the half that is not a defect.
- **Would-be artifact:** an ADR amending ADR-045, possibly with a small PRD.

## Summary

A parallel batch runs QA, review and security per branch. Each stage evaluates a
tree that no sibling's changes have reached. Nothing decides what those passes
say about the **union** of the branches, or where the union must be validated.

## Why it is not already decided

ADR-045 §1 states as settled background:

> in `pr-per-task` the forge serializes merges and each task is independent of
> its siblings' branches

The 2026-08-27 measurement contests the second clause. Fifteen merges from that
batch were compared, each merge's `merge-base(^1, ^2)` against its first parent:

- 14 of 15 show the feature branch rebased onto the trunk tip before merge.
- 1 does not: `nrc-02-hold-classification-plan`, which may simply have merged
  first in its group.

A rebased second parent is what `_rebase_independent_branch` produces. So in
those 14, `make validate` ran on the *merge result*, not on the branch in
isolation. The catch that makes serialized merges safe is the rebase inside the
gate — not branch independence.

That is a stronger property than the bug report first credited, and it is worth
recording: a cross-branch semantic break (a requirement anchor claimed twice, a
field made required that a sibling's test does not pass) **is** caught at merge
under serialized `aet ship merge`, provided the operator is on the branch.

## The open question

What does *not* compose is the per-branch pipeline verdict. QA, review and
security each attest to a tree the siblings never touched, and ADR-025 made a
verdict's `tree_hash` the record of exactly which tree it attests to. So the
evidence is honest about its own scope — but nothing states what that scope
implies for the batch, and nothing requires evidence for the union.

The practical cost: the catch happens at ship, after every expensive stage has
already run on each branch.

Candidate positions, none argued for here:

1. **Verdicts are per-branch and that is correct.** The gate's rebase is the
   composition point; document it and require serialized merges.
2. **The union needs its own evidence.** Something validates the integration
   result and writes a verdict for it, before the expensive per-branch stages
   are spent.
3. **`single-pr` integration mode already answers it** (ADR-045 §2), and the
   question is really whether `pr-per-task` should adopt part of that model.

## Related

- `docs/bugs/20260827-ship-checks-the-ambient-checkout.md` — the mechanical half,
  including the withdrawn interim guard and why the structural fix
  (gating inside `_merge_into_target`'s worktree) preserves checkout
  independence.
- ADR-045 (epic integration branch and task integration mode) — the assumption
  contested here.
- ADR-025 (validation freshness / verdict provenance) — `tree_hash` is the atom
  that makes "which tree did this attest to?" answerable at all.
- ADR-019 (structured gate evidence) — the fail-closed verdict contract.
