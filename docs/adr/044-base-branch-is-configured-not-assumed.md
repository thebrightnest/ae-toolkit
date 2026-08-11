---
subject: base-branch
---

# The Base Branch Is Configured, Not Assumed

## Status

Accepted. Generalizes the trunk assumption embedded in ADR-027 (main hygiene
halts unattended runs) and ADR-029 (autonomous merge is a fail-closed gate).
Prerequisite for ADR-045. Motivated by
`docs/bugs/2026-07-22-orchestrator-base-branch-hardcoded.md` and
`docs/bugs/2026-07-22-queue-reset-dead-end.md`.

## Context

AET assumes the literal branch name `main` in seven places. The assumption was
never a decision — it is a default that spread by copy, and no ADR records it.

Two of the seven are in git plumbing and were reported:

- `worktree.py:16` — `create_worktree(..., base_branch="origin/main")`. All
  three orchestrator call sites (`orchestrator.py:1042`, `:2036`, `:2332`) pass
  no override, so the default always wins. No flag, env var, or config key
  changes it.
- `worktree.py:377`, `:386` — `check_main_hygiene` gates on `origin/main..main`
  and `main..origin/main`.

Three more were found while verifying the report:

- `orchestrator.py:428`, `:437` — `_session_diff_stats` diffs `main...HEAD`, so
  on a non-`main` base every task's telemetry absorbs the entire base-vs-`main`
  delta.
- `worktree.py:154` — `remove_worktree` counts `main..HEAD` and removes the
  worktree only when the count is zero. On a non-`main` base every worktree
  looks "ahead", so cleanup silently refuses and `.worktrees/` grows for the
  whole run.
- `aet_state.py:69-73` — `is_ancestor_of_main` resolves against `origin/main`.

The last one is the important one, and it is why this is an ADR rather than a
find-and-replace. `derive_status` (`aet_state.py:181-185`) decides `merged`
from `is_ancestor_of_main`. In a repository whose trunk is not `main`, a task
that genuinely merged can never derive as `merged`; ADR-011's forward-only
state never records the terminal transition, dependents never unblock, and
`aet state heal`'s primary repair (`aet_state.py:518`) is unreachable. The
assumption is not confined to git plumbing — **it has reached the state
machine**, where its failure mode is a silent deadlock rather than an error.

The immediate consequence is that AET cannot run in a repository whose plans
live anywhere but trunk. Worktrees are cut from a base that does not contain
the plan file, every task fails with `Plan not found in worktree`, and under the
default `--on-failure triage` the queue requeues them in a loop — spawning agent
sessions that cost money and cannot make progress. The failure is loud per task
and invisible as a pattern.

Two further defects surfaced in the same incident. They are not "wrong branch
name" bugs, but they are the reason the incident was unrecoverable rather than
merely blocked, so they are recorded here:

- **Worktree refresh hijacks the operator's checkout.** `worktree.py:120` runs
  `git -C <repo_root> rebase --onto <base> <sha> <branch_name>`. Passing
  `rebase` a branch argument makes git check that branch out *in `repo_root`*
  first. `repo_root` is the operator's own working tree. In the incident it
  switched the operator off their feature branch onto a task branch and replayed
  11 unrelated commits. This is a plain bug at any branch name; a non-trunk base
  merely makes the divergence that triggers it routine.
- **The orchestrator trips its own dirty-tree hard-stop.** `check_main_hygiene`
  ignores four queue sidecars (`worktree.py:346-351`) but not `.agents/runs/`,
  which the orchestrator itself writes. ADR-027 then halts the run. `aet-setup`
  documents the ignore list in prose (`SKILL.md:365`, `checklist.md:111`) and
  that prose omits `.agents/runs/`; `references/README.md:47` omits the queue
  sidecars as well.

## Decision

**The branch AET builds on is resolved configuration. No code path names a
branch literally.**

### 1. One resolver, one precedence chain

A single resolver returns the refs every consumer uses. Nothing computes a base
independently.

- **`trunk_branch`** — the final merge target. Resolution order: config value →
  `git symbolic-ref refs/remotes/origin/HEAD` → `main`. Detection means a repo
  on `dev`, `master`, or `trunk` works unconfigured.
- **`integration_branch`** — the branch task worktrees are cut from and
  integrate into. Resolution order: `--base` flag → `AET_WORK_BASE_BRANCH` env →
  config `integration_branch` → `trunk_branch`.

`trunk_branch` and `integration_mode` (ADR-045) are **project configuration**
and resolve through the existing external-first chain established by ADR-036
and `backends/factory.py:59` — `AET_WORK_CONFIG` → `~/.aet/{slug}/config.json`
→ `.agents/aet-work.json` → defaults.

`integration_branch` is **not** project configuration. A project has one trunk
but many epics over its life, so the integration branch is per-ticket state. It
is therefore a per-run input (flag or env) that falls back to trunk. Putting it
in the config file would mean editing an external, gitignored, unreviewable file
on every new ticket. The config key exists as the lowest-precedence fallback for
a repo that genuinely has a long-lived integration branch — it is not the
expected way to set it.

### 2. Every consumer reads the resolver

`create_worktree`, `remove_worktree`, `_session_diff_stats`, and
`is_ancestor_of_main` take the resolved refs. `check_main_hygiene` becomes
`check_base_hygiene(integration_branch, trunk_branch)`. Per the project's
no-backward-compat rule, these are renames and signature changes, not aliases.

