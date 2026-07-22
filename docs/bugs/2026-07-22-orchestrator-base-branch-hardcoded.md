# Issue: orchestrator hardcodes `origin/main` as the worktree base

**Date:** 2026-07-22
**Component:** `aet run` / `aet run-one` orchestrator (`src/aet/worktree.py`, `src/aet/cli/orchestrator.py`)
**Severity:** blocks the AFK loop entirely for any project not using a
trunk-based, plans-on-`main` workflow.
**Status:** worked around (env var); needs a proper config-driven fix.

## Summary

The batch orchestrator cannot run plans for a project whose plan files live on
an integration or feature branch rather than on `main`. Every task fails
immediately with `❌ Plan not found in worktree` and, under the default
`--on-failure triage`, requeues in a loop — spawning agent sessions that burn
API cost without ever making progress.

## Where it was hit

Repo `example-service` (workflow per its branching ADR: `feat/*` and `fix/*`
branches integrate into `dev`, not `main`). A single ticket (`ABC-123`) was
planned as 11 stage plans committed to the feature branch
`feat/ABC-123-multi-stage-feature`. The plans were never merged to `main` or `dev`.
Running `aet run` produced, for every task:

```
Preparing worktree (new branch 'abc-123-s2')
branch '...' set up to track 'origin/main'.
HEAD is now at fd8096f6 ...
❌ Plan not found in worktree — base may be stale; ensure the plan is committed
   and pushed to origin/main
```

## Root cause

`create_worktree` bases every task worktree on a hardcoded `origin/main`:

```python
# src/aet/worktree.py
def create_worktree(repo_root, task_id, base_branch="origin/main"):
    ...
```

All three call sites in `orchestrator.py` (batch spawn, resume, single-plan)
call it with no `base_branch` argument, so the default always wins. There is no
CLI flag, environment variable, or config-file setting to change it.

The orchestrator then resolves the plan file *inside* the freshly cut worktree
(`plan_file = os.path.join(worktree_dir, relpath)`) and fails loudly if it is
absent. Because the base (`origin/main`) does not contain the plan committed on
the feature branch, the plan is always missing.

## Related `main` hardcodings (same class of bug)

These do not block the run once the base is fixed, but they make the toolkit
subtly wrong for non-`main` workflows and should be fixed together:

1. **`check_main_hygiene(repo_root)`** (`src/aet/worktree.py`) — the pre-branch
   durability gate checks `main` / `origin/main` for dirty tree and
   ahead/behind. For a `dev`-based project this should track the configured
   integration branch, not `main`. (In this incident it happened to pass only
   because local `main` was manually fast-forwarded to `origin/main` first.)
2. **`_session_diff_stats(worktree_dir)`** (`src/aet/cli/orchestrator.py`) —
   computes files-modified / commits-created with `git diff main...HEAD` and
   `git rev-list main..HEAD`. With a non-`main` base these stats include the
   entire base-vs-main delta, inflating per-task telemetry.

## Secondary issue found the same session

The orchestrator's dirty-tree check ignores only the four queue sidecars
(`work-queue.json`, `.lock`, `.lease`, `work-history.jsonl`). It does **not**
ignore the `.agents/runs/` telemetry directory it creates itself. In a project
that has not gitignored these paths, the orchestrator trips its own
dirty-tree hard-stop on the first run. `example-service` only gitignored
`.agents/learnings.jsonl`; adding the queue/runs paths to `.gitignore` was
required before the loop could start. Consider having `aet-setup` write these
ignore entries, and/or documenting them as a hard requirement.

## Workaround applied (2026-07-22)

Made the base branch resolvable from an environment variable, default
unchanged:

```python
def create_worktree(repo_root, task_id, base_branch=None):
    if base_branch is None:
        base_branch = os.environ.get("AET_WORK_BASE_BRANCH", "origin/main")
    ...
```

Backward compatible: env unset → `origin/main` (existing behavior); explicit
`base_branch=` callers unaffected. All 10 `tests/worktree` tests pass. Run with
`AET_WORK_BASE_BRANCH=origin/feat/ABC-123-multi-stage-feature aet run`.

Note: the base must be a ref that **contains the plan files**. `dev` itself does
not (the plans were only ever on the feature branch), so the feature branch —
which is itself based on `dev` — is the working base. Using literal `dev` would
require merging the plans into `dev` first (a protected-branch PR).

## Dangerous side effect found while applying the workaround

With the base pointed at the feature branch, re-running hit a **worktree HEAD
hijack**. Leftover task branches from the earlier `origin/main` runs still
existed. `create_worktree`'s refresh path ran:

```python
_run_git(["-C", repo_root, "rebase", "--onto", base, branch_base_sha, branch_name], ...)
```

