---
subject: worktree-venv-isolation
relates: [22, 36, 79, 82, 87]
---

# Worktree Virtual Environment Isolation and Self-Healing

## Status

Proposed. Amends ADR-022 and ADR-079. PRD:
`docs/prds/worktree-venv-isolation-prd.md`.

## Context

The repository contains both skills and an installable Python package (`src/aet/`,
ADR-036). The local development workflow relies on editable installation
(`make install-editable`), which writes an editable path pointer into the
virtual environment at
`.venv/lib/python3.11/site-packages/_editable_impl_aet.pth`.

When `aet` spawns worker sessions in linked worktrees (`.worktrees/*`) or creates
temporary worktrees during merge train flushes and bisects (`/tmp/aet-train-flush-*`,
`/tmp/aet-train-bisect-*`), subprocesses frequently run `make validate` or
`make install-editable`. Because the worktree shares the root virtual environment,
`pip install -e .` mutates `_editable_impl_aet.pth` to point to that ephemeral
worktree's `src/` directory.

When the worktree is torn down or pruned at task completion, the `.pth` file
points to a deleted directory. Every subsequent Python command and `aet` CLI
invocation in the root workspace immediately crashes with:
`ModuleNotFoundError: No module named 'aet'`.

## Decision

1. **Worktree-Aware Editable Install:** `scripts/check-editable-install.py` and
   `Makefile` detect whether execution is running inside a linked git worktree
   (where `git rev-parse --git-dir` differs from `git rev-parse --git-common-dir`).
   In linked worktrees, `install-editable` verifies that `aet` is importable via
   `PYTHONPATH` or the shared virtual environment, and skips running
   `pip install -e .` into the shared `.venv`.
2. **Worktree Python Path Isolation:** `create_worktree()` in `src/aet/worktree.py`,
   child orchestrator spawns in `src/aet/cli/orchestrator.py`, and
   `_run_flush_validation()` in `src/aet/train.py` explicitly inject
   `PYTHONPATH=<worktree>/src:<root_repo>/src` into the execution environment.
   Worktree processes load their own code without modifying global virtualenv state.
3. **Virtualenv Symlink Standardization:** `create_worktree()` and temporary
   worktree allocators in `src/aet/train.py` standardize symlinking
   `<root_repo>/.venv` to `<worktree>/.venv`. This avoids empty venv creation
   (`python3 -m venv .venv`) that lacks dev dependencies like `pytest` and `ruff`.
4. **Self-Healing Guard on Teardown and Flush:** `teardown_worktree()` in
   `src/aet/worktree.py` and `finally` cleanup blocks in `src/aet/train.py`
   inspect `_editable_impl_aet.pth` in `.venv`. If it references a non-existent
   path or a path outside the root repository, they restore it to `<repo_root>/src`.
   `aet state heal` also performs this check during manual state reconciliation.