`is_ancestor_of_main` is renamed to name what it checks rather than which branch
it once checked. Its rename is the substantive one: it moves trunk-awareness
out of the state machine and into resolved configuration.

### 3. A base that lacks the plan fails fast, once

When the resolved base does not contain the task's plan file, the orchestrator
reports the resolved base, where the plan was expected, and how to override —
and does **not** requeue. This failure is a misconfiguration, not a flaky task,
and ADR-027's "halt rather than churn" reasoning applies: a run that cannot
succeed must stop, not loop.

### 4. The orchestrator's own artifacts never fail its hygiene gate

The ignore list covers every path AET writes, `.agents/runs/` included, and is
derived from one shared constant rather than restated per call site. `aet setup`
**writes** these entries to `.gitignore` as code. Prose in a checklist is not a
mechanism; the incident is the evidence.

### 5. Worktree refresh never checks out a branch in `repo_root`

Refresh operates inside the task worktree, or moves refs with `git branch -f` /
`git update-ref`, which require no checkout. No AET code path may run a git
command in `repo_root` that changes `HEAD` there. The operator's working tree is
not AET's to move.

### 6. Queue regeneration is scoped to the plans it is asked for

ADR-013 makes the queue safe to lose because it can be regenerated from plans.
`init_queue.py` breaks that guarantee: it validates the whole `plan_files` set
and returns `1` on any finding (`:230-238`) **before** the per-plan
`is_settled_plan` skip at `:253` and the `is_sprint_member` skip at `:260`. A
plan it would have skipped anyway still aborts the rebuild. In a shared
repository — where `docs/plans/` holds other people's features, which this
operator will never fix — the queue becomes unregenerable, and it is gitignored
so it cannot be restored from git either.

Validation is scoped to the plans being included. Invalid siblings are warned
and skipped. **The queue file is never left unwritten because of a plan the
caller did not ask to include.**

### 7. A task can be un-started

`aet state heal` gains the missing rule, and a task-level reset primitive
exists. The heal gap is precisely two lines: `cmd_heal` matches `derived==ready`
against `stored ∈ {failed, blocked, planned}` (`aet_state.py:526`) and
`derived==failed` against `stored==in_progress` (`:533`). The incident state was
`derived ∈ {ready, blocked}` with `stored == in_progress`, which matches
neither, so heal correctly computed the discrepancy and then had no rule that
consumed it — reporting "No healable discrepancies found" while the queue was
visibly wrong. Heal must also clear `branch` and `worktree`; nothing in
`aet_state.py` clears runtime fields today.

## Consequences

- **Easier:** AET runs in repositories whose trunk is `dev`, `master`, or
  `trunk`, with no configuration at all — detection covers it.
- **Easier:** Plans can live on a feature branch, which is what a shared
  repository's branching policy usually requires.
- **Easier:** A wedged queue is recoverable. Deleting it becomes a supported
  reset path rather than a one-way door.
- **Easier:** Telemetry, worktree cleanup, and merge detection stop disagreeing
  about what the base is, because there is one resolver.
- **Harder:** Five call sites and two function names change together. Anything
  reading `check_main_hygiene` or `is_ancestor_of_main` must be updated in the
  same change; a partial migration leaves two sources of truth, which is the
  condition this ADR exists to remove.
- **Risk:** `git symbolic-ref refs/remotes/origin/HEAD` is unset in some clones
  (it is written at clone time and can go stale after a default-branch rename).
  The `main` fallback preserves today's behavior, but a repo with an unset
  symbolic-ref and a non-`main` trunk will silently resolve to `main`.
  Mitigation: `aet setup verify` reports the resolved trunk and how it was
  derived, so the value is inspectable rather than inferred.
- **Neutral:** `AET_WORK_BASE_BRANCH` — the stopgap applied to the operator's
  local install during the incident — is adopted as the documented per-run
  override rather than discarded.

## Alternatives Considered

- **Env-var override only** (the shipped stopgap) — rejected as the durable
  answer. It fixes where worktrees are cut and nothing else. The state machine
  still cannot derive `merged`, cleanup still refuses, telemetry is still wrong,
  and the hijack still fires. It addresses the symptom that produced an error
  message and leaves the four that produce silence.
- **Find-and-replace `main` with a module constant** — rejected. A constant is
  still one value for two distinct concepts. Trunk and integration branch are
  the same ref only in the trunk-based case; collapsing them is exactly the
  conflation ADR-045 has to undo.
- **Put `integration_branch` in `.agents/aet-work.json`** — rejected as the
  primary mechanism. It is per-ticket state in a per-project file, and under
  ADR-036 that file is external and gitignored, so the edit is neither
  reviewable nor durable. Retained as the lowest-precedence fallback only.
- **Derive the integration branch from the operator's current branch** —
  rejected, and this was the closest call. It needs no configuration and is
  usually right. Rejected because it makes an implicit input decide where code
  lands: running the same command from a different checkout would silently
  target a different branch, and ADR-027 already establishes that the operator's
  branch state is a thing AET checks, not a thing AET reads intent from.
- **Require plans to be merged to trunk before running** — rejected. It forces
  planning documents through a protected-branch PR before implementation can
  start, which inverts the host repository's own workflow. AET does not get to
  dictate a team's branching policy as a precondition for being useful.
