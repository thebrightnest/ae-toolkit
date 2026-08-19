# Bug: gate tests reach the real repository's remote

## Metadata

- **Reported:** 2026-08-19
- **Severity:** high
- **Status:** resolved

## Symptoms

`tests/gate/test_gate_submit.py` took **36 min 34 s** to run serially — 25 tests,
with individual tests as slow as 679 s. The durations were not reproducible: the
same test measured 77.6 s in one run and under 4.1 s in another with identical
collection order and no random-ordering plugin installed.

The cost was not work. It was `git fetch origin` against the **real repository**,
stalling on authentication until timeout.

## Reproduction Steps

```bash
# before the fix
python -m pytest tests/gate/test_gate_submit.py --durations=15 -q
# 25 passed in 2194s (0:36:34); slowest single test 679.73s
```

Mechanism isolated independently:

```bash
git fetch origin '+refs/aet/*:refs/aet/*'                      # 1.9 s
env -i PATH=/usr/bin:/bin git fetch origin '+refs/aet/*:refs/aet/*'   # 6 min 15 s
```

## Root Cause

The tests run `gate.main()` in-process under
`patch.dict(os.environ, {...}, clear=True)` (e.g. `test_gate_submit.py:86`).

- `gate.py:301-305` constructs the backend with the **relative** default
  `.agents/work-queue.json`, so the root is derived from the process cwd — which
  during a test run is this checkout. `AET_REPO_ROOT` does not enter this path,
  which is why the 8 tests that already set it were affected too.
- This repository's `.agents/aet-config.json` selects `git-refs`, so
  `GitRefsBackend.fetch()` runs `git fetch origin '+refs/aet/*:refs/aet/*'`
  (`git_refs_backend.py:310`).
- `clear=True` wipes `HOME` and `SSH_AUTH_SOCK`, so git's credential/SSH lookup
  stalls until timeout. The variance between runs is connection-state dependent,
  which is why no duration here is stable.

Measured blast radius: **23 of 25 tests** in that one file reach the real
repository's remote. No test in the other 15 files that use `clear=True` does.

**The data-integrity half.** The refspec is *forced*. On this machine the stall
means the fetch never completes, but on any machine or CI whose git auth survives
a cleared environment, running the suite would force-overwrite the developer's
own `refs/aet/*` from origin. That, not the runtime, is the reason this is filed
as high severity.

## Fix Summary

- **Files modified:** `tests/conftest.py`, `tests/test_suite_isolation.py` (new)
- **Key change:** a fourth autouse isolation fixture makes
  `git_refs_backend._has_remote` return `False` **for this checkout only**,
  delegating to the real implementation for every other path. `fetch()` and
  best-effort `push()` then return before shelling out.
- **Why a module attribute and not an env var:** the affected tests run under
  `clear=True`, which wipes env vars. `tests/conftest.py` already records this
  same lesson for the telemetry archive.
- **Why scoped to this checkout:** an unconditional guard breaks 13 tests in
  `test_git_refs_sync.py`, `test_git_refs_reconcile.py`, and
  `test_state_reconcile.py` that legitimately exercise fetch/push against tmpdir
  fixture remotes. The scoping is load-bearing.

Effect: `tests/gate/test_gate_submit.py` 36 min 34 s → **7.34 s**.

## Regression Test

`tests/test_suite_isolation.py`:

- `test_real_repo_remote_is_unreachable_from_tests` — pins the invariant.
  Verified to fail when the guard is removed.
- `test_guard_does_not_hide_remotes_of_other_repositories` — pins the scoping, so
  a future broadening of the guard fails instead of silently disabling the
  backend suite.

## Validation

- [x] `tests/gate/test_gate_submit.py`: 25 passed in 7.34 s (was 36 min 34 s)
- [x] Regression test verified red without the guard, green with it
- [x] Full suite green — see commit
- [x] `ruff` clean

## Known Limitation

This is a **net, not a cure**. The 23 tests still resolve this checkout; they can
no longer reach its remote. The cure is to run them with cwd inside a
git-initialized tmp repo — the `xdist_group("cwd")` + `monkeypatch.chdir` idiom
already used in `tests/backends/test_git_refs_sync.py:35,72`. That is a 23-test
restructure, outside the bug diff budget, and it would enlarge the serialized
`@cwd` group. Filed as a known limitation rather than done here.

Note that setting `AET_REPO_ROOT` — the fix suggested by
`content/2026-08-19-scoped-validation-review.md` — does **not** work: neither
`queue_repo_root()` nor `GitRefsBackend` consults it.

## Unrelated Findings Observed

- `tests/orchestrator/test_nightshift_rehearsal.py::TestNightShiftExitGateRehearsal::test_stall_killed_and_classified_timeout`
  is flaky at roughly 13–27% (2/15 failures without this change, 4/15 with —
  statistically indistinguishable). Pre-existing; unrelated to this fix.
- A test run can leave an `abc123def456/` directory in the repository root
  containing `.agents/ledger.jsonl`. The name is a mocked merge SHA from
  `tests/state/test_desk_actions.py` used as a path component. Same defect
  family; intermittent; not addressed here.

## Lessons Learned

- **Pattern:** a test suite silently depending on the ambient repository. It was
  invisible because the symptom was slowness, not failure — and the durations
  were too unstable to look like a bug.
- **Prevention:** assert the isolation invariant directly rather than trusting
  that tests set the right env vars. An env-var-based fix would not have worked
  here at all, because the code path anchors on cwd.
- **Reference:** `docs/bugs/20260819-162612-git-refs-store-root-ignores-subdirectory-invocation.md`
  (the product-side defect in the same cwd-anchoring mechanism).
