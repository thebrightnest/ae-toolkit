---
id: worktree-venv-isolation
status: accepted
---

# PRD: Worktree Virtual Environment Isolation & Self-Healing

## Overview

When `aet` runs tasks or flushes merge trains across linked git worktrees (`.worktrees/*`, `/tmp/aet-train-flush-*`, `/tmp/aet-train-bisect-*`), subprocesses frequently execute `make install-editable` or `pip install -e .` against the shared Python virtual environment (`.venv`). This mutates `.venv/lib/python3.11/site-packages/_editable_impl_aet.pth` to point to the ephemeral worktree's `src/` directory. When the worktree is torn down upon task completion or flush exit, the `.pth` file points to a non-existent path, instantly breaking `aet` CLI dispatch across the entire workspace with `ModuleNotFoundError: No module named 'aet'`.

This PRD establishes complete virtual environment isolation and self-healing for git worktrees:
1. Worktree commands execute with explicit `PYTHONPATH` isolation pointing to `<worktree>/src`, preventing worktrees from needing to run `pip install -e .`.
2. `Makefile` and `scripts/check-editable-install.py` detect when execution is running inside a linked git worktree, skipping editable reinstall into the shared `.venv`.
3. Worktree teardown (`src/aet/worktree.py`) and merge train flush/bisect cleanup (`src/aet/train.py`) verify and automatically self-heal `_editable_impl_aet.pth` to ensure it always references the root repository.
ADR-088 records the architectural decision.

## Intake Triage

Enhancement closing systemic environment corruption and runtime failure across linked worktrees and merge flushes.
Work class: `critical`, because it affects workspace runtime availability, CLI dispatch integrity, and multi-worktree execution safety.

## Evidence

From execution telemetry and live failures observed during the `autonomous-loop-reliability` epic:
- During `alr-01` and `alr-02` merge flushes, `_editable_impl_aet.pth` in `.venv` was repeatedly rewritten to point to `/tmp/aet-train-flush-.../src` and `.worktrees/alr-02-.../src`.
- When the ephemeral worktrees were pruned, any subsequent `aet` command in the root repository immediately crashed:
  ```text
  Traceback (most recent call last):
    File "/home/.../.local/bin/aet", line 3, in <module>
      from aet.cli import main
  ModuleNotFoundError: No module named 'aet'
  ```
- During `alr-03` completion, `alr-05` tore down its worktree, invalidating the `.pth` file while `alr-03` was transitioning states, causing `aet_state.py` to fail with `ModuleNotFoundError` and orphaning `alr-03` in `in_progress`.

## Goals

- Eliminate `.venv` corruption caused by worktrees running `pip install -e .`.
- Ensure linked worktrees import their own working tree code without modifying the shared virtual environment.
- Make `Makefile`'s `install-editable` target worktree-aware so it skips mutating the shared `.venv` when invoked inside a linked worktree.
- Provide automatic self-healing in `teardown_worktree()` and `train.flush()` to restore `_editable_impl_aet.pth` to the root repository path if ever modified.

## Non-Goals

- Creating full standalone duplicate virtualenvs (100MB+ copies) for every ephemeral worktree.
- Modifying pip's internal editable installation mechanism.

## Requirements

- **R-1 (Worktree-Aware Editable Install):** `scripts/check-editable-install.py` and `Makefile` must detect when they are executing inside a linked git worktree (where `git rev-parse --git-dir` differs from `--git-common-dir`). In linked worktrees, `install-editable` must verify that `aet` is importable via `PYTHONPATH` or the shared environment, and skip invoking `pip install -e .`.
- **R-2 (Worktree Execution Environment Isolation):** `create_worktree()` in `src/aet/worktree.py`, child orchestrator spawns in `src/aet/cli/orchestrator.py`, and `_run_flush_validation()` in `src/aet/train.py` must inject `PYTHONPATH=<worktree>/src:<root_repo>/src` into the execution environment so that local worktree code takes precedence without mutating global virtualenv state.
- **R-3 (Virtualenv Symlink Standardization):** `create_worktree()` and temporary worktree allocators must symlink the root `.venv` to `<worktree>/.venv` if not already present, ensuring tools expecting `.venv/bin/python` find the shared interpreter without creating bare empty virtualenvs.
- **R-4 (Teardown & Flush Self-Healing Guard):** `teardown_worktree()` in `src/aet/worktree.py` and `finally` cleanup blocks in `src/aet/train.py` must inspect `_editable_impl_aet.pth` in `.venv` and, if it points to a non-existent directory or a path outside the root repository, restore it to `<repo_root>/src`.

## User Stories

- As an operator running parallel epics, I want child worktrees to run their test suites without modifying the shared virtual environment, so that the primary repository never loses access to the `aet` CLI. (satisfies: R-1, R-2)
- As an autonomous worker in an ephemeral worktree, I want `.venv` to be cleanly symlinked from the root repository, so that virtualenv python tools and dev dependencies are instantly available without re-running `python3 -m venv`. (satisfies: R-3)
- As an orchestrator tearing down completed worktrees, I want a self-healing guard that restores `_editable_impl_aet.pth`, so that workspace commands never crash on stale paths. (satisfies: R-4)

## Acceptance Criteria

- [ ] `make install-editable` invoked inside a linked worktree does not rewrite `_editable_impl_aet.pth` in the shared `.venv`. (satisfies: R-1)
- [ ] Subprocesses running in a linked worktree import that worktree's version of `src/aet` via `PYTHONPATH` without mutating the parent virtualenv. (satisfies: R-2)
- [ ] Ephemeral worktrees allocated by `create_worktree` and `flush()` contain a valid `.venv` symlink to the root virtualenv. (satisfies: R-3)
- [ ] If `_editable_impl_aet.pth` is manually pointed to a deleted temporary directory, running `teardown_worktree()` or `aet state heal` restores it to `<repo_root>/src`. (satisfies: R-4)

## Technical Notes

- Architecture decision recorded in `docs/adr/088-worktree-venv-isolation.md`.
- Detection of linked worktrees:
  ```python
  def is_linked_worktree(path: Path) -> bool:
      git_dir = subprocess.run(["git", "-C", str(path), "rev-parse", "--git-dir"], capture_output=True, text=True).stdout.strip()
      common_dir = subprocess.run(["git", "-C", str(path), "rev-parse", "--git-common-dir"], capture_output=True, text=True).stdout.strip()
      return os.path.abspath(git_dir) != os.path.abspath(common_dir)
  ```
- `_editable_impl_aet.pth` location: `<venv_dir>/lib/python<version>/site-packages/_editable_impl_aet.pth`.

## Open Questions

- None.

*Stage: scope-validated*
*Next step: run `aet sprint add`*
