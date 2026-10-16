---
id: retire-cli-dry-run
status: scope-validated
branch: feat/retire-cli-dry-run
pr_title: "refactor(cli): eliminate --dry-run across aet ship, state, and setup commands"
---

# PRD: Retire Optional CLI --dry-run Flags

## Overview

The `aet` CLI has accumulated optional `--dry-run` flags across multiple operational commands (`aet ship`, `aet state`, and `aet setup`). In practice, these flags represent dead, deceptive, or cargo-cult logic:

- In `aet ship merge`, `--dry-run` does not evaluate mergeability, detect merge conflicts, or run test suites; it merely prints a mock string (`"Would integrate..."`) and exits zero.
- In `aet ship` (and its subcommands `gate`, `open`, `open-epic`, `close`), it adds fake mock print statements while the actual commands rely entirely on Git's native safety and transactional atomicity. If a merge or rebase conflicts, Git stops and errors out naturally; if a ref is missing, Git halts.
- In `aet state` (e.g., `reset`, `transition`, `set-stage`, `record-merge`), commands mutate deterministic task state or DAG stages where state invariants and Git refs already govern validity.
- In `aet setup` (`skills`, `hooks`, `project`), the command should simply perform the setup actions and report what was executed; simulating installation adds unnecessary branching without value.
- In autonomous and agentic pipelines (`aet-drive`, `aet run`), `--dry-run` acts as an unprompted defensive crutch for LLMs, resulting in false completion reports without actual execution.

This PRD retires `--dry-run` flags from the `aet ship`, `aet state`, and `aet setup` surfaces. Operations execute directly, surface informative summaries, and let the underlying transactional engines (Git and filesystem) handle errors natively.

**Intake Triage Guard:** Confirmed enhancement/simplification. Not a reproducible defect.

## Goals

- Eliminate `--dry-run` options and their mocked code branches from `aet ship` subcommands (`merge`, `gate`, `open`, `open-epic`, `split`, `close`, and default dispatch).
- Eliminate `--dry-run` options and their preview branches from `aet state` subcommands (`reset`, `transition`, `set-stage`, `record-merge`).
- Eliminate `--dry-run` options from `aet setup` subcommands (`skills`, `hooks`, `project`), letting them execute directly and print status.
- Remove fake simulation logic and dead code branches across CLI implementations and internal helpers.
- Clean up tests that pass or assert `dry_run`, reducing fixture verbosity and test maintenance debt.

## Non-Goals

- Inventing synthetic pre-flight check layers or pre-validation abstractions. Operations run directly; underlying tool failures (Git conflict, ref lookup error, OS permissions) are surfaced as native errors.
- Modifying read-only inspection commands (such as `aet status`, `aet queue list`, `aet state audit`, or `aet config show`), which already serve as the canonical mechanism to inspect state without mutating anything.
- Altering CLI subcommands whose primary design uses `--apply` to toggle batch cleanup modes (such as `aet state reconcile` or `aet state backfill-specs`), unless unified in a separate pass.

## Requirements

- **R-1**: Remove `--dry-run` option and mock branching from `aet ship` and all its subcommands (`ship`, `gate`, `open`, `open-epic`, `merge`, `split`, `close`).
- **R-2**: Internal git helpers in `src/aet/cli/ship.py` (`_push_branch`, `_create_pr`, `_rebase_independent`, etc.) must drop the `dry_run` parameter and execute real git operations directly.
- **R-3**: Remove `--dry-run` option and bypass logic from `aet state reset`, `aet state transition`, `aet state set-stage`, and `aet state record-merge`.
- **R-4**: Remove `--dry-run` option from `aet setup skills`, `aet setup hooks`, and `aet setup project`, performing installation directly and printing standard operational feedback.
- **R-5**: Clean up callers in `src/aet/cli/desk.py` and across the test suite (`tests/`) removing `dry_run=False` arguments and retiring dry-run-specific assertion tests.
- **R-6**: Update CLI documentation (`docs/CLI.md`) via `aet docs generate` to reflect the clean command signatures.

## User Stories

- As an operator or autonomous agent, I want `aet ship merge` to execute the merge directly and fail with clear Git output if there are conflicts, so that I never get false confirmation from a simulation (satisfies: R-1, R-2).
- As an engineer managing task states, I want `aet state` commands to execute state updates directly without redundant preview flags, relying on DAG constraints and ref validation (satisfies: R-3).
- As a developer installing skills or hooks, I want `aet setup` to execute and output what it linked without needing dry-run options (satisfies: R-4).
- As a maintainer, I want cleaner test signatures without ubiquitous `dry_run=False` kwargs (satisfies: R-5).

## Acceptance Criteria

- [ ] `aet ship --help`, `aet ship merge --help`, `aet ship close --help`, etc., show no `--dry-run` option (satisfies: R-1).
- [ ] `aet ship merge` performs real merge/integration logic directly; conflicting merges or missing branches fail via standard git errors (satisfies: R-1, R-2).
- [ ] `aet state reset --help`, `aet state transition --help`, etc., show no `--dry-run` option (satisfies: R-3).
- [ ] `aet setup skills --help`, `aet setup hooks --help`, and `aet setup project --help` show no `--dry-run` option (satisfies: R-4).
- [ ] All occurrences of `dry_run` parameters in `src/aet/cli/ship.py`, `src/aet/cli/aet_state.py`, `src/aet/cli/setup.py`, and `src/aet/cli/desk.py` are excised (satisfies: R-1, R-2, R-3, R-4, R-5).
- [ ] `make validate` passes cleanly with all updated tests (satisfies: R-5).
- [ ] `docs/CLI.md` is updated without `--dry-run` in the affected commands (satisfies: R-6).

## Technical Notes

- In `src/aet/cli/ship.py`:
  - `cmd_merge`: Remove lines 1249-1252 (`if getattr(args, "dry_run", False): ...`).
  - `cmd_split`: Remove soft reset dry-run preview (lines 1148-1152).
  - `cmd_close`: Remove branch deletion dry-run branching (lines 352-354).
  - `_rebase_independent`: Drop `dry_run` arg and preview return (lines 488-493).
  - `_push_branch` and `_create_pr`: Drop `dry_run` arg and mock returns.
- In `src/aet/cli/aet_state.py`:
  - Remove `dry_run` option from `reset`, `transition`, `set_stage`, `record_merge` Typer commands and underlying functions (`cmd_reset`, `cmd_transition`, `cmd_set_stage`, `cmd_record_merge`).
- In `src/aet/cli/setup.py`:
  - Remove `dry_run` option from `skills`, `hooks`, `project` and simplify `_link_skill`.
- Test updates:
  - Replace tests that verified `--dry-run` with tests verifying direct execution or remove the obsolete dry-run test cases.
