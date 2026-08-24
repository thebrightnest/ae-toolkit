# Local `main` reset to `origin/main` — divergence record

*Date: 2026-08-24 — Reset performed on branch `main`*

Local `main` had diverged from `origin/main` by 7 commits ahead / 106 behind. The
divergence was resolved by discarding local `main` and taking `origin/main` as
authoritative. This record names every piece of work that left `main` in that
reset and the exact command that brings each one back.

## Preserved refs

*Both branches were deleted on 2026-08-24 once every item below was replayed;
the SHAs remain valid in the reflog for its expiry window.* Two local branches
held the discarded state:

| Ref | SHA | Contents |
|---|---|---|
| `backup/main-pre-sync` | `e011f9cf` | Local `main` exactly as it stood before the reset: the 7 divergent commits on top of merge-base `3e91670a`. |
| `wip/main-sync-merge-20260824` | `4750bac9` | A completed merge of `origin/main` into that tip, with all five conflicts resolved. **The test suite was never run against this tree.** |

Both are local-only and unpushed. `git reflog main` also holds `e011f9cf` until
the reflog expires (90 days by default), but the two branches are the durable
handle.

Merge-base of local and upstream: `3e91670a` ("Merge owb-05-board-is-open-work
into main").

## What upstream superseded

Three items in the discarded work are already in `origin/main` by other means.
They need no recovery.

- **`e011f9cf` — desk merge mock writing a ledger into the repo root.** Upstream
  fixed the identical bug independently: `tests/state/test_desk_actions.py` on
  `origin/main` already delegates `-C` invocations to the real subprocess and
  answers `rev-parse --show-toplevel` with a real path.
- **The factory half of `49977159`** (git-refs store anchoring). `queue_repo_root`
  and the config-anchoring comment in `src/aet/backends/factory.py` are present
  on `origin/main` verbatim.
- **`docs/prds/orchestrator-signal-exit-determinism-prd.md`**, which was untracked
  in the working tree. The untracked copy was an earlier `scope-validated` draft;
  `origin/main` carries the finished document at stage `synced`, including the
  `osd-01` and `osd-02` divergence summaries. The stale draft was not preserved
  and does not need to be.

## Item 1 — owb-13: PRD-derived integration branch (R-17)

**Commits:** `53ca943f` (implementation), `7362ee51` (PRD sync), plus the merge
commit `eb5d96ef`.

**Status upstream:** absent. `derive_integration_branch_from_prd`,
`resolve_integration_branch_for_task`, `_task_prd_path` and `prd_path_from_text`
exist nowhere in `main`. The fifth symbol is a move rather than an addition:
`main` carries a private `_prd_path_for_plan` and the `_PRD_REF_RE` regex inside
`src/aet/plan_validate.py:153-165`, and the discarded work lifts both into
`src/aet/plan_parser.py` as public helpers that `plan_validate` then calls
through to.

`origin/main`'s own `docs/prds/open-work-board-prd.md:73` still states R-17 — "the
integration branch is derived from the PRD a task belongs to, rather than from a
single static config value, so concurrent PRDs each carry their own branch and
PR" — and its acceptance criterion at `:131` is unchecked. Upstream therefore
treats R-17 as open work. This is the only implementation of it that exists.

Counts are `git show --stat` totals for `53ca943f`, and for `7362ee51` in the
last row.

| File | Changed lines | Content |
|---|---|---|
| `src/aet/branch_ref.py` | 83 | `derive_integration_branch_from_prd`, `_task_prd_path`, `resolve_integration_branch_for_task` — branch-name resolution kept in one module rather than split across backend and CLI |
| `src/aet/cli/aet_state.py` | 122 | audit, heal, validate, reset, transition and record-merge resolve the integration branch per task |
| `src/aet/plan_parser.py` | 37 | `prd_path_from_text`, `prd_path_for_plan`, and `_PRD_REF_RE` |
| `src/aet/cli/ship.py` | 20 | `ship verify` against a PRD-derived branch |
| `src/aet/cli/orchestrator.py` | 8 | call-site wiring |
| `src/aet/plan_validate.py` | 7 | reuses the new parser instead of its own PRD regex |
| `tests/orchestrator/test_prd_derived_integration_branch.py` | 461 | primary coverage |
| `tests/state/test_aet_state.py` | 159 | transition and record-merge |
| `tests/cli/test_ship_verify.py` | 123 | `ship verify` branch resolution |
| `docs/prds/open-work-board-prd.md` | 19 | owb-13 divergence summary |

A second live copy of this work exists outside the two preserved branches:
`.worktrees/owb-13-prd-integration-branch` is checked out at `7362ee51` with a
clean tree, so the feature can also be read or built there directly without
restoring anything.

Recovery of the whole feature, rebased onto current `main`:

```sh
git checkout -b owb-13-r17-replay origin/main
git cherry-pick 53ca943f 7362ee51
```

Replayed onto `main` at `7c94b248`, each commit conflicts in exactly one file:
`src/aet/cli/aet_state.py` for `53ca943f`, which upstream rewrote for the
git-refs-only store, and `docs/prds/open-work-board-prd.md` for `7362ee51`, whose
divergence summary lands in a region upstream also edited. `src/aet/cli/ship.py`,
`src/aet/plan_parser.py`, `src/aet/cli/orchestrator.py` and all three test files
auto-merge. `53ca943f` does not touch `src/aet/backends/factory.py`; that file
belongs to item 4.

Reviewing the feature before replaying it:

```sh
git show --stat 53ca943f
git show 53ca943f -- src/aet/branch_ref.py src/aet/plan_parser.py
```

`owb-13` branched at `77214bcc`, not at the merge-base — `eb5d96ef`'s parents are
`3e91670a` and `7362ee51` — so a diff from `3e91670a` to `53ca943f` also reverses
the `owb-05` merge. `src/aet/plan_parser.py` reads 44 added and 12 removed lines
that way, against 37 added and none removed in the commit itself.

## Item 2 — test isolation: never reach the real remote

**Commit:** `223814c4`. **Status upstream:** absent.

`tests/conftest.py` gained an autouse `_no_real_remote` fixture that patches
`aet.backends.git_refs_backend._has_remote` to report no remote when the repo root
is this checkout. Tests that run backend code under
`patch.dict(os.environ, ..., clear=True)` resolve the queue path relative to the
process cwd, land on this checkout, and then stall for minutes on `git fetch
origin` with `HOME` and `SSH_AUTH_SOCK` wiped. The fetch refspec is forced, so on
a machine whose git auth survives a cleared environment the fetch overwrites the
developer's own `refs/aet/*` from origin. Patching the module attribute is what
survives `clear=True`; an environment variable would not.

`tests/test_suite_isolation.py` (+45) asserts the guard holds.

The hazard is still live on `main`. `_AET_FETCH_REFSPEC` is
`+refs/aet/*:refs/aet/*` (`src/aet/backends/git_refs_backend.py:45`), `fetch`
still gates on the module-level `_has_remote` (`:341-350`), and neither of the
autouse fixtures upstream added covers it: `_isolate_ledger` patches
`ledger._resolve_ledger_repo_root` and `_isolate_aet_repo_root` deletes
`AET_REPO_ROOT`, and a backend constructed under a cleared environment still
resolves this checkout and still fetches.

The bug writeup is `docs/bugs/20260819-190235-gate-tests-reach-the-real-repository-remote.md`.

```sh
git checkout -b test-isolation-replay origin/main
git cherry-pick 223814c4
```

The cherry-pick conflicts in two files. `tests/conftest.py` is the one that
matters: upstream added `_isolate_ledger` and `_isolate_aet_repo_root` in the same
region. All three are independent autouse fixtures and all three are wanted, so
the resolution is to keep them; the resolved version is at
`wip/main-sync-merge-20260824:tests/conftest.py`. The second is the append-only
tail of `.agents/learnings.jsonl`, which the commit adds one entry to — the same
line-range conflict described in item 5.

## Item 3 — `_PATH_TARGETS` drift guard

**Commit:** `2bce0d7e`. **Status upstream:** absent (`TestPathTargetsDrift` does
not exist in `origin/main`).

`tests/test_change_scope.py` (+60) fails when a `src/aet` module has no
`_PATH_TARGETS` prefix match and is not listed in the `_UNMAPPED_MODULES`
allowlist the same commit adds. A second assertion fails when the allowlist keeps
an entry that has since been mapped. `_PATH_TARGETS` is hand-maintained and
nothing else notices it drifting.

Drift costs precision, not coverage. `change_scope.targets` returns `["tests/"]`
as soon as any changed code path has no mapping
(`src/aet/change_scope.py:193-195`), so a module that falls out of
`_PATH_TARGETS` widens `make validate` to the full suite rather than dropping its
tests. What the guard defends is the scoping: an absent mapping turns targeted
runs silently back into full ones, and a mapping that exists but is too narrow
under-tests its module on every run.

On `main` at `7c94b248`, 18 of the 82 modules under `src/aet` have no
`_PATH_TARGETS` prefix match. Fifteen are exactly the allowlist the commit ships.
The three the guard would flag are `src/aet/liveness.py`, `src/aet/validation.py`
and `src/aet/validation_cache.py`, each with a dedicated test file
(`tests/orchestrator/test_liveness.py`, `tests/test_validation.py`,
`tests/test_validation_cache.py`) that no mapping names.

```sh
git checkout -b path-targets-drift-replay origin/main
git cherry-pick 2bce0d7e
```

The three missing mappings, applied on top:

```python
# src/aet/change_scope.py, in _PATH_TARGETS
    ("src/aet/liveness.py", "tests/orchestrator/test_liveness.py"),
    ("src/aet/validation.py", "tests/test_validation.py"),
    ("src/aet/validation_cache.py", "tests/test_validation_cache.py"),
```

`2bce0d7e` cherry-picks onto `7c94b248` without conflict. With the three
mappings added, the unmapped set is exactly the shipped allowlist, so both drift
assertions hold; the file collects 25 tests on `main` and 27 once the guard's two
are added.

## Item 4 — `GitRefsBackend(repo_root=…)` pass-through

**Commit:** `49977159`, backend half only. **Status upstream:** absent.

Upstream took the factory half of this fix and not the backend half. On
`main`, `create_backend` derives `queue_root` in pure Python
(`src/aet/backends/factory.py:84-107`), anchors config resolution and the
out-of-repo refusal to it, and then does not pass it to the constructor;
`GitRefsBackend.__init__` re-derives its own root by shelling out to `git
rev-parse --show-toplevel` (`src/aet/backends/git_refs_backend.py:88-93`,
`:105-118`). Upstream's version is correct, because it also walks up from a queue
directory that does not exist yet, but it spends a git subprocess on every
backend construction to recompute a value the caller already holds.

The subprocess-free property therefore covers config resolution only, not the
construction that follows it. `tests/orchestrator/test_read_path_no_git.py`, which
`queue_repo_root`'s docstring cites for the requirement, does not reach either:
its three tests drive `orchestrator.get_next_ready_task` and
`has_pending_tasks` over in-memory queue lists and never construct a backend. The
assertion that does hold upstream is
`test_root_discovery_invokes_no_git_subprocess`
(`tests/backends/test_config_root_anchoring.py:80`), and it covers
`queue_repo_root` alone.

The discarded local version accepts `repo_root` and keeps discovery as the
fallback for direct construction. Its 25 added lines in
`tests/backends/test_config_root_anchoring.py` add one test, for subdirectory
invocation. Out-of-repo refusal
(`test_out_of_repo_queue_is_refused_by_name`, `:39`) and the no-git-subprocess
check (`:80`) already exist on `main`.

The resolved form, which combines the pass-through with upstream's `posture`
parameter and walk-up fallback, is on the merge branch:

```sh
git show wip/main-sync-merge-20260824:src/aet/backends/git_refs_backend.py
git diff origin/main wip/main-sync-merge-20260824 -- src/aet/backends/
```

One caveat when replaying `tests/backends/test_config_root_anchoring.py`: its last
test calls `_repo(tmp_path / "repo", backend="git-refs")`, written against a helper
signature that upstream removed with `task_backend`; `main`'s helper is
`_repo(root: Path, config: dict | None = None)`
(`tests/backends/test_config_root_anchoring.py:26`). The call becomes
`_repo(tmp_path / "repo", config={})`. Auto-merge does not catch this — the two
sides touch different lines of the file — and the module still imports, so the
failure surfaces as a `TypeError` when that one test runs.

## Item 5 — bug writeups and learnings

Three `docs/bugs/` documents exist only on `backup/main-pre-sync`:

- `20260819-162612-git-refs-store-root-ignores-subdirectory-invocation.md` (135 lines)
- `20260819-190235-gate-tests-reach-the-real-repository-remote.md` (125 lines)
- `20260819-193913-desk-merge-mock-writes-a-ledger-into-the-repo-root.md` (118 lines)

The third documents a bug upstream fixed independently; the writeup itself is
still the only record of the analysis. Two of the three ride along with their
commits: `223814c4` adds the `190235` writeup, so item 2's cherry-pick carries it,
and `49977159` adds the `162612` one, which item 4's replay does not pick up
because it works from the merge branch rather than the commit. The checkout below
covers all three regardless.

Three `.agents/learnings.jsonl` entries were also discarded, timestamped
2026-08-19 at 15:39, 18:04 and 18:39. The ledger is append-only; the last entry at
the merge-base is 2026-08-19T00:17Z and upstream's nine additions run from
2026-08-20T12:44Z to 2026-08-23T21:05Z, with no deletions. The three entries
therefore slot in ahead of upstream's without conflicting on content — only the
line range conflicts.

```sh
# restore the writeups without touching anything else
git checkout backup/main-pre-sync -- docs/bugs/20260819-162612-git-refs-store-root-ignores-subdirectory-invocation.md \
                                     docs/bugs/20260819-190235-gate-tests-reach-the-real-repository-remote.md \
                                     docs/bugs/20260819-193913-desk-merge-mock-writes-a-ledger-into-the-repo-root.md

# read the discarded learnings entries
git diff 3e91670a backup/main-pre-sync -- .agents/learnings.jsonl
```

## Reviewing the whole discarded set

```sh
# every local commit that left main
git log --oneline 3e91670a..backup/main-pre-sync

# their net effect against the merge-base
git diff 3e91670a backup/main-pre-sync

# the resolved merge, against what main now is
git diff origin/main wip/main-sync-merge-20260824

# the full pre-reset state, restored wholesale
git checkout -b main-pre-sync-review backup/main-pre-sync
```

## Verification, 2026-08-24

`main` stands at `7c94b248` ("chore(release): prepare v1.10.0"), identical to
`origin/main` — zero commits in either direction. Nothing pushed to `main` after
the reset alters the status of any item above.

Both preserved branches are intact at the recorded SHAs and appear on no remote
ref. `.worktrees/owb-13-prd-integration-branch` is checked out at `7362ee51` with
a clean tree. All eleven commit SHAs named in this record resolve.

`wip/main-sync-merge-20260824`'s second parent is `7c94b248` itself, so
`git diff origin/main wip/main-sync-merge-20260824` compares the resolved merge
against `main` as it stands. Re-running that merge names the five conflicts it
resolved: `.agents/learnings.jsonl`, `src/aet/backends/factory.py`,
`src/aet/backends/git_refs_backend.py`, `tests/conftest.py` and
`tests/state/test_desk_actions.py`.

Cherry-pick outcomes were established without modifying the working tree, using
`git merge-tree --write-tree --merge-base <commit>^ main <commit>`:

| Commit | Item | Conflicts |
|---|---|---|
| `53ca943f` | 1 | `src/aet/cli/aet_state.py` |
| `7362ee51` | 1 | `docs/prds/open-work-board-prd.md` |
| `223814c4` | 2 | `tests/conftest.py`, `.agents/learnings.jsonl` |
| `2bce0d7e` | 3 | none |

The three superseded items hold as recorded: `tests/state/test_desk_actions.py`
on `main` delegates `-C` invocations to the real subprocess and answers
`--show-toplevel` with a real path (`:210-261`); `queue_repo_root` and the
anchoring comment are present in `src/aet/backends/factory.py` (`:84`, `:125-131`);
and `docs/prds/orchestrator-signal-exit-determinism-prd.md` carries both
divergence summaries and closes at `*Stage: synced*`.

## Recommended follow-up

Item 1 implements a requirement `main` still lists as open at
`docs/prds/open-work-board-prd.md:73`, with its acceptance criterion unchecked at
`:131` and Phase 7 described at `:143` as "R-17 is the delta, not the mode". Item
2 guards a hazard that is live on `main` today: a forced fetch refspec that can
overwrite a developer's own `refs/aet/*` from origin. Item 3 is the only check on
`_PATH_TARGETS` drift and cherry-picks clean. Each warrants replay as its own
branch rather than a re-merge of `backup/main-pre-sync`, whose merge commit
`eb5d96ef` would drag the superseded work back in with them.

The two preserved branches can be deleted once every item above is either replayed
or explicitly abandoned:

```sh
git branch -D backup/main-pre-sync wip/main-sync-merge-20260824
```

`.worktrees/owb-13-prd-integration-branch` holds the same R-17 work and outlives
those branches; it is removed with `git worktree remove` rather than
`git branch -D`. Its own `.venv` is an editable install rooted at the worktree,
which is what a build or test run inside it executes.

Removing the worktree does not change what `aet` executes on this machine.
`/Users/p.rocha/.local/bin/aet` runs the interpreter in
`~/.local/share/ae-toolkit/venv`, whose `aet` is a non-editable install of
`~/.local/share/ae-toolkit/repo` — its `direct_url.json` carries no `editable`
flag and the venv holds no `.pth` — at version 1.10.0, matching `main` at
`7c94b248`.
