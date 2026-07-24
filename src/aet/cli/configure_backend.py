#!/usr/bin/env python3
"""aet configure — Configure the AET project config.

Usage:
  aet configure [--task-backend json|git-refs] [--trunk-branch B]
                [--integration-mode pr-per-task|single-pr]
                [--integration-branch B] [--scope project|user]
                [--non-interactive] [--help]
  aet configure --migrate

In interactive mode (default), the script prompts for the task backend (empty
input accepts the default, git-refs). In non-interactive mode, a missing
--task-backend selects the default (git-refs).

GitHub Issues is no longer a task_backend value; it is configured on the
orthogonal "projections" axis in .agents/aet-config.json (see aet-setup docs).

Config resolution order remains external-first:
AET_WORK_CONFIG env → ~/.aet/{slug}/config.json → .agents/aet-config.json → defaults.

Use --scope user for a non-invasive project: the config is written to
~/.aet/{slug}/config.json and nothing is written inside the repo. The default
scope is project when an in-tree config already exists, and user otherwise.

Use --migrate to rename a legacy .agents/aet-work.json to the canonical
.agents/aet-config.json. The rename uses git mv when the legacy file is
tracked and a plain filesystem rename otherwise. Migrate refuses to overwrite
an existing .agents/aet-config.json.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import typer

from aet.backends.factory import INTEGRATION_MODES
from aet.project_id import derive_config_slug

DEFAULT_BACKEND = "git-refs"
NEW_CONFIG_NAME = "aet-config.json"
LEGACY_CONFIG_NAME = "aet-work.json"
KNOWN_BACKENDS = frozenset({"json", "git-refs"})


def _log(msg: str) -> None:
    print(f"[configure] {msg}", file=sys.stderr)


def _error(msg: str) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def _write_json_config(existing_json: str | None, updates: dict) -> str:
    config: dict = {}
    if existing_json:
        config = json.loads(existing_json)
    config.update(updates)
    return json.dumps(config, indent=2)


def _read_existing_config(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _is_tracked(path: Path) -> bool:
    """Return True when ``path`` is tracked in git."""
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(path)],
        cwd=path.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _migrate_config(project_root: Path) -> int:
    """Rename legacy .agents/aet-work.json to .agents/aet-config.json.

    Uses ``git mv`` when the legacy file is tracked; otherwise a plain rename.
    Refuses to overwrite an existing new file.
    """
    agents_dir = project_root / ".agents"
    legacy = agents_dir / LEGACY_CONFIG_NAME
    new_file = agents_dir / NEW_CONFIG_NAME

    if not legacy.exists():
        _error(f"No legacy config to migrate: {legacy}")
        return 1

    if new_file.exists():
        _error(
            f"Refusing to migrate: {new_file} already exists. "
            "Resolve the conflict manually and remove one of the files."
        )
        return 1

    if _is_tracked(legacy):
        result = subprocess.run(
            ["git", "mv", LEGACY_CONFIG_NAME, NEW_CONFIG_NAME],
            cwd=agents_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            _error(f"git mv failed: {result.stderr.strip()}")
            return 1
    else:
        legacy.rename(new_file)

    _log(f"Migrated {legacy} -> {new_file}")
    return 0


def _target_path(project_root: Path, scope: str) -> Path:
    """Return the config file path for the chosen scope."""
    if scope == "user":
        slug = derive_config_slug(project_root)
        external_config_dir = Path.home() / ".aet" / slug
        external_config_dir.mkdir(parents=True, exist_ok=True)
        return external_config_dir / "config.json"

    agents_dir = project_root / ".agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    return agents_dir / NEW_CONFIG_NAME


def _resolve_scope(project_root: Path, scope: str | None) -> str:
    """Choose scope: explicit value wins, then project if in-tree config exists."""
    if scope is not None:
        return scope
    if (project_root / ".agents" / NEW_CONFIG_NAME).exists():
        return "project"
    return "user"


def _validate_options(
    task_backend: str | None,
    integration_mode: str | None,
) -> str | None:
    """Reject values the resolver would reject, naming legal values."""
    if task_backend is not None and task_backend not in KNOWN_BACKENDS:
        return (
            f"Invalid task_backend '{task_backend}'. "
            f"Choose one of: {', '.join(sorted(KNOWN_BACKENDS))}. "
            "GitHub Issues is configured on the 'projections' axis, not as a task_backend."
        )
    if integration_mode is not None and integration_mode not in INTEGRATION_MODES:
        return (
            f"Invalid integration_mode '{integration_mode}'. "
            f"Choose one of: {', '.join(sorted(INTEGRATION_MODES))}."
        )
    return None


def _build_updates(
    task_backend: str | None,
    trunk_branch: str | None,
    integration_mode: str | None,
    integration_branch: str | None,
    existing: dict,
) -> dict:
    """Build the merge-style config updates for the keys explicitly provided."""
    updates: dict = {}

    if task_backend is not None:
        updates["task_backend"] = task_backend

    if trunk_branch is not None:
        updates["trunk_branch"] = trunk_branch

    if integration_mode is not None:
        updates["integration_mode"] = integration_mode

    if integration_branch is not None:
        updates["integration_branch"] = integration_branch

    # Preserve a switch warning when the backend changes.
    existing_backend = existing.get("task_backend", "")
    if task_backend is not None and existing_backend and existing_backend != task_backend:
        switch_warning = (
            f"Switching from '{existing_backend}' to '{task_backend}' is forward-only: "
            "active tasks and settled history are not migrated."
        )
        _log(f"WARNING: {switch_warning}")
        updates["switch_warning"] = switch_warning

    return updates


def _run(
    task_backend: str | None,
    trunk_branch: str | None,
    integration_mode: str | None,
    integration_branch: str | None,
    scope: str | None,
    non_interactive: bool,
    migrate: bool,
) -> int:
    project_root = Path.cwd()

    if migrate:
        return _migrate_config(project_root)

    if task_backend is None:
        if non_interactive:
            task_backend = DEFAULT_BACKEND
        else:
            try:
                choice = input("Choose task backend (json or git-refs) [git-refs]: ")
            except (EOFError, KeyboardInterrupt):
                choice = ""
            task_backend = choice.strip() or DEFAULT_BACKEND

    validation_error = _validate_options(task_backend, integration_mode)
    if validation_error is not None:
        print(f"Error: {validation_error}", file=sys.stderr)
        return 1

    resolved_scope = _resolve_scope(project_root, scope)
    target = _target_path(project_root, resolved_scope)
    existing = _read_existing_config(target)
    updates = _build_updates(
        task_backend, trunk_branch, integration_mode, integration_branch, existing
    )

    if not updates:
        _log("No config changes requested.")
        return 0

    if task_backend == "json":
        _log(
            "NOTE: json is the documented opt-out, appropriate for non-git or "
            "unconfigured contexts; git-refs is the default backend written by aet-setup."
        )

    existing_json = target.read_text(encoding="utf-8") if target.exists() else None
    target.write_text(_write_json_config(existing_json, updates), encoding="utf-8")

    if resolved_scope == "user":
        _log(f"Wrote user config to {target}")
        _log(
            "Config resolution order: AET_WORK_CONFIG env → ~/.aet/{slug}/config.json "
            f"→ .agents/{NEW_CONFIG_NAME} → defaults"
        )
    else:
        _log(f"Wrote project config to {target}")

    return 0


app = typer.Typer(invoke_without_command=True)


@app.callback()
def configure(
    task_backend: str | None = typer.Option(
        None,
        "--task-backend",
        help="Choose the task backend (default: git-refs).",
    ),
    trunk_branch: str | None = typer.Option(
        None,
        "--trunk-branch",
        help="Set the trunk branch name.",
    ),
    integration_mode: str | None = typer.Option(
        None,
        "--integration-mode",
        help="Set the integration mode.",
    ),
    integration_branch: str | None = typer.Option(
        None,
        "--integration-branch",
        help="Set the integration branch name.",
    ),
    scope: str | None = typer.Option(
        None,
        "--scope",
        help="Write to project config or user config (default: project if in-tree config exists).",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Fail if a required value is missing instead of prompting.",
    ),
    migrate: bool = typer.Option(
        False,
        "--migrate",
        help=f"Rename legacy .agents/{LEGACY_CONFIG_NAME} to .agents/{NEW_CONFIG_NAME}.",
    ),
) -> None:
    """Configure the AET project config."""
    rc = _run(
        task_backend,
        trunk_branch,
        integration_mode,
        integration_branch,
        scope,
        non_interactive,
        migrate,
    )
    raise typer.Exit(rc)


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    try:
        return app(argv, standalone_mode=False)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0


if __name__ == "__main__":
    app()
