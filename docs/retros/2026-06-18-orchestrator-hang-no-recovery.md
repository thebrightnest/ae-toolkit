# Retro: 2026-06-18 — Orchestrator Hangs After Tasks Complete

## What Went Well

- The `kimi` CLI flag fix (`-p` without `--yolo`) allowed the orchestrator to spawn subagents successfully.
- All three queued tasks (`aet-work-state-refactor-status-next-plan`, `aet-work-state-refactor-sync-init-plan`, `aet-validate-scope-closure-discipline-plan`) advanced through their pipeline stages and committed work.
- The queue was updated to `done` for each task, so the work itself was not lost.

## What Went Wrong

- **The orchestrator process hung after marking all tasks complete.** The output log stopped advancing; the summary footer (`🏁 Orchestrator finished...`) never printed. The parent process had to be killed manually.
- **No built-in timeout or watchdog.** A stuck subprocess (or a stuck polling loop) can run indefinitely with no automatic recovery.
- **No heartbeat or progress telemetry.** There was no way to tell from logs whether the orchestrator was still working, waiting on a subprocess, or deadlocked.
- **Worktrees and branches were left behind.** Because the orchestrator was killed rather than exiting cleanly, the completed task worktrees were not removed automatically.

## Root Cause

The orchestrator's batch loop (`run_batch` in `aet-work/bin/orchestrator`) trusts that every spawned subprocess will exit and that the loop will reach the summary print. It has:

- No per-task wall-clock timeout.
- No heartbeat logging while polling.
- No forced cleanup/final summary on abnormal exit.
- No upper bound on total batch runtime.

This means any subprocess that does not exit cleanly (or any logic path that prevents the loop from breaking) turns the orchestrator into a silent zombie.

## Learnings

- **Long-running batch orchestrators need a heartbeat.** Silence for minutes is indistinguishable from a hang.
- **Every spawned subprocess needs a timeout.** Trusting external CLI tools to always exit is brittle.
- **Cleanup and summary must be guaranteed.** Use `finally` blocks or context managers so worktrees are removed and telemetry is written even when the orchestrator is interrupted.

## Action Items

- [ ] **Add per-task timeout and watchdog to `aet-work/bin/orchestrator`.** Enforce a default max runtime per task (e.g., 30 minutes), log a heartbeat every N poll cycles, and kill + mark failed any task that exceeds its budget. — @agent — 2026-06-18
- [ ] **Add a total batch timeout and graceful shutdown.** Cap the entire `run_batch` loop and ensure the summary/footer is always printed. — @agent — 2026-06-18
- [ ] **Record learning in `.agents/learnings.jsonl`** with triggers `orchestrator`, `hang`, `timeout`, `watchdog`, `subprocess`. — @agent — 2026-06-18