Passing `rebase` a `<branch_name>` argument makes git **check that branch out in
`repo_root` first**, then rebase. Because `repo_root` was the operator's own
worktree, this silently switched it from `feat/ABC-123-multi-stage-feature` onto
`abc-123-s8` and replayed 11 unrelated `main`-side commits onto
it (reflog: `rebase (finish): returning to refs/heads/abc-123-s8`).

No commits were lost (the feature branch ref was untouched), but the operator's
working tree was left on the wrong branch and the run crashed with
`fatal: '<task-branch>' is already used by worktree at '<repo_root>'`.

**Fix:** worktree refresh must never check out a branch in `repo_root`. Operate
inside the task worktree, or move the ref with `git branch -f` / `git
update-ref` without a checkout. This is a plain bug independent of the base
branch or workflow.

## Proper fix (recommendation)

The design proposed alongside this report was adopted, split across two ADRs
(the original draft was numbered 041, which was already taken):
`docs/adr/044-base-branch-is-configured-not-assumed.md` for the generalization
below, and `docs/adr/045-epic-integration-branch-and-task-integration-mode.md`
for the epic/integration-branch layer with an `integration_mode` (`pr-per-task`
vs `single-pr`) and a local merge queue. The items below are the concrete first
steps and are planned under `docs/prds/non-trunk-integration-workflow-prd.md`.

1. Add a project-level `base_branch` (integration branch) setting to
   `.agents/aet-work.json`, defaulting to the repo's detected default branch
   (`git symbolic-ref refs/remotes/origin/HEAD`) rather than assuming `main`.
2. Thread that value through `create_worktree`, `check_main_hygiene` (rename to
   `check_base_hygiene`), and `_session_diff_stats` so all three agree on one
   base.
3. Keep `AET_WORK_BASE_BRANCH` as an override for one-off runs.
4. Have `aet-setup` gitignore `.agents/work-queue.json`,
   `.agents/work-queue.json.lock`, `.agents/work-queue.lease`,
   `.agents/work-history.jsonl`, and `.agents/runs/`.
5. Document that plans must live on the configured base branch for the AFK loop;
   the trunk-based assumption should be explicit in the aet-work skill.

## Verification against `aiskills@main` (2026-07-22, added during planning)

Every claim above was re-checked against this repository. All confirmed, with
three corrections and two additions.

**Confirmed:**

- `worktree.py:16` — `create_worktree(..., base_branch: str = "origin/main")`.
- `orchestrator.py:1042`, `:2036`, `:2332` — all three call sites pass no
  `base_branch`, so the default always wins.
- `worktree.py:377`, `:386` — `check_main_hygiene` hardcodes `origin/main..main`
  and `main..origin/main`.
- `orchestrator.py:428`, `:437` — `_session_diff_stats` uses `main...HEAD` and
  `main..HEAD`.
- `worktree.py:120` — the hijack: `git -C <repo_root> rebase --onto <base>
  <sha> <branch_name>`. Passing a branch argument checks it out in `repo_root`.

**Correction:** the `AET_WORK_BASE_BRANCH` workaround described above is **not
present in this repository**. It was applied to the operator's local install
only. `create_worktree` still carries the literal default. Any fix must
therefore introduce the override rather than generalize an existing one.

**Correction:** the "orchestrator ignores only four queue sidecars" claim is
accurate but the ignore list lives in `check_main_hygiene`
(`worktree.py:346-351`), not in the orchestrator.

**Correction:** `aet-setup` does not silently omit the gitignore guidance — it
documents it in prose at `aet-setup/SKILL.md:365` and
`aet-setup/checklist.md:111`. Two problems remain: the guidance is prose that
nothing enforces, and **both lists omit `.agents/runs/`** — the exact path that
tripped the hard-stop. `references/README.md:47` omits the queue sidecars too.

**Additional hardcoding #1 — `remove_worktree` (`worktree.py:154`).** Cleanup
counts commits with `git rev-list --count main..HEAD` and only removes the
worktree when that count is zero. On a non-`main` base every task worktree
appears "ahead", so cleanup silently refuses and `.worktrees/` accumulates for
the whole run. Not in the original report; same bug class.

**Additional hardcoding #2 — `is_ancestor_of_main` (`aet_state.py:69-73`).**
State derivation itself is trunk-bound: `merge-base --is-ancestor <ref>
origin/main`. Consequence is more serious than telemetry drift — `derive_status`
(`aet_state.py:181-185`) decides `merged` from this, so on a `dev`-based repo a
genuinely merged task can never derive as `merged`, and its dependents never
unblock. This is the deepest of the hardcodings and the one most likely to be
missed, because it sits behind the state machine rather than in the git plumbing.
