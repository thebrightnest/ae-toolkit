# Bug: config and store anchored to different repositories

## Summary

`create_backend` resolved the in-tree config against the repository discovered
from the **process cwd**, then handed the queue path to whichever backend that
config named. `GitRefsBackend` anchors its store to the repository discovered
from the **queue file's own location**. When the two disagreed — a project
config in one tree, a queue path outside it — the backend was selected by
repository A and rooted in repository B, and the mismatch escaped as an uncaught
`RuntimeError` with a full traceback.

Discovered while deciding whether to merge `.agents/aet-config.json` to `main`:
adding a valid project config to this repository made **22 tests fail**. The
tests had been passing on the *absence* of that file, not on isolation.

## Environment

- ae-toolkit at `254e82fe` (v1.8.0 + 2), branch `fix/config-and-backend-share-one-root`
- Trigger: any project config selecting `task_backend: git-refs` plus a queue
  path outside that repository

## Reproduction

```bash
# tree A: a repository whose project config selects git-refs
git init -q /tmp/repo && mkdir -p /tmp/repo/.agents
echo '{"task_backend": "git-refs"}' > /tmp/repo/.agents/aet-config.json

# tree B: a queue outside any repository
mkdir -p /tmp/outside && echo '[]' > /tmp/outside/q.json

cd /tmp/repo
aet sprint add <plan> --queue-file /tmp/outside/q.json --history-file /tmp/outside/h.jsonl
```

Observed:

```
RuntimeError: GitRefsBackend requires the queue path to live inside a git
repository; /tmp/outside is not inside a git repository
```

Uncaught, so the CLI exits 1 with a traceback and no named error.

In this repository the same condition is reached by simply creating
`.agents/aet-config.json`, because `tests/workflow/test_aet_work_add_review.py`
(13 tests) and `tests/plan/test_intake_gate.py` (9 tests) build a temp repo root
and pass `--queue-file` into it without overriding `--config`.

## Root cause

Two derivations of one fact, with nothing requiring them to agree:

- `resolve_config_with_source` (`backends/factory.py:101-108`) anchors both the
  external `~/.aet/{slug}/config.json` lookup and the in-tree `config_path` to
  `resolve_repo_root(repo_root)` — the cwd-discovered root when no `repo_root`
  is passed. This is deliberate, so subdirectory invocations resolve the same
  config as root invocations.
- `GitRefsBackend.__init__` (`backends/git_refs_backend.py:81-82`) anchors the
  store to `_discover_repo_root(Path(queue_file).resolve().parent)`.

`create_backend` called `resolve_config(...)` with no `repo_root`, so the two
roots were independent. The failure is therefore not test-specific: it is
reachable by any operator with `git-refs` configured who points `--queue-file`
outside the repository.

## Impact

- Uncaught traceback instead of a named error on a reachable misconfiguration.
- The toolkit could not dogfood the project config it ships: this repository's
  own suite broke when the repository was configured.
- A config in one tree silently governed operations on a queue in another.

## Fix

Derive the root **once**, from the queue file being operated on, and use it for
both layers.

- `_queue_repo_root(queue_file)` walks up from the queue file's directory to the
  first ancestor containing a `.git` entry. It walks past a not-yet-created
  directory first, which is what keeps subdirectory invocations resolving the
  repository root. It uses a filesystem test rather than `git rev-parse`
  because config resolution runs on the status/next read path, which must invoke
  no git subprocess (`tests/orchestrator/test_read_path_no_git.py`). A `.git`
  *file* is a linked worktree, whose work-tree root is where that file lives.
- `create_backend` passes that root into `resolve_config`, so a queue outside
  any repository finds no in-tree config and falls back to `json`
  deterministically rather than by accident.
- Selecting `git-refs` for a queue outside a repository now raises
  `QueueOutsideRepositoryError`, handled at the CLI boundary in
  `cli/main.py` and printed as a named refusal.

Files: `src/aet/backends/factory.py`, `src/aet/cli/main.py`,
`tests/backends/test_config_root_anchoring.py`. Within the bug diff budget.

## Validation

- The 22 previously-failing tests pass with the project config present (36/36 in
  the two files).
- Full suite: **1684 passed** with `.agents/aet-config.json` present.
- The regression test was verified to fail before the fix: the same two-tree
  scenario raises `RuntimeError` on the pre-fix code and returns a `JsonBackend`
  after.
- A test pins the no-git-subprocess invariant, which the first attempt at this
  fix broke — `subprocess.run(["git", ...])` in `create_backend` put a git call
  on the read path and failed `test_read_path_no_git.py`.

## Test gap noted

`tests/workflow/test_aet_work_add_review.py` and `tests/plan/test_intake_gate.py`
still do not override `--config`. They now pass because resolution follows the
queue rather than the cwd, but they remain sensitive to the ambient repository in
principle. Not fixed here: it would widen the diff beyond the root cause, and the
production defect is closed.

## Related observation (not part of this fix)

One intermittent failure was seen once under `pytest -n auto` in
`tests/test_aet_run_dispatch.py::TestRunOneBlocks`. It passes in isolation,
passes alongside the new tests, and passes on a full re-run. Recorded as a
suspected pre-existing flake, not investigated.
