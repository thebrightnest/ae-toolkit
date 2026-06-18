---
id: 2026-06-18-orchestrator-run-one-hardening
blocked_by: []
size: M
---

# Plan: Harden `run-one` — main-hygiene gate, plan-presence guard, unmaskable run outcome

## Context

Motivated by a real silent failure on 2026-06-18 while shipping `fods-02`: local `main` was 5 commits ahead of `origin/main` (the fods-02 plan lived in an unpushed commit), and `aet-work run-one` created a worktree from `origin/main` that **did not contain the plan file** — yet proceeded toward spawning an agent session with nothing to implement.

Root causes in `aet-work/bin/orchestrator`:

1. `run_single` never calls `check_main_hygiene` (only `run_batch` does, at `orchestrator:254`). A stale/ahead/behind local `main` therefore leaks a wrong base into run-one worktrees with no warning.
2. `process_task` does not verify the plan file is present in the worktree after creation; a missing plan silently defaults the stage to `plan-approved` (`read_plan_stage(...) or "plan-approved"`) and spawns a doomed session.
3. The orchestrator never writes telemetry, so `aet-work report` reads `.agents/execution.log.jsonl` — a log nothing populates. When the run is backgrounded through `tee`, the orchestrator's non-zero exit is masked by `tee`'s `0` and a failed run looks green.

This is a robustness enhancement to the toolkit's own orchestrator (not a product feature): it makes run-one fail loudly and record its true outcome. Related: ADR-011 introduced the forward-only state work that exposed the unpushed-main edge; this plan is independent of that schema.

## Intake Triage

- [x] Defect-driven hardening of existing tooling with a known reproduction (below). It adds new guards plus telemetry wiring rather than only patching one line, so it is tracked as a plan — mirroring the `2026-06-18-fix-nondeterministic-skill-packaging` precedent.
- [ ] If treated as a pure defect, a companion `docs/bugs/` entry can be filed via `aet-bug-report`; the reproduction is recorded here.

**Reproduction:** with local `main` ahead of `origin/main`, run `aet-work run-one <plan>` where the plan is only in an unpushed commit → the worktree is created from `origin/main` without the plan; no halt, no warning, no telemetry.

## Tasks

1. **Extract a shared main-hygiene gate and call it from `run_single`** — S (`aet-work/bin/orchestrator`)

   Factor the `run_batch` hygiene block (`orchestrator:254`) into a helper `enforce_main_hygiene(repo_root) -> bool` that halts (caller returns exit code `1`) in interactive mode and warns-and-continues when `AET_EXECUTION_MODE=unattended`. Call it at the start of `run_single` before any worktree work, and from `run_batch` (no behaviour change for batch).

2. **Guard: fail loudly when the plan file is absent in the worktree** — S (`aet-work/bin/orchestrator`)

   In `process_task`, after `create_worktree` + `copy_untracked_files`, assert the computed worktree plan path exists. If missing, print an actionable diagnostic (e.g. `Plan not found in worktree — base may be stale; ensure the plan is committed and pushed to origin/main`) and return `False` instead of defaulting the stage and spawning a session.

3. **Emit a run-summary telemetry record so the true outcome is recoverable** — M (`aet-work/bin/orchestrator`)

   Extend `aet-work/lib/telemetry.py::run_summary_record()` to accept `outcome`, `exit_code`, `task_ids`, and `final_stage`, then wire the orchestrator to it: allocate a `run_id` via `new_run_id()`, and on every exit path of `run_single` and `run_batch` write a `run_summary_record(...)` via `append_record`. This populates `.agents/execution.log.jsonl` (today written by nothing) so `aet-work report` reflects reality even when stdout is `tee`-masked.

4. **Stop masking the exit code in the skill docs** — S (`aet-work/SKILL.md`)

   Update the `run` and `run-one` command examples to background the orchestrator with `> <log> 2>&1` (or document `set -o pipefail`) instead of `| tee <log>`, so the launching shell observes the orchestrator's real exit status.

5. **Unit tests** — M (`tests/test_orchestrator.py`)

   - `test_run_single_halts_when_main_ahead`, `_behind`, `_dirty` (interactive) and `test_run_single_warns_in_unattended`
   - `test_process_task_fails_when_plan_missing_in_worktree`
   - `test_run_summary_written_on_success` and `test_run_summary_written_on_failure` (record carries correct outcome + exit code)

6. **Merge branch to main and verify integration** — S

## Dependencies

- Independent of the `fods-*` forward-only-state work; touches the orchestrator, telemetry wiring, skill docs, and tests only.
- Task 5's hygiene tests depend on Task 1; the plan-presence test depends on Task 2.

## Validation Steps

- [ ] Lint passes (`make validate`).
- [ ] Tests pass; `tests/test_orchestrator.py` covers run_single hygiene (halt + unattended-warn), the plan-presence guard, and run-summary emission on success/failure. `check_main_hygiene` itself remains covered by `tests/test_worktree.py`.
- [ ] `run_single` reaches the shared hygiene gate (grep confirms it is called from both `run_single` and `run_batch`).
- [ ] `aet-work report` shows a `run_summary` row after a run-one invocation (telemetry no longer empty).
- [ ] `aet-work/SKILL.md` no longer pipes the orchestrator through `tee`.
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`.

## Rollback Plan

Revert `aet-work/bin/orchestrator`, `aet-work/lib/telemetry.py`, the `aet-work/SKILL.md` doc change, and `tests/test_orchestrator.py`. `check_main_hygiene` already existed, so reverting restores prior behaviour with no schema or queue impact.

---

_Stage: qa-complete_
_Next step: run `aet-review`_
