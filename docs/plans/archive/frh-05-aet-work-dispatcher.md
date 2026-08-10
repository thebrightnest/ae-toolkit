---
id: frh-05-aet-work-dispatcher
size: M
blocked_by: []
pipeline: standard
status: merged
---

# Plan: `aet-work` Multicall Dispatcher and Installer Hygiene

## Context

- PRD: `docs/prds/fable-review-hardening-prd.md` (G4)
- Source finding: technical assessment critical issue #3

`aet-work/SKILL.md` documents `aet-work add|review|status|next|sync|report|run|run-one` — but no `aet-work` binary exists; a human following the docs gets `command not found`. Meanwhile `aet-setup/bin/install-aet-binaries` symlinks **every** skill binary under its bare name into `~/.local/bin`: `sync` (shadows the Unix system command), `add`, `status`, `next`, `report`, `review`, `ship`, plus a stale `ingest-telemetry` from a removed binary — the installer never prunes.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect

## Task List

1. Create `aet-work/bin/aet-work` (Python, stdlib): multicall dispatcher mapping `add|review|status|next|sync|report|init-queue` to the sibling binaries (exec via `sys.executable`, argv forwarded), `run` → `orchestrator --queue-file .agents/work-queue.json` (forwarding `--max-jobs`, `--isolation`, `--task-timeout`, `--cli-bin`), `run-one <plan>` → `orchestrator --plan-file <plan>`; unknown subcommand exits 2 with usage — M
2. Rename `aet-ship/bin/ship` → `aet-ship/bin/aet-ship`; update references in `aet-ship/SKILL.md` and the module-load path in `tests/test_aet_ship.py` — S
3. Installer policy in `aet-setup/bin/install-aet-binaries`: link only binaries whose name starts with `aet-` plus an explicit allowlist (`configure-task-backend`, `install-aet-binaries`, `mine-learnings`); prune any existing symlink in BIN_DIR that points into a skill directory but is no longer in the install set (removes `sync`, `add`, `status`, `next`, `report`, `review`, `ship`, `init-queue`, `orchestrator`, `ingest-telemetry`) — never touch non-AET symlinks or real files — M
4. Update `aet-work/SKILL.md` and `aet-work/references/queue-commands.md` so every documented invocation matches the dispatcher (including removing the unimplemented `AET_WORK_JOBS` env-var claim in favor of `--max-jobs`) — S
5. Tests: `tests/test_aet_work_dispatcher.py` (new) and installer prune coverage (subprocess against a tmp BIN_DIR + fake skill tree) — M
6. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 3 files / ≤ 100 lines; M ≤ 1 day / ≤ 5 files / ≤ 200 lines; L must be split.

### Batching Check

- [x] Not one of several near-identical additions
- [x] Diff expected to exceed 3 files or 50 lines
- [x] Cannot share a branch with related tasks

## Files to Modify

- `aet-work/bin/aet-work` (new)
- `aet-setup/bin/install-aet-binaries`
- `aet-ship/bin/ship` → `aet-ship/bin/aet-ship` (rename)
- `aet-ship/SKILL.md`
- `aet-work/SKILL.md`
- `aet-work/references/queue-commands.md`
- `tests/test_aet_work_dispatcher.py` (new)
- `tests/test_aet_ship.py` (load-path update)

## Validation Steps

- [ ] `make validate` passes; full suite passes
- [ ] New source coverage — `tests/test_aet_work_dispatcher.py`:
  - `test_dispatch_status_forwards_argv`
  - `test_run_maps_to_orchestrator_queue_mode`
  - `test_run_one_maps_to_orchestrator_plan_mode`
  - `test_unknown_subcommand_exits_2`
  - `test_installer_prunes_stale_and_bare_links` (tmp BIN_DIR: stale link + bare `sync` link removed; `aet-work`, `aet-state` linked; foreign symlink untouched)
- [ ] Manual: `make install-binaries` on this machine, then `aet-work status` runs and `which sync` no longer resolves to `~/.local/bin/sync`
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit and re-run `make install-binaries` — the old installer restores the previous link set. The prune only removes symlinks, so restoration is complete.

---

_Stage: merged_
\_Next step: run `aet-implement`
