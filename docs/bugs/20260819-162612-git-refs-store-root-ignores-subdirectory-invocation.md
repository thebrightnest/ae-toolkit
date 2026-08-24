# Bug: git-refs store root ignores subdirectory invocation

## Metadata

- **Reported:** 2026-08-19T16:26:12+0100
- **Severity:** high
- **Status:** resolved

## Symptoms

Any `aet` command that constructs the task backend crashes with an uncaught
`RuntimeError` and a full traceback when run from a subdirectory of a repository
configured with `task_backend: git-refs`. From the repository root the same
command succeeds.

```
RuntimeError: GitRefsBackend requires the queue path to live inside a git
repository; <repo>/a/b/c/.agents is not inside a git repository
```

The failure contradicts a documented requirement: `backends/factory.py:136,185`
both state that in-tree paths are anchored to the repository root "so
subdirectory invocations resolve the same config as root invocations", and R-2
of `docs/prds/aet-config-file-overhaul-prd.md` records the same guarantee.

## Reproduction Steps

```bash
mkdir -p probe && cd probe
git init -q . && mkdir -p .agents a/b/c
echo '{"task_backend":"git-refs"}' > .agents/aet-config.json
echo '{"tasks":{}}' > .agents/work-queue.json
: > .agents/work-history.jsonl
git add -A && git commit -qm init

python -m aet.cli.main state audit          # from root:   {}  rc=0
(cd a     && python -m aet.cli.main state audit)   # RuntimeError
(cd a/b/c && python -m aet.cli.main state audit)   # RuntimeError
```

Deterministic — reproduced at depth 1 and depth 3, repeated runs, fresh
repository each time. `state audit` is documented as non-mutating, so the
reproduction is read-only.

## Root Cause

One fact derived twice, with nothing requiring the two derivations to agree —
the same root cause named in
`docs/bugs/20260814-091729-config-and-store-anchored-to-different-repos.md`.
That report's stated fix was to "derive the root **once**, from the queue file
being operated on, and use it for **both layers**". Only the config layer got it.

- `create_backend` (`backends/factory.py:96`) computes
  `queue_root = queue_repo_root(queue_file)` by walking the filesystem up from
  the queue file's own location, uses it to anchor config resolution, and uses it
  again for the `QueueOutsideRepositoryError` guard at line 111 — then **discards
  it**. Line 117 constructed `GitRefsBackend` without it.
- `GitRefsBackend.__init__` (`backends/git_refs_backend.py:86-87`) therefore
  re-derived its own root as
  `_discover_repo_root(Path(queue_file).resolve().parent)`, which runs
  `git -C <dir> rev-parse --show-toplevel`. `queue_file` is the **relative**
  default `.agents/work-queue.json`, so `Path(...).resolve()` anchors on the
  process cwd. From a subdirectory that names a directory which does not exist,
  and `git -C` on a missing directory fails.

Measured from `probe/a/b/c` before the fix:

| Layer | Resolves to |
| --- | --- |
| `queue_repo_root()` | `<repo>` — correct |
| `resolve_config()` | `{'task_backend': 'git-refs'}` — correct |
| `GitRefsBackend` | `<repo>/a/b/c/.agents` → `git -C` fails |

`queue_repo_root` deliberately walks past a not-yet-created directory, which is
what makes it survive a subdirectory invocation; `_discover_repo_root` has no
such tolerance because `git -C` cannot enter a missing directory.

**Why existing tests did not catch it:** every test either ran with cwd at the
repository root or passed an absolute `--queue-file`. No test constructed the
backend from a subdirectory using the relative defaults that `gate`, `state`, and
the other CLI entry points actually pass.

## Fix Summary

Pass the already-derived root into the backend instead of letting it re-derive.

- **Files modified:** `src/aet/backends/git_refs_backend.py`,
  `src/aet/backends/factory.py`,
  `tests/backends/test_config_root_anchoring.py`
- **Key change:** `GitRefsBackend.__init__` accepts an optional pre-resolved
  `repo_root`; `create_backend` passes the `queue_root` it already holds.
- **Side effects:** when constructed through `create_backend`, the store's root
  now comes from `queue_repo_root`'s filesystem walk rather than
  `git rev-parse --show-toplevel`. This is the intended consequence — it is what
  makes the config and the store agree by construction — but it is a change of
  *mechanism*, not only of source, and the two can differ at edges such as
  submodules. Direct construction without `repo_root` is unchanged and still
  discovers via git, so the 17 test call sites keep their existing behaviour.
  Construction through `create_backend` now runs one fewer `git` subprocess.

## Regression Test

`tests/backends/test_config_root_anchoring.py::test_subdirectory_invocation_roots_the_store_at_the_repository`
— builds a git-refs repository, `chdir`s into `a/b/c`, calls `create_backend`
with the relative defaults, and asserts a `GitRefsBackend` rooted at the
repository. Marked `xdist_group("cwd")` because it changes the process
directory.

Verified to fail before the fix with the exact reported signature
(`RuntimeError ... /a/b/c/.agents is not inside a git repository`) and to pass
after.

## Validation

- [x] Reproduction steps no longer trigger the bug — `{}` rc=0 at root, depth 1,
      and depth 3
- [x] `tests/backends/` + `tests/orchestrator/test_read_path_no_git.py`:
      105 passed, including the pinned no-git-subprocess invariants
- [x] Regression test verified red before the fix, green after
- [x] Full suite: **1744 passed**, 0 failures (13 min 18 s) — 1743 pre-existing
      plus the new regression test

## Lessons Learned

- **Pattern:** a fix that names the right principle ("derive it once, use it for
  both layers") but applies it to only one of the layers. The second derivation
  survived because it lived in a different module from the fix.
- **Prevention:** when a bug report's root cause is "two derivations of one
  fact", the fix should delete or subordinate *every* derivation, and the
  regression test should assert the two layers agree — not merely that the
  reported symptom is gone. A test that exercises the CLI's real relative
  defaults from a non-root cwd would have caught both this and the Aug 14 bug.
- **Reference:** `docs/bugs/20260814-091729-config-and-store-anchored-to-different-repos.md`
  (same defect class, config layer); R-2 in
  `docs/prds/aet-config-file-overhaul-prd.md`.
