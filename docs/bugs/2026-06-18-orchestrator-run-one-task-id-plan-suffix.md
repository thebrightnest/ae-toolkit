# Bug Report: `run-one` task-id derivation assumes a `*-plan.md` filename

## Metadata

- **Reported:** 2026-06-18T16:53:21Z
- **Severity:** medium
- **Status:** fixed

## Symptoms

Running `aet-work run-one docs/plans/<name>.md` on a plan whose filename does **not**
end in `-plan.md` produces a worktree and branch whose name retains the `.md`
extension — e.g. `fods-01-record-merge.md` instead of `fods-01-record-merge`. This
yields ugly branch/worktree names (`.worktrees/fods-01-record-merge.md`,
branch `fods-01-record-merge.md`) and, in batch mode, can desynchronize the
orchestrator-derived id from the queue's task id.

Observed while shipping `fods-01` (plan `docs/plans/fods-01-record-merge.md`); worked
around by exporting `AET_TASK_ID=fods-01-record-merge`.

## Reproduction Steps

1. Reproduce the derivation directly:

   ```bash
   python3 -c "import os; print(os.path.basename('docs/plans/fods-01-record-merge.md').replace('-plan.md',''))"
   # -> fods-01-record-merge.md   (the .md is NOT stripped)
   python3 -c "import os; print(os.path.basename('docs/plans/foo-plan.md').replace('-plan.md',''))"
   # -> foo                        (correct, because it matched -plan.md)
   ```

2. Or end-to-end: `aet-work run-one docs/plans/fods-01-record-merge.md` **without**
   `AET_TASK_ID` → worktree `.worktrees/fods-01-record-merge.md`, branch
   `fods-01-record-merge.md`.

## Root Cause

`aet-work/bin/orchestrator:381`:

```python
task_id = os.environ.get("AET_TASK_ID") or os.path.basename(plan_file).replace("-plan.md", "")
```

`.replace("-plan.md", "")` only strips the suffix when the filename matches the
`*-plan.md` convention. For any other naming (e.g. `fods-01-record-merge.md`) the
substring is absent, so the `.md` extension survives into the task id.

- **Wrong assumption:** every plan filename ends in `-plan.md`.
- **Path:** `run_single()` → task-id derivation → `create_worktree(repo_root, task_id)`
  names the branch/worktree from the malformed id.
- **Batch mode is protected:** `run_batch` passes `AET_TASK_ID` (the queue task id) to
  the child, so the env-var branch wins. The defect manifests only in direct
  `run-one` on a non-`-plan.md` plan.
- **Why not caught:** no test exercises a non-`-plan.md` plan name.

## Fix Summary (applied)

- **Files modified:** `aet-work/bin/orchestrator` (1 file, 2 lines).
- **Key change:** derive the id with `os.path.splitext(os.path.basename(plan_file))[0]`
  and `removesuffix("-plan")`, so the id never carries an extension regardless of
  naming convention.
- **Risk:** low. **Diff budget:** within (≤3 files, ≤100 lines).

## Regression Test

Verified manually:

```bash
python3 -c "import os; base = os.path.splitext(os.path.basename('docs/plans/fods-01-record-merge.md'))[0]; print(base.removesuffix('-plan'))"
# -> fods-01-record-merge
python3 -c "import os; base = os.path.splitext(os.path.basename('docs/plans/foo-plan.md'))[0]; print(base.removesuffix('-plan'))"
# -> foo
```

## Validation

- [x] Reproduction steps no longer trigger the bug
- [x] Existing test suite passes with no new failures (`make validate`)
- [x] No regressions observed in related functionality

## Lessons Learned

- **Pattern:** convention baked into string munging (`replace`) instead of robust
  parsing (`splitext`).
- **Prevention:** derive ids by stripping the extension, not a hard-coded suffix;
  test id derivation across naming conventions.
- **Workaround:** pass `AET_TASK_ID` for plans not named `*-plan.md`.
