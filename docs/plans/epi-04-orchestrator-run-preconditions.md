---
id: epi-04-orchestrator-run-preconditions
size: M
blocked_by: [epi-01-base-branch-resolver]
pipeline: standard
status: merged
security_review: skipped
security_review_reason: writes .gitignore entries during setup and changes an error path; no network, credential, or privileged write surface
docs_sync: required
docs_sync_reason: aet-setup prose lists of ignored paths are corrected and made consistent with what the code writes
---

# Plan: Stop the orchestrator failing on its own preconditions

## Context

- PRD: `docs/prds/non-trunk-integration-workflow-prd.md` (R-6, R-8, R-9)
- ADR: `docs/adr/044-base-branch-is-configured-not-assumed.md` (decisions 3, 4)
- Bug: `docs/bugs/2026-07-22-orchestrator-base-branch-hardcoded.md`

Two preconditions AET imposes on itself and then fails: it halts on files it
wrote, and it requeues a task that can never succeed. Both are what turned a
configuration problem into a cost problem.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] If a reproducible defect was described, redirected to `aet-bug-report`

The dirty-tree hard-stop is a reproducible defect from the bug report. It is
planned with R-6 because both are "the orchestrator's own run preconditions" and
share the failure surface.

## Locked design

- **One ignore constant.** The list in `check_main_hygiene`
  (`src/aet/worktree.py:346-351`) becomes a single shared constant that both the
  hygiene gate and `aet setup` read. Restating the list per call site is how
  `.agents/runs/` came to be in one place and not the other.
- **`.agents/runs/` is in the list.** It is the telemetry directory the
  orchestrator itself creates, and its absence is what tripped ADR-027's
  hard-stop on a first run.
- **`.worktrees/` is in the list too.** `create_worktree` writes it inside
  `repo_root` (`src/aet/worktree.py:24`); this repository gitignores it, but a
  fresh repository does not, and untracked worktree contents trip the same
  gate. The task audits every in-repo path AET writes against the constant
  (PRD R-8).
- **`aet setup` writes the entries.** Prose in a checklist is not a mechanism —
  the incident is the evidence. Writing is idempotent: never duplicate an entry
  that is already present, never reorder or rewrite unrelated lines.
- **Three prose lists are corrected to match**, not just one:
  `aet-setup/SKILL.md:365` and `aet-setup/checklist.md:111` omit
  `.agents/runs/`; `aet-setup/references/README.md:47` omits the queue sidecars
  too. They must agree with the constant.
- **R-6 halts, it does not requeue.** A base that lacks the plan file is a
  misconfiguration, not a flaky task. ADR-027's "halt rather than churn"
  reasoning applies. The message names three things: the resolved base, the
  expected plan path, and the override (`--base` / `AET_WORK_BASE_BRANCH`).
- The current message ("base may be stale; ensure the plan is committed and
  pushed to origin/main") is wrong twice: it names a branch that may not be the
  base, and it suggests staleness when the real cause is usually a base that
  never contained the plan.

## Task List

1. ✓ Extract the ignored-paths list into one shared constant covering the queue
   sidecars, `.agents/runs/`, and `.worktrees/`, audited against every in-repo
   path AET writes, read by the hygiene gate — S (traces: R-8)
2. ✓ Write the ignore entries to `.gitignore` in `aet setup`, idempotently
   — M (traces: R-9) [Changed: exposed through a dedicated `aet setup bootstrap`
   subcommand rather than the main setup flow]
3. ✓ Correct the three `aet-setup` prose lists to match the constant
   — S (traces: R-9)
4. ✓ Halt instead of requeueing when the resolved base lacks the plan file,
   naming base, expected path, and override — M (traces: R-6)
5. [Deferred: merge happens at the ship/merge stage] Merge branch to main and
   verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 100 lines; M ≤ 1 day / ≤ 200 lines; L must be
re-evaluated.

### Batching Check

- [x] Not one of several near-identical additions — an ignore-list mechanism and
      a failure-path change, batched by shared surface
- [x] The diff is expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with `epi-02` — `epi-02` is a rename sweep; mixing a
      behavioral halt into it would obscure both

## Rejected Alternatives

- **Document the ignore entries harder** — rejected: they are already documented
  in two places and it did not prevent the incident. The mechanism is the fix.
- **Have the orchestrator write `.gitignore` on first run** — rejected: the
  orchestrator runs unattended under ADR-027 and should not mutate tracked files
  as a side effect. Setup is the explicit, attended moment.
- **Ignore all of `.agents/` in the hygiene gate** — rejected: it would mask
  genuine dirt in tracked AET files such as `.agents/aet-work.json`.
- **Requeue R-6 failures a bounded number of times** — rejected: the retry
  cannot change the outcome, so any bound above zero is money spent on a
  certainty.
- **Auto-detect and switch to a base that contains the plan** — rejected: it
  guesses where the operator's work belongs, and a wrong guess pushes commits to
  a branch they did not choose.

## Files to Modify

- `src/aet/worktree.py`
- `src/aet/cli/setup.py`
- `src/aet/cli/orchestrator.py`
- `skills/aet-setup/SKILL.md`
- `skills/aet-setup/checklist.md`
- `skills/aet-setup/references/README.md`
- `tests/setup/test_gitignore_entries.py` (new)
- `tests/orchestrator/test_missing_plan_halts.py` (new)

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] New source coverage: `tests/setup/test_gitignore_entries.py` asserts every
      constant entry is written, that re-running adds no duplicates, and that
      unrelated existing lines are untouched
- [ ] New source coverage: `tests/orchestrator/test_missing_plan_halts.py`
      asserts the run halts, the message names base / expected path / override,
      and the task's requeue count does not increase — demonstrated **failing**
      against the current requeue behavior
- [ ] A repo with no AET entries in `.gitignore` reaches task execution rather
      than halting on `.agents/runs/`
- [ ] The constant covers `.worktrees/` and every in-repo write path found in
      the audit; the prose lists agree with it, verified by reading them side
      by side
- [ ] R-trace coverage: R-6 by task 4; R-8 by task 1; R-9 by tasks 2–3
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. Ignore entries already written to a project's `.gitignore`
remain and are harmless. The halt reverts to a requeue, restoring the loop.

## Pipeline

`standard`.

---

*Stage: merged*
