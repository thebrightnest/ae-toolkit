# Technical Reference for aet-drive

This directory contains technical references and deep-dive architecture details for `/aet-drive`.

## CLI Adapter Detection

`aet-drive` relies on the host adapter detection mechanism in `src/aet/cli_adapter.py`.

Resolution priority:

1. Explicit CLI argument (`--cli-bin <path>`).
2. Environment variable (`AET_CLI_BIN`).
3. Process ancestry inspection (`detect_host_adapter()`).
   - Walks parent process hierarchy (`ps -o ppid=,comm=`).
   - Identifies whether the host shell was spawned by `agy` (Antigravity), `claude` (Claude Code), or `kimi` (Kimi CLI).
   - Resolves appropriate execution flags, session identifiers, and streaming formats.

When process detection is inhibited (for example inside sandboxed container IDEs), setting `export AET_CLI_BIN=<bin>` in the environment provides deterministic adapter selection.

## Autonomous Merge Architecture

`aet ship merge` performs:

1. **Target Branch Resolution**: Defaults to the active task's stamped `integration_branch` (from `task.get("integration_branch")` or `task.get("stamp", {}).get("branch")`), falling back to trunk `main` only for standalone tasks.
2. **Pre-Merge Gate**: Validates tests, static analysis, and verify verdicts in an isolated gate worktree.
3. **Conflict Detection**: Uses `git merge-tree` against the merge base and target branch to detect conflict markers. If found, parses conflicting file paths and emits them in the error output.
4. **Direct Integration**: Merges the feature branch into the target integration branch without modifying the human exit-gate for PR creation.
5. **Terminal Closure**: Archives the plan file and registers the closed event in `refs/aet/ledger`.

## Conflict Resolution Patterns

When resolving conflicts:

- **Additive Changes**: Combine additions from both branches (e.g., non-conflicting imports, new function definitions).
- **Overlapping Logic**: Compare the requirements of both tasks. Ensure no assertions, edge case handlers, or validation gates added by the predecessor task are erased.
- **Verification Rule**: Never commit conflict resolutions without executing the corresponding test suite (`make test` or targeted pytest).
