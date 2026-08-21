---
subject: settled-ness
---

# Plan Documents Are Outside the Durability Gate

## Status

Accepted (2026-08-05). Narrows ADR-027 (Main Hygiene Halts Unattended Runs) for
plan paths and revises ADR-034 (Settled-ness Is Derived from Versioned Plan
Data) decision 3. Implements the `local-only-plans` PRD
(`docs/prds/local-only-plans-prd.md`).

## Context

`aet run` refuses to start unless every queued plan is committed and pushed.
Two mechanisms enforce it:

- `aet sprint add` refuses an untracked plan (`src/aet/cli/sprint.py:127`) and
  then calls `commit_and_push_status` unconditionally (`:172`), so even
  `--allow-untracked` publishes the plan.
- `check_base_hygiene` (`src/aet/worktree.py:445`) reports "Working tree is
  dirty" for any untracked `docs/plans/*.md`, and halts when the integration
  branch is ahead of origin regardless of what those commits touch.

ADR-027 introduced the hygiene hard-stop to fix one concrete bug: plans queued
against an unpushed working tree silently went missing, and the run built an
empty worktree off `origin/main`. Its Alternatives section rejected a surgical
per-plan presence check as "more code for the same coverage" — an **economy**
argument, not a safety one.

That economy no longer holds, because the surgical mechanism now exists and is
already partially built:

- `copy_untracked_files` (`worktree.py:255`, called at
  `src/aet/cli/orchestrator.py:1226`) mirrors untracked planning documents into
  the task worktree **before** the plan-existence check at `:1260`. An untracked
  plan already reaches the agent. The docstring on `plan_is_untracked`
  (`sprint.py:49-56`) still justifies the refusal by saying an untracked plan
  "yields an empty worktree" — that justification is obsolete.
- `MissingPlanError` (`orchestrator.py:1260`) already halts loudly when the plan
  is genuinely absent, rather than proceeding on an empty worktree.
- All plan discovery is filesystem-based (`plans_dir.glob("*.md")` in
  `init_queue.py:218`, `plans.py:51`, `sync.py:53`, `plans_lint.py:26`); nothing
  reads plan content through git objects or origin refs.
- `working_tree_hash` (`src/aet/verifier.py:81-121`) stages untracked files via
  `git add -A`, so verdict evidence already covers untracked plans.

ADR-027 and ADR-045 both defend the durability of **agent-produced code on
unpushed branches** — ADR-045 explicitly requires pushing the integration branch
on every integration for exactly that reason. Neither addresses a plan document.
The two are different in kind: code is hours of agent output that cannot be
recreated, while a plan is an operator-authored execution script regenerable
from its PRD.

The residual durability exposure is also smaller than it appears. The only thing
deferred is a non-terminal `status` marker on the plan file mid-sprint, and the
queue that mirrors it (`.agents/work-queue.json`) is already gitignored per
ADR-013 — mid-sprint liveness was never durable across clones. ADR-034's real
guarantee, that settled-ness derives from committed plan data, is written at
**closure**, which is unaffected.

## Decision

Plan documents (`docs/plans/`) are outside the durability class that ADR-027
protects. Durability for a plan is deferred to the PR that carries it.

1. **Base hygiene classifies paths, not counts.** Paths under `docs/plans/` do
   not trip the dirty-tree check. The ahead-of-origin check passes only when
   *every* diverging path is under `docs/plans/`; a commit mixing a plan and a
   source file remains a violation. Hygiene stays fail-closed in both execution
   modes for every other path — ADR-027's contract is narrowed in scope, not in
   strictness.
2. **Durability is gated on status terminality, not on path alone.**
   `commit_and_push_status` (`src/aet/queue.py:685`) serves both intake
   (`status: queued`) and closure (`status: merged`). For a plan path it writes
   the file only for non-terminal statuses, and commits and pushes for terminal
   ones (`merged`, `abandoned`). This is the single point of control; callers
   stay ignorant of the rule.
3. **The plan travels with its PR.** The task branch's first commit adds the
   task's own plan file by explicit path, skipped when the plan already exists
   on the integration branch. Intent and implementation land in one diff.
4. **Correction replaces prevention.** The always-on worktree overlay plus a
   fail-closed plan resolution replaces ADR-027's preventive gate for plan
   paths. The gate forbade the state; the overlay makes the state work and halts
   loudly when the plan is genuinely absent.
