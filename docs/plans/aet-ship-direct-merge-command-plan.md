---
id: aet-ship-direct-merge-command-plan
size: M
status: in_progress
blocked_by: []
pipeline: standard
security_review: required
security_review_reason: touches branch mutation and git remotes, but no new auth/data paths
---

# Plan: aet-ship Direct Merge Command

## Context

Add an `aet ship merge` subcommand that merges a feature branch directly into a
specified target branch without creating a PR. The target branch is **required**
(not defaulted to `main`) so the skill and CLI make the merge destination
explicit for teams that ship to `dev`, `staging`, or other integration branches.

The command must preserve the safety value of a PR by detecting merge conflicts
against the target branch before performing the merge.

## Task List

1. **Add `aet ship merge <plan> --branch <target>` to `src/aet/cli/ship.py`.** — M [x]

   - `--branch` is a required string option (no default).
   - Resolve the plan argument with `_resolve_plan_arg`.
   - Run the existing pre-merge gate (`_run_gate`).
   - Run the release guard and monolithic-commit checks used by `cmd_open`.
   - Detect conflicts before merging:
     - Fetch `origin`.
     - Compute `git merge-tree $(git merge-base HEAD origin/<target>) HEAD origin/<target>`.
     - If the merge tree contains conflict markers starting with `<<<<<<<`,
fail with a clear message telling the user to rebase or resolve conflicts first.
   - Perform the merge:
     - Locate an existing worktree for `<target>` or create a temporary one at
`.worktrees/.merge-<target>-<pid>`.
     - In the target worktree: checkout `<target>`, pull `origin/<target>`, merge
the feature branch, and push `<target>`.
     - Remove the temporary worktree if one was created.
   - Record closure by calling `aet_state.cmd_record_merge` with the resulting
merge commit.

2. **Wire the Typer subcommand and argparse fallback.** — S [x]

   - Add `ship_merge` to the Typer app.
   - Add a `merge` subparser in `build_parser()` for parity with the
legacy argparse path.

3. **Update `skills/aet-ship/SKILL.md` with the new command.** — S [x]

   - List `aet ship merge <plan> --branch <target>` alongside existing commands.
   - Note that `--branch` is required and that conflict detection is performed
before the merge.

4. **Add tests in `tests/test_ship_merge.py`.** — M [x]

   - Test that missing `--branch` is rejected.
   - Test conflict detection returns a non-zero exit code.
   - Test a clean merge path (mock git calls to avoid mutating the real repo).
   - Test that the gate failure prevents merge.

## Files to Modify

- `src/aet/cli/ship.py`
- `src/aet/cli/aet_state.py`
- `skills/aet-ship/SKILL.md`
- `tests/test_ship_merge.py` (new)
- `tests/cli/test_build_parsers.py`

## Validation Steps

- [x] `aet ship merge --help` shows `--branch` as required.
- [x] `aet ship merge <plan>` without `--branch` fails immediately.
- [x] Simulated conflict is detected and merge is aborted.
- [x] `make validate` passes.
- [x] `make test` passes.

## Rollback Plan

Revert the changes to `src/aet/cli/ship.py`, `src/aet/cli/aet_state.py`,
`skills/aet-ship/SKILL.md`, `tests/cli/test_build_parsers.py`, and
delete `tests/test_ship_merge.py`.

---

_Stage: merged_
_Next step: run `aet-work`_
