# Bug Report: worktree teardown refuses on committed work, so every successful task strands its worktree

## Metadata

- **Reported:** 2026-08-27
- **Severity:** medium
- **Status:** fixed 2026-08-27
- **Related plan:** `docs/plans/osd-03-worktree-teardown-visibility.md` (plan-approved) owns
  this code; its task 1 is the diagnosis recorded here.

## Symptoms

Every task in a run ends with a teardown warning naming a list of files:

```
⚠️  Worktree teardown failed for dep-03-…: .github/workflows/ci.yml,
    .github/workflows/deploy.yml, docs/ROADMAP.md, …
```

`git status --porcelain` is empty in the named worktree. The paths are the files
the branch changed, not uncommitted work. Observed on 2026-08-27 in a seven-task
batch: seven of seven worktrees stranded, every one clean.

## Reproduction Steps

1. Run any task to completion so its branch carries at least one commit touching
   a non-deferred path.
2. Let the orchestrator reach end-of-run teardown.

Observed: `teardown_worktree` returns `removed: False` with
`reason: "worktree has non-deferred changes"` and the branch's changed files as
obstructions. Expected: the worktree is removed, because the commits live on the
branch ref and survive removal.

## Root Cause

`_worktree_obstructions` (`src/aet/worktree.py:274-314`) unions two sets that
carry different risk:

- `git diff --name-only <base>..HEAD` — work already committed to the branch.
- `git status --porcelain --untracked-files=all` — uncommitted work.

`git worktree remove` does not touch branch refs, so committed work is not at
risk. The first set therefore protects nothing at teardown, and it is non-empty
for every task that did anything, which makes end-of-run teardown fail by
construction.

The diff half is not gratuitous. Its sibling predicate
`_worktree_has_non_deferred_changes` (`src/aet/worktree.py:198-212`) is diff-only
and serves `remove_worktree` (`:215`), which is called from the in-place refresh
path (`:113-116`). There, a surviving worktree is recreated and the branch
rebuilt from base, so refusing on committed work is correct — that refusal is the
fix recorded in `docs/bugs/20260819-create-worktree-fallthrough-crash.md`.

One risk model is applied to two callers whose risk differs.

## Consequences

- Worktrees accumulate: seven remained after the observed batch, removed by hand.
- `aet state heal` reports `No healable discrepancies found` while they remain,
  because stranded worktrees are outside its documented scope.
- The warning text names changed files, which reads as uncommitted work and
  invites a search for state that does not exist.

## Fix Direction

Give teardown its own predicate: uncommitted changes only, from
`git status --porcelain`. Leave `_worktree_has_non_deferred_changes` and
`remove_worktree` untouched so the refresh path keeps refusing on committed work.
Report the two conditions separately — a dirty tree names its files, an unmerged
branch says so in those words.

Rejected: passing `--force` to `git worktree remove`, which discards uncommitted
work and contradicts the 2026-08-19 fix.