5. **This is behavior, not a mode.** There is no config key, CLI flag, or env
   var. At plans-only scope nothing load-bearing is deferred, so there is no
   second posture worth a second code path.

This revises **ADR-034 decision 3** ("Status writes are committed and pushed").
Terminal status writes remain committed and pushed; non-terminal status writes
on plan paths do not. ADR-034's decision 4 (the queue remains an ephemeral
cache) is unaffected. ADR-034's decisions 1 and 2 (plan `status` as the
authoritative liveness signal, and `init-queue` reading plan status rather than
history) were superseded by **ADR-055**: the `status` field left the plan
contract, and settled-ness is now derived by the Settled-ness Authority.

Scope is `docs/plans/` only. PRDs, ADRs, audits, retros, and product-briefs keep
today's posture, and `copy_untracked_files`' six-directory untracked mirror is
unchanged.

## Consequences

- **Easier:** A plan goes from `aet sprint add` to merged PR with no
  intermediate commit. Reviewers see intent and implementation in one diff.
- **Easier:** The implementing agent provably reads the latest local plan text,
  because the overlay syncs by content and git state stops being an input.
- **Easier:** ADR-027's originating bug is closed more precisely than before —
  the plan reaches the worktree, and an absent plan halts loudly.
- **Harder:** An uncommitted plan is lost on machine failure. Bounded: one
  non-terminal status marker on a regenerable script, in a system whose queue
  was already gitignored.
- **Harder:** Preventive strictness is genuinely reduced for every user,
  night-shift included. The mitigation is a regression obligation, not a
  promise: the overlay and the fail-closed resolution carry mandatory tests
  covering the empty-worktree scenario ADR-027 was written for.
- **Harder:** `remove_worktree`'s emptiness test can no longer be a commit
  count, because the seeded plan commit makes every worktree non-empty. It
  becomes a changed-path classification.
- **Neutral:** `aet sprint add` loses `--allow-untracked`. Untracked is the
  normal case, so a flag asserting it no longer gates anything.

## Relation to ADR-027 and ADR-045

ADR-027 is narrowed, not overturned: mechanical durability remains a
fail-closed hard-stop in unattended mode for every path outside `docs/plans/`.
ADR-045 is untouched — its requirement that the integration branch be pushed on
every integration concerns agent-produced code and still holds. This ADR draws
the line those two never needed to draw, between code whose loss is
unrecoverable and documents whose loss is not.

## Alternatives Considered

1. **A `plan_durability: committed|local` config toggle** — Rejected. At
   plans-only scope nothing load-bearing is deferred, so `committed` mode would
   preserve a posture with no defender. Costed at roughly 13 files by the
   `integration_mode` precedent (4 source, 9 test) for no delivered behavior,
   and the project does not keep backward-compatibility paths.
2. **Widen the scope to all six planning directories** — Rejected. PRDs and
   ADRs are intent documents whose loss is not cheaply recoverable, and the
   operator's workflow already commits them. Wider scope also worsens the
   leak risk in decision 3, where more untracked documents sit in the worktree
   at commit time.
3. **Gate `commit_and_push_status` on path alone** — Rejected. It would disable
   closure's durability write, since closure writes `merged` to the same paths.
4. **Remove the ahead-of-origin check entirely** — Rejected. It protects against
   building a worktree off a stale `origin` when local commits contain code.
5. **Base worktrees on local refs instead of `origin/<ref>`** — Rejected. It
   contradicts ADR-044/045 and would change the branch model to solve a document
   visibility problem that a copy solves.
6. **Keep the gate and have `aet sprint add` auto-commit silently** — Rejected.
   It is today's behavior with the refusal hidden; the operator still gets
   bookkeeping commits on the integration branch before any code exists.

## Addendum (2026-08-11): gitignored live plans require force-add

Repos may ignore `docs/plans/*.md` so transient live plans stay out of
`git status` (this repo does, `.gitignore:24`). Gitignore rules still apply
inside task worktrees, so every code path that stages a plan path by explicit
name must use `git add -f`. Both known paths do: closure/archival
(`src/aet/queue.py`, fixed in `95fb26e`) and the task-branch seed
(`seed_task_plan`, `src/aet/worktree.py`, fixed the same day the gap
quarantined `t2r-07`). Seed failures now also record an `environment` failure
signature with stage `seed`, so triage sees the real cause instead of an empty
signature. Any future plan-path staging must follow the same rule.
