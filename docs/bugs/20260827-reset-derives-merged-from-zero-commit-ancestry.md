# Bug Report: `aet state reset` seals a never-implemented task as `merged`

## Metadata

- **Reported:** 2026-08-27
- **Severity:** high — silently settles unimplemented work
- **Status:** open
- **Related:** ADR-064 (Merge Evidence Is Recorded, Not Inferred), which names
  the general principle this is an instance of.

## Symptoms

Three tasks whose agent sessions died before producing a single commit were
reported by `aet state audit` as derived `merged`, and `aet state reset`
dry-runs offered to apply it:

```
[dry-run] Would reset poh-01-re-ingest-an-inert-task-spec: failed -> merged
[dry-run] Would reset poh-02-verify-routing-key-and-work-class-gate-default: failed -> merged
[dry-run] Would reset poh-04-divergence-is-recorded-at-closure: failed -> merged
```

Nothing was merged. Nothing was written. Each branch had zero commits, each
worktree was clean, and each task's telemetry records `commits_created: 0` and
`files_modified: []`.

The command's own help reads "Recompute a task from git and blockers, reset to
**ready/blocked**, clear stale runtime fields" — so an operator reaching for it
to clear a failed task has no reason to expect a terminal state, and `--apply`
would have sealed three unimplemented tasks as done.

## Reproduction Steps

1. Admit a task and let its branch be created from the current trunk.
2. Have the agent session die before committing anything, so the branch tip
   equals its base commit.
3. Run `aet state audit`, or `aet state reset <task-id>`.

Observed: `derived: "merged"`, `discrepancy: true`, and a dry-run offering
`failed -> merged`. Expected: `ready` or `blocked` — the states the help text
names — because no merge occurred.

## Root Cause

The deriver treats ancestry as merge evidence. A branch with zero commits has a
tip that is trivially an ancestor of `origin/main`, because it *is* a commit on
`origin/main`. `git merge-base --is-ancestor <branch> origin/main` is true, and
the deriver reads that as "the branch landed".

The predicate cannot distinguish the two cases it must separate:

- a branch that diverged, was merged, and is now contained in the trunk, and
- a branch that never diverged at all.

Both are ancestors. Only the first is merged. This is precisely what ADR-064
means by ancestry not being merge evidence, and the zero-commit case is its
sharpest instance: there is no commit whose presence could be checked, so
ancestry is the *only* signal available and it is uninformative.

## Consequences

- An operator clearing failed tasks with the documented command settles them as
  merged instead. The work is not just lost — the board asserts it was done.
- `aet state heal`, which "applies safe fixes", derives the same value.
- The tasks' plans remain in the PRD's requirement coverage, so the settled
  records would credit requirements nothing implemented — the coverage
  `plan_validate` reads at intake.

## Why It Survived

The zero-commit case only arises when a session dies before its first commit.
In this instance that was caused by a separate failure — the `agy` adapter
timing out at ~300s with `num_turns: 1` on every attempt — so the two defects
are needed together to produce it.

## Workaround

`aet state transition <id> failed ready --reason "..."` states the target state
explicitly rather than deriving it, and validates legality. It is what was used
to clear the three tasks on 2026-08-27. For a task stuck `in_progress` the legal
path is `in_progress -> failed` first; `in_progress -> blocked` and
`in_progress -> ready` are both rejected.

## Fix Direction

Require positive merge evidence before deriving `merged`, per ADR-064: a
recorded `merge_commit`, or a recorded `base_commit` the branch can be shown to
have advanced beyond. A branch with no commits beyond its base has no evidence
either way and must derive to a non-terminal state.

Narrower and worth doing regardless: a branch whose commit count beyond
`origin/main` is zero can never have been merged *by this task*, so the
zero-commit case can be excluded from the `merged` derivation outright, without
waiting for base-commit recording to land.

Related: `docs/bugs/20260827-agy-adapter-stall-timeout.md` records the failure
that produces zero-commit branches in the first place.
