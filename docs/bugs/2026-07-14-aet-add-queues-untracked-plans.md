# Bug Report: `aet add` queues plans that git does not track (non-durable sprint entries)

## Metadata

- **Reported:** 2026-07-14T14:12:48Z
- **Severity:** medium
- **Status:** fixed (Gap 1); follow-up planned (Gaps 2–3)

## Symptoms

`aet add` accepts a plan file with **zero** durability checking: an untracked
`docs/plans/*.md` enters `.agents/work-queue.json` and shows up in `aet status` as
a normal `ready`/`blocked` task. Because aet-work builds task worktrees from
`origin/main`, a queued-but-uncommitted (or unpushed) plan is absent in the
worktree — the run spawns an **empty worktree** and the plan "goes missing." Same
failure class as `docs/bugs/2026-06-18-orchestrator-untracked-adr-not-copied-to-worktree.md`.

Observed live this session: five freshly-created, **untracked** plans
(`docs/plans/vgr-0*.md`) were added via `aet add` and appeared in `aet status`,
all while untracked in git. They were only committed later, manually.

## Reproduction Steps

1. From a clean checkout, create a plan file but do **not** `git add` it:
   `docs/plans/x-demo.md`.
2. Run `aet add docs/plans/x-demo.md`.
3. **Before fix:** `✓ Added x-demo.md to the queue as ready` — an untracked plan is
   now a sprint task. In unattended mode, `aet run-one` then builds a worktree off
   `origin/main` that lacks the plan.

## Root Cause

Three independent gaps; **Gap 1 is fixed here**, Gaps 2–3 are routed to `aet-plan`.

- **Gap 1 (fixed) — no durability guard at intake.** `aet-work/bin/add:main()`
  validated stage, queue integrity, duplicates, and settled-history but **never**
  checked git state, so an untracked file passed straight through.
- **Gap 2 (follow-up) — hygiene is downgraded to a warning in unattended mode.**
  `enforce_main_hygiene` (`aet-work/bin/orchestrator:192`) calls the real check
  `check_main_hygiene` (`aet-work/lib/worktree.py:335`, which correctly fails on a
  dirty tree _and_ on `main` ahead of `origin/main`), but in
  `AET_EXECUTION_MODE=unattended` it prints `⚠️ … Continuing` and returns `True`.
  So the AFK path proceeds despite an unpushed/dirty main — this is where plans
  actually go missing. **Correction to the initial hypothesis:** `run_single`
  (run-one) does _not_ skip the check (`orchestrator:1515`); the earlier
  "run-one skips hygiene" framing was from a stale note and is wrong.
- **Gap 3 (follow-up) — the planning pipeline never commits plans.**
  `aet-pipeline-plan` Step 3 / `aet-plan` run `aet add`/`aet sync` with no commit
  step, so the happy path leaves plans uncommitted through intake.

Why existing checks didn't catch it: the durability guard belongs at the
`aet add` boundary (missing entirely), and the execution-side guard exists but is
deliberately softened in the exact mode (unattended/AFK) where it matters most.

## Fix Summary

Fail closed at the intake boundary (Gap 1), the tightest fix that directly answers
"enforce committed plans before adding."

- **Files modified:** `aet-work/bin/add`, `tests/test_aet_work_add_review.py`
- **Key change:** `aet add` now refuses a plan file that is inside a git work tree
  but untracked, with a message pointing to committing it first; a new
  `--allow-untracked` flag escapes the guard for throwaway spikes.
- **Design choices / side effects:** the bar is **tracked** (in the index), not
  "committed & clean" — this preserves the plan-authoring/edit loop, and the
  deeper _pushed-to-origin/main_ guarantee remains the execution-side check. The
  guard **no-ops when the plan is not inside any git repository** (nothing to
  enforce), so ad-hoc/out-of-VCS usage and the existing non-git test fixtures are
  unaffected. Only new behavior: untracked adds inside a repo are refused.

## Regression Test

Added to `tests/test_aet_work_add_review.py`:

- `test_add_refuses_untracked_plan_in_git_repo` — untracked plan in a `git init`
  repo is refused (rc 1), queue stays empty.
- `test_add_accepts_tracked_plan_in_git_repo` — a staged/tracked plan queues normally.
- `test_add_allow_untracked_bypasses_guard` — `--allow-untracked` queues a spike.

## Validation

- `ruff check` clean on both files.
- `tests/test_aet_work_add_review.py`: 27 passed (24 existing + 3 new).
- Queue-adjacent regression (`test_queue`, `test_queue_guard`, `test_init_queue_sync`): 78 passed.
- Full suite: **631 passed, 34 subtests** (no regressions).
- Live: an untracked probe plan was refused (rc 1) and never entered the queue;
  a tracked plan (`vgr-01`) passed the guard.
- **Trust boundary (aet-cso):** not invoked — this is an additive intake-integrity
  guard with no auth/secret/data surface; it only strengthens what may enter the queue.

## Follow-up (routed to `aet-plan`)

- **Gap 2:** make `enforce_main_hygiene` fail closed in unattended mode for the
  plan-durability-critical conditions (dirty tree / `main` ahead of `origin/main`),
  rather than warn-and-continue — behavior change to the AFK contract.
- **Gap 3:** add an explicit "commit the plans" step to `aet-pipeline-plan` /
  `aet-plan` before `aet add`, so the happy path is correct by construction.
