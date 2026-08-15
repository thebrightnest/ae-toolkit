# Bug: git-refs backend leaves stale task refs on origin and across clones

## Summary

When the git-refs backend is active, sealing or removing a task deletes the
local `refs/aet/tasks/<id>` ref, but the deletion is **not propagated to
origin**. Additionally, `backend.fetch()` uses a force refspec that overwrites
local refs but never **prunes** refs that have been deleted on origin. The
combination means:

- A sealed task can reappear as `in_progress` / `awaiting_merge` on every other
  clone forever.
- Running `aet status` on any stale clone silently resurrects the task in that
  clone and, if anything pushes from that clone, resurrects it on origin too.

This report documents the root causes, the fixes already landed on `main`, and
a step-by-step checklist to clean up a clone that still sees stale refs.

## Environment

- ae-toolkit source repo at current `main` (2026-08-15)
- Backend: `git-refs` (`task_backend: git-refs` in `.agents/aet-config.json`)
- Remote: `origin` hosting `refs/aet/*`
- Affected task in this incident: `owb-01-spec-travels-in-task-record`

## Reproduction

```bash
# 1. Machine A seals a task (e.g. aet ship close / record-merge).
#    Local ref refs/aet/tasks/<id> is deleted, history is appended.
# 2. Machine B runs:
aet status

# Observed:
# - Machine B reports the task as in_progress / awaiting_merge again.
# - git ls-remote origin refs/aet/tasks/<id> shows the ref still on origin.
# - git show-ref on Machine B shows the ref locally.
```

## Root causes

There are **two** independent but overlapping problems.

### Problem 1: `push()` does not send deletion refspecs

`backend.push()` only sent `+refs/aet/*`. That refspec updates refs that still
exist locally; it does **not** delete refs on origin that no longer exist
locally. So after `backend.seal()` deleted the local task ref, origin kept the
old blob forever.

Affected code paths:

- `backend.save()` prunes refs for tasks no longer in the live queue, but did
  not track them for deletion.
- `backend.seal()` deletes the ref directly via `git update-ref -d` and was not
  tracked at all.

### Problem 2: `fetch()` does not prune deleted remote refs

`backend.fetch()` runs:

```python
self._git("fetch", "origin", "+refs/aet/*:refs/aet/*")
```

The leading `+` forces local refs to match remote ones, but git only updates
refs that are advertised by the remote. If a ref was deleted on origin, the
remote no longer advertises it, so the local copy is left untouched. Every
clone therefore hoards every ref it has ever seen.

## Fixes already on main

Two commits were pushed to `main`:

1. `6084a56` — `fix(git-refs): push deleted task refs on seal`
   - Tracks refs pruned by `save()` in `backend._deleted_refs`.
   - After the main namespace push, sends explicit deletion refspecs
     `:refs/aet/tasks/<id>` for anything in `_deleted_refs`.

2. `6736865` — `fix(git-refs): seal() must also push deleted task refs`
   - Adds the deleted ref to `_deleted_refs` inside `backend.seal()` so the
     terminal-closure path also propagates deletions.
   - Adds `test_seal_deletes_task_ref_on_remote`.

These fixes stop the leak going forward: every seal or save that removes a task
will now delete the ref on origin. They do **not**, by themselves, remove refs
already stranded on local clones.

## Checklist for cleaning Machine B

Run all of these on the other machine in order.

### 1. Ensure the clone is on the fixed code

```bash
cd /path/to/ae-toolkit
git fetch origin
git checkout main
git pull origin main

# Verify the fixes are present
git log --oneline -5 main
# expect 6736865 at or near the top

grep -n "_deleted_refs.add" src/aet/backends/git_refs_backend.py
# expect two matches: one in save() and one in seal()
```

### 2. Ensure `aet` is running from the repo source

```bash
python -c "import aet.backends.git_refs_backend as m; print(m.__file__)"
# should print something ending in src/aet/backends/git_refs_backend.py
```

If it points elsewhere (e.g. site-packages), reinstall editable:

```bash
pip install -e .
```

### 3. Inspect the current stale state

```bash
git show-ref | grep refs/aet/tasks/owb-01
git ls-remote origin refs/aet/tasks/owb-01-spec-travels-in-task-record
aet status
```

### 4. Delete the stale ref locally and on origin

```bash
# Delete local ref
git update-ref -d refs/aet/tasks/owb-01-spec-travels-in-task-record

# Delete remote ref
git push origin :refs/aet/tasks/owb-01-spec-travels-in-task-record

# Verify
git show-ref | grep refs/aet/tasks/owb-01 || echo "local gone"
git ls-remote origin refs/aet/tasks/owb-01-spec-travels-in-task-record || echo "remote gone"
```

### 5. Verify the queue is clean

```bash
aet status
```

Expected:

- `owb-01-spec-travels-in-task-record` is **not** in the live queue.
- `owb-04-plan-tooling-and-board-review`, `owb-05-board-is-open-work`, and
  `owb-13-prd-integration-branch` no longer list `owb-01` as a blocker.
- No stale worktree warnings.

### 6. Prune other stale remote-tracking refs (optional)

```bash
git remote prune origin
```

## Verification of the fix

From a clean clone, the new behavior can be verified with the regression tests:

```bash
python -m pytest tests/backends/test_git_refs_sync.py -q
```

Both of these tests must pass:

- `test_push_deletes_sealed_task_refs_on_remote`
- `test_seal_deletes_task_ref_on_remote`

## Follow-up improvements

The current fixes stop new leaks. Two optional hardenings remain:

1. **Make `backend.fetch()` prune deleted remote refs.**
   Change `src/aet/backends/git_refs_backend.py`:

   ```python
   self._git("fetch", "--prune", "origin", _AET_FETCH_REFSPEC)
   ```

   This would make every `aet status` clean up local refs already deleted on
   origin. The trade-off is that a local-only ref created while offline would
   also be pruned on the next fetch. In normal AET use every mutating command
   pushes immediately, so this is likely safe.

2. **One-shot cleanup command.**
   Add `aet state purge-merged-refs` or similar for explicit house-keeping
   across clones without changing default fetch behavior.

## Related files

- `src/aet/backends/git_refs_backend.py`
- `tests/backends/test_git_refs_sync.py`
- `docs/bugs/2026-08-14-aet-state-transition-does-not-push-refs.md`
