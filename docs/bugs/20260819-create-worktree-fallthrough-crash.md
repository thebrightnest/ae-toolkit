# Bug Report: create_worktree crashes instead of halting when a conflicting worktree survives removal

## Metadata

- **Reported:** 2026-08-19
- **Severity:** high
- **Status:** resolved

## Symptoms

`aet work run-one` (and `run`) dies with a raw traceback instead of halting cleanly:

```
fatal: '<repo>/.worktrees/task-1' already exists
subprocess.CalledProcessError: Command '['git', '-C', '<repo>', 'worktree', 'add',
  '<repo>/.worktrees/task-1', 'task-1']' returned non-zero exit status 128.
```

Raised at `src/aet/worktree.py:139`. No caller wrapped `create_worktree`, so the
traceback escaped `run_single`/`main` with no telemetry record and no queue state
update.

## Reproduction Steps

1. Create a worktree for a task: `create_worktree(repo, "task-1")`.
2. Commit a change to a tracked file on the task branch inside that worktree.
3. Advance `origin/main` with a *conflicting* change to the same file.
4. Call `create_worktree(repo, "task-1")` again.

Observed: `CalledProcessError` at `worktree.py:139`. Reproduced reliably in a
scratch repo before the fix.

## Root Cause

The original report claimed `worktree add` ran "unconditionally". It does not —
`worktree.py:62-102` handles an existing worktree and returns on every branch but
one.

The wrong assumption is in the in-place refresh path (`worktree.py:92-95`): on
rebase conflict it aborted the rebase, called `remove_worktree(...)`, and **discarded
the return value**, then fell through to the rebuild path with the comment
"Fall through to recreate the worktree from the current base."

But `remove_worktree` (`worktree.py:192-209`) deliberately *refuses* to delete a
worktree holding non-deferred changes — which is exactly the state after a
conflicting rebase on a branch with real work. The directory therefore survived, and
the rebuild path's `git worktree add` hit an existing directory and died. Lines 161
and 167 carried the same exposure via the same fall-through; 139 is simply the branch
reached when the task branch has local commits.

Existing tests missed it because `test_refresh_conflict_rebuilds_branch_from_base`
covers the *other* conflict path — the one entered when `.worktrees/<id>` does not
exist — where deleting and rebuilding the branch from base is the intended behavior.
No test exercised a conflict against an already-materialised worktree.

Scope note: the blast radius in the original report ("any task with an existing
worktree crashes") was overstated. Four conditions must coincide: base advanced,
worktree clean, rebase conflicts, and the branch holds non-deferred changes.

## Fix Summary

- **Files modified:** `src/aet/worktree.py`, `src/aet/cli/orchestrator.py`,
  `tests/worktree/test_worktree.py`
- **Key change:** honour `remove_worktree`'s refusal — raise a new
  `WorktreeBlockedError` instead of falling through into an impossible rebuild.
- **Side effects:** three orchestrator call sites now halt cleanly on that error:
  the batch spawn loop marks the task failed and stops spawning; `run_single`'s
  `run_task` path exits 4; the run-one queued-task path writes a failure run summary
  and exits 4. Guarding the `worktree add` calls with a pre-existence check was
  rejected — it would convert the crash into silently discarded work.

## Regression Test

`tests/worktree/test_worktree.py::TestCreateWorktree::test_conflicting_refresh_halts_instead_of_crashing`
— builds the four-condition state, asserts `WorktreeBlockedError` is raised, and
asserts the worktree directory and the task branch SHA both survive.

## Validation

- [x] Reproduction steps no longer trigger the bug (clean halt; worktree and commit intact)
- [x] Existing test suite passes with no new failures: `tests/worktree
      tests/orchestrator tests/gate` → 333 passed, 5 subtests passed, 0 failed
      (run with the project venv interpreter; a bare `python3` run reports three
      spurious `TestRenderTaskPlan` failures from missing dependencies)
- [x] No regressions observed in related functionality

## Lessons Learned

- **Pattern:** a refusal signal returned as a bool was discarded, and the code
  proceeded on an assumption the callee had just declined to satisfy.
- **Prevention:** treat any "refuses when unsafe" helper as raising-or-checked at
  every call site; never `# fall through to recreate` past a guard that can decline.
- **Reference:** `src/aet/worktree.py` `WorktreeBlockedError`.
