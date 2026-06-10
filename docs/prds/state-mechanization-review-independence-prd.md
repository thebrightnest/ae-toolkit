# PRD: State Mechanization and Review Independence

## Overview

Ten workflow audit issues trace to one cause: agents maintaining a three-headed state store (plan footers + PRD footers + queue JSON) by following prose. Stale `worktree` fields, invented statuses, done-without-merge, artifacts staged — all because state is asserted, not derived, and mutated by hand.

This PRD creates **`aet-state`**, a Python helper that owns all state mutations. It derives status from ground truth (git, files, branches), validates legality (cannot set `merged` without ancestry check), and updates footers and queue atomically. It also enforces reviewer independence by requiring the review step to work from disk artifacts in a fresh context.

## Goals

1. **Create `aet-state` helper** — a Python script (standard library only) that owns queue mutations, stage transitions, and footer updates.
2. **Derived status from ground truth** — status is computed, not stored: plan file exists → planned; branch exists → in-progress; `git merge-base --is-ancestor` → merged; worktree dir present → has worktree. JSON only stores the DAG and `abandoned` + reason.
3. **Legality validation** — `aet-state` rejects illegal transitions (e.g., `merged` without running the ancestry check itself).
4. **Atomic updates** — footers and queue JSON update together, not separately.
5. **Reviewer independence** — `aet-review` in `aet-pipeline-implement` works from disk artifacts only (diff + plan), ideally in a fresh subagent/session, never from the implementing conversation's memory.

## Non-Goals

- Replacing `.agents/work-queue.json` with GitHub Issues. The queue stays local-first; GitHub is an optional adapter (see PRD 1 non-goals).
- Rewriting the orchestrator. `aet-state` is a helper script, not a new runtime.
- Changing the plan/PRD footer format. We keep the existing `*Stage:` convention; `aet-state` writes it.

## User Stories

- As an agent operator, I want the queue to always reflect reality so `status` doesn't lie about merge-verified when git says otherwise.
- As a task author, I want to set a state and know the tool validates it's legal, rather than hoping I followed the prose correctly.
- As a reviewer, I want to review code from a clean context with no memory of the implementation conversation, so bias can't leak.

## Acceptance Criteria

- [ ] `scripts/aet-state.py` exists with standard-library-only Python.
- [ ] `aet-state` commands: `transition`, `derive`, `validate`, `sync-footers`.
- [ ] `derive` recomputes all non-declarative status fields from git/filesystem ground truth.
- [ ] `transition` validates legality before applying (e.g., rejects `merged` without ancestry check).
- [ ] `sync-footers` updates plan and PRD footers atomically with queue JSON.
- [ ] `aet-work/SKILL.md` updated to call `aet-state` instead of direct JSON mutation.
- [ ] `aet-pipeline-implement/SKILL.md` updated to run `aet-review` from disk artifacts, ideally in a fresh subagent.
- [ ] `aet-state` includes a `--dry-run` flag for safe testing.

## Open Questions

1. Should `aet-state` be invoked by skills directly, or wrapped in Make targets (e.g., `make state-transition STAGE=merged`)?
2. Should the reviewer independence mechanism be a fresh subagent (requires subagent support) or a context-clear instruction?
3. How do we handle the migration of existing queues with stale/invented statuses — auto-repair on first run or manual cleanup?

---

_Stage: scope-validated_
_Validated: 2026-06-10_
_Notes: No conflicts. Python helper (aet-state.py) aligns with PRD 5's Python build system direction. Reviewer independence requires subagent support — if unavailable, falls back to context-clear instruction._
