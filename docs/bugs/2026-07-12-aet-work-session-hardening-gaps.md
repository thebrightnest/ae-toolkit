# Bug Report: aet-work session-hardening gaps — integrity refusals, hygiene sidecars, backgrounded validations

## Metadata

- **Reported:** 2026-07-12
- **Severity:** medium
- **Status:** resolved

## Symptoms

Reported from an aet-work orchestration session, three gaps:

1. **content_hash brick, still uncatchable from the user's seat.** ADR-024
   made `aet state audit` / `heal --apply` the recovery path, but every other
   queue-loading entry point — `next`, `sync`, `add`, `init-queue`, and the
   orchestrator's batch startup — still died with an uncaught
   `QueueIntegrityError` traceback. The traceback names the remedy, but a
   batch that crashes on startup reads as "unrecoverable" even when it is not.
2. **Lock file not in the hygiene ignore list (nor cleaned on crash).**
   `check_main_hygiene` ignored only `work-queue.json` and
   `work-history.jsonl`. The `work-queue.json.lock` sidecar lingers on disk
   after every run (and after a crash), so projects without it gitignored saw
   the orchestrator halt on "Working tree is dirty". The `work-queue.lease`
   sidecar had the same visibility problem.
3. **Stage agent backgrounding its own validations produces zero commits.**
   The one-shot stage prompts never required foreground validation: an agent
   that started validations as background tasks and ended its turn killed
   them before completion and never committed — the orchestrator then saw a
   "successful" session with no commits.

## Root Cause

1. The ADR-024 fix (`7fe0f4b`) wrapped `aet-state main()` but not the other
   bins that load the queue through the same verified path.
2. The lock file is intentionally never unlinked — deleting an fcntl lock
   file on release races with concurrent openers (a waiter on the unlinked
   inode and a new opener of a fresh file would hold "the" lock
   simultaneously). Since the file must persist, it must be ignored: in
   `check_main_hygiene` and in project `.gitignore` templates (aet-setup's
   template and checklist listed neither sidecar). The lease already
   self-reclaims on the next mutation when its PID is dead; it only needed
   the same ignore treatment.
3. `build_prompt` and `build_stage_group_prompt` instructed "commit before
   exiting" but said nothing about validations running to completion in the
   foreground before that commit.

## Fix Summary

- Files modified:
  - `aet-work/bin/next`, `bin/sync`, `bin/add`, `bin/init-queue` — catch
    `QueueIntegrityError` at the first `backend.load()` and return 1 with a
    one-line refusal naming `aet state audit` / `aet state heal --apply`
  - `aet-work/bin/orchestrator` — same guard on the batch startup load (no
    worktrees spawned against a tampered queue); `build_prompt` and
    `build_stage_group_prompt` now require foreground validations that run to
    completion before the commit-and-exit step
  - `aet-work/lib/worktree.py` — `check_main_hygiene` ignores
    `.agents/work-queue.json.lock` and `.agents/work-queue.lease`; docstring
    records why the lock file is never unlinked
  - `aet-setup/SKILL.md` gitignore template and `aet-setup/checklist.md` —
    both sidecars added to the generated-artifacts ignore list
  - `aet-work/references/queue-commands.md` — dirty-check documentation
    covers the sidecars
- Regression tests:
  - `tests/test_queue_guard.py` — clean-refusal tests for `next`, `sync`,
    `add`, `init-queue` on a tampered queue (rc 1, remedy named, no
    traceback)
  - `tests/test_worktree.py` — sidecars ignored by hygiene; unrelated
    untracked files still fail (control)
  - `tests/test_orchestrator.py` — both prompt builders require foreground
    validations; `run_batch` refuses cleanly on a tampered queue

## Validation

- [x] Targeted suites pass: `test_queue_guard`, `test_worktree`,
      `test_orchestrator`, `test_init_queue_sync`,
      `test_aet_work_add_review`, `test_aet_work_read_side` — 172 tests green
- [x] Full `make validate` green (lint, format, ruff, pytest, workflow lint,
      skill-structure validator)

## Lessons Learned

- A fail-closed guard is only as good as its noisiest caller: every entry
  point that can hit the guard needs the same clean-refusal treatment, not
  just the one the original bug report named.
- Sidecar files that must persist for correctness (lock files) have to be
  part of the hygiene contract everywhere — the dirty check, the setup
  templates, and the docs — or they will eventually brick a clean-tree gate.
- One-shot agent prompts must state ordering constraints explicitly:
  "commit before exiting" does not imply "wait for your validations"; agents
  will background long-running checks unless told not to.
