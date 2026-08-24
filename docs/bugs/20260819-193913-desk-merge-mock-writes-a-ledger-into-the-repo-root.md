# Bug: desk merge mock writes a ledger into the repository root

## Metadata

- **Reported:** 2026-08-19
- **Severity:** medium
- **Status:** resolved

## Symptoms

Running the test suite left a directory named after a commit SHA in the
repository root:

```text
abc123def456/.agents/ledger.jsonl
abc123def456/.agents/ledger.jsonl.lock
```

Untracked, so it showed up in `git status` and would have been swept into any
`git add -A`. The contents are synthetic — the events reference pytest tmpdirs —
so this was litter rather than corrupted state.

## Reproduction Steps

```bash
rm -rf abc123def456
python -m pytest tests/state/test_desk_actions.py -q
ls abc123def456/.agents/ledger.jsonl   # present
```

Deterministic: reproduced 3/3 on the file and on the single test
`TestMergeSuccess::test_merge_drives_closure_path_to_merged`.

It was originally described as intermittent. That was wrong — it is deterministic
per test. It only *looked* intermittent under `-n auto` because xdist workers do
not all run with the repository root as their cwd.

## Root Cause

Two things combine.

- `_merge_subprocess_runner` (`tests/state/test_desk_actions.py:194`) is installed
  with `monkeypatch.setattr(desk.subprocess, "run", ...)`. `desk.subprocess` is
  the `subprocess` **module object**, not a module-local alias, so this replaces
  `subprocess.run` **process-wide**. Verified: `desk.subprocess is subprocess`
  and `aet.ledger.subprocess is subprocess` are both `True`.
- The mock matched on the git *subcommand*, so every `rev-parse` returned
  `abc123def456` — including `rev-parse --show-toplevel`, which real git answers
  with an absolute path.

`ledger._resolve_ledger_repo_root()` calls exactly that, then returns
`Path(result.stdout.strip()).resolve()`. `Path("abc123def456")` is relative, so
`.resolve()` anchored it to the process cwd — the real checkout — and the ledger
writer created `<repo>/abc123def456/.agents/` on demand.

Blast radius is one helper: every other subprocess mock in the suite keys on the
full command tuple, so none of them intercept `--show-toplevel`.

**Why existing tests did not catch it:** nothing asserts that the suite leaves the
working tree unchanged, and the two affected tests pass either way — the stray
write is invisible to their assertions.

## Fix Summary

- **Files modified:** `tests/state/test_desk_actions.py`
- **Key change:** the mock answers `rev-parse --show-toplevel` with the `cwd` it
  already receives, and keeps returning the SHA for every other `rev-parse` form.
- **Side effects:** none. The two merge tests assert on
  `merge_commit == "abc123def456"`, which the unchanged branch still supplies.

## Regression Test

`tests/state/test_desk_actions.py::test_merge_runner_answers_show_toplevel_with_a_path`
asserts the mock returns an absolute path for `--show-toplevel` and the SHA for
`rev-parse HEAD`. Verified to fail with the fix hunk removed:

```text
AssertionError: --show-toplevel returned 'abc123def456'; a relative value makes
the ledger write into whatever directory the suite happens to run from
```

## Validation

- [x] Reproduction no longer creates the directory — 3/3 clean runs
- [x] `tests/state/test_desk_actions.py`: 7 passed
- [x] Full suite: 1748 passed, no stray directory afterwards
- [x] Regression test verified red without the fix
- [x] `ruff` clean

Known unrelated failure in the same run:
`test_nightshift_rehearsal.py::TestNightShiftExitGateRehearsal::test_stall_killed_and_classified_timeout`,
a pre-existing flake measured at roughly 13-27% across 30 runs. It shares no code
with this change.

## Follow-up Not Taken

`ledger._resolve_ledger_repo_root()` accepts a relative
`git rev-parse --show-toplevel` result and silently resolves it against cwd.
Rejecting a non-absolute root would make this whole class of mock error fail
loudly instead of writing a stray directory. Real git always returns an absolute
path, so it is defensive only, and it is product scope on a test-side bug —
deliberately left out rather than folded in.

There is also no guard asserting that a test session leaves the working tree
unchanged. Such a guard would have caught this, the F-1 defect, and anything else
in the family. Worth considering separately.

## Lessons Learned

- **Pattern:** patching an attribute on an imported module object is
  **process-wide**, not module-local. `monkeypatch.setattr(mod.subprocess, "run")`
  reads as narrow and is not. Any code reached during that test sees the mock.
- **Prevention:** a subprocess mock that matches on a subcommand must answer every
  form of that subcommand realistically, or match on the full argument list.
  `rev-parse` is the sharp case: it returns a SHA for most forms and a path for
  `--show-toplevel`.
- **Reference:** `docs/bugs/20260819-190235-gate-tests-reach-the-real-repository-remote.md`
  — same family, tests writing into the real checkout.
