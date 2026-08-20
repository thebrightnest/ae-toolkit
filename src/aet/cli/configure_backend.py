#!/usr/bin/env python3
"""aet configure — Configure the AET project config.

Usage:
  aet configure [--trunk-branch B]
                [--integration-mode pr-per-task|single-pr]
                [--integration-branch B] [--scope project|user]
                [--non-interactive] [--help]
  aet configure --guided [--scope team|shadow] [--integration-mode pr-per-task|single-pr]
  aet configure --migrate

The ``--guided`` flow is the setup-time entry point: it asks exactly two
questions — scope (team/shadow) and integration mode (pr-per-task/single-pr) —
and writes the config via the single cfg-02 writer. Existing config is detected
and shown before overwriting. ``AET_EXECUTION_MODE=unattended`` or explicit
``--scope``/``--integration-mode`` flags skip all prompts.

GitHub Issues is configured on the orthogonal "projections" axis in
.agents/aet-config.json (see aet-setup docs).

Config resolution order remains external-first:
AET_WORK_CONFIG env → ~/.aet/{slug}/config.json → .agents/aet-config.json → defaults.

Use --scope user for a non-invasive project: the config is written to
~/.aet/{slug}/config.json and nothing is written inside the repo. The default
scope is project when an in-tree config already exists, and user otherwise.
In guided mode ``--scope team`` is an alias for ``project`` and ``shadow`` is an
alias for ``user``.

Use --migrate to rename a legacy .agents/aet-work.json to the canonical
.agents/aet-config.json. The rename uses git mv when the legacy file is
tracked and a plain filesystem rename otherwise. Migrate refuses to overwrite
an existing .agents/aet-config.json.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import typer

from aet.backends.factory import INTEGRATION_MODES, resolve_config_with_source
from aet.project_id import derive_config_slug

NEW_CONFIG_NAME = "aet-config.json"
LEGACY_CONFIG_NAME = "aet-work.json"

# Guided-flow scope vocabulary.  "team" writes config into the repo;
# "shadow" writes it to an external user-scoped directory so nothing is
# committed.  These aliases are normalized to the writer's project/user
# vocabulary before any I/O happens.
GUIDED_SCOPE_ALIASES = {
    "team": "project",
    "shadow": "user",
    "project": "project",
    "user": "user",
}


def _log(msg: str) -> None:
    print(f"[configure] {msg}", file=sys.stderr)


def _error(msg: str) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def _write_json_config(existing_json: str | None, updates: dict) -> str:
    config: dict = {}
    if existing_json:
        config = json.loads(existing_json)
    # Drop the removed task_backend key when rewriting config through the
    # supported writer; this is the in-place migration path.
    config.pop("task_backend", None)
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
    Refuses to overwrite an existing new file. The rename also strips the
    removed ``task_backend`` key.
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

    # Strip the removed key from the migrated file.
    raw = new_file.read_text(encoding="utf-8")
    config = json.loads(raw)
    if "task_backend" in config:
        config.pop("task_backend")
        new_file.write_text(json.dumps(config, indent=2), encoding="utf-8")

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
    integration_mode: str | None,
) -> str | None:
    """Reject values the resolver would reject, naming legal values."""
    if integration_mode is not None and integration_mode not in INTEGRATION_MODES:
        return (
            f"Invalid integration_mode '{integration_mode}'. "
            f"Choose one of: {', '.join(sorted(INTEGRATION_MODES))}."
        )
    return None


def _build_updates(
    trunk_branch: str | None,
    integration_mode: str | None,
    integration_branch: str | None,
) -> dict:
    """Build the merge-style config updates for the keys explicitly provided."""
    updates: dict = {}

    if trunk_branch is not None:
        updates["trunk_branch"] = trunk_branch

    if integration_mode is not None:
        updates["integration_mode"] = integration_mode

    if integration_branch is not None:
        updates["integration_branch"] = integration_branch

    return updates


def _is_unattended() -> bool:
    """Return True when the environment requests non-interactive execution."""
    return os.environ.get("AET_EXECUTION_MODE") == "unattended"


def _prompt_choice(prompt: str, choices: set[str], default: str | None = None) -> str:
    """Prompt until the user supplies one of ``choices``.

    ``default`` is returned on empty input when provided.
    """
    choice_str = "/".join(sorted(choices))
    default_hint = f" [{default}]" if default else ""
    while True:
        try:
            value = input(f"{prompt} ({choice_str}){default_hint}: ").strip()
        except (EOFError, KeyboardInterrupt):
            value = ""
        if not value and default is not None:
            return default
        if value in choices:
            return value
        print(f"Please enter one of: {', '.join(sorted(choices))}.", file=sys.stderr)


def _prompt_yes_no(prompt: str, default: bool = False) -> bool:
    """Prompt for a yes/no answer and return the boolean result."""
    suffix = " [Y/n]" if default else " [y/N]"
    while True:
        try:
            value = input(f"{prompt}{suffix}: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            value = ""
        if not value:
            return default
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        print("Please answer yes or no.", file=sys.stderr)


def _normalize_guided_scope(value: str | None) -> str | None:
    """Map guided scope aliases to the writer's project/user vocabulary."""
    if value is None:
        return None
    normalized = GUIDED_SCOPE_ALIASES.get(value.lower())
    if normalized is None:
        return value
    return normalized


def _run_guided(
    scope: str | None,
    integration_mode: str | None,
) -> int:
    """Interactive two-question setup flow.

    Asks for scope (team/shadow) and integration mode (pr-per-task/single-pr),
    detects an existing config, confirms before overwriting, and writes the
    result through the cfg-02 writer.  Non-interactive bypass is available via
    ``--scope``/``--integration-mode`` flags or ``AET_EXECUTION_MODE=unattended``.
    """
    project_root = Path.cwd()
    in_tree_path = project_root / ".agents" / NEW_CONFIG_NAME

    config, source = resolve_config_with_source(str(in_tree_path), project_root)
    existing_mode = config.get("integration_mode")
    existing_scope = "team" if source == "project" else "shadow" if source in {"user", "env"} else None

    has_flags = scope is not None or integration_mode is not None
    unattended = _is_unattended() or has_flags

    if scope is None:
        if unattended:
            # Default to shadow (non-invasive) when nothing is specified.
            scope = "shadow"
        else:
            hint = f" [{existing_scope}]" if existing_scope else ""
            scope = _prompt_choice(
                f"Where should AET store its config? (team=repo, shadow=HOME){hint}",
                {"team", "shadow"},
                default=existing_scope,
            )
    scope = _normalize_guided_scope(scope)

    if integration_mode is None:
        if unattended:
            integration_mode = existing_mode or "pr-per-task"
        else:
            hint = f" [{existing_mode}]" if existing_mode else ""
            integration_mode = _prompt_choice(
                "Integration mode" + hint,
                INTEGRATION_MODES,
                default=existing_mode,
            )
    if integration_mode not in INTEGRATION_MODES:
        _error(
            f"Invalid integration_mode '{integration_mode}'. "
            f"Choose one of: {', '.join(sorted(INTEGRATION_MODES))}."
        )
        return 1

    target = _target_path(project_root, scope)
    existing_target_config = _read_existing_config(target)

    # Confirmation when we are about to overwrite an existing config.
    if existing_target_config and not unattended:
        current_scope_label = "team" if scope == "project" else "shadow"
        print("Existing AET config detected:")
        print(f"  scope: {current_scope_label}")
        print(f"  integration_mode: {existing_target_config.get('integration_mode', 'not set')}")
        if not _prompt_yes_no("Overwrite existing config?", default=False):
            _log("Config left unchanged.")
            return 0

    updates = {
        "integration_mode": integration_mode,
    }
    existing_json = target.read_text(encoding="utf-8") if target.exists() else None
    target.write_text(_write_json_config(existing_json, updates), encoding="utf-8")

    scope_label = "team" if scope == "project" else "shadow"
    provenance = "committed in repo" if scope == "project" else "external user config"
    _log(f"Wrote config ({scope_label}, {provenance}): {target}")
    _log(f"  integration_mode: {integration_mode}")
    return 0


def _run(
    trunk_branch: str | None,
    integration_mode: str | None,
    integration_branch: str | None,
    scope: str | None,
    non_interactive: bool,
    migrate: bool,
    guided: bool,
) -> int:
    project_root = Path.cwd()

    if migrate:
        return _migrate_config(project_root)

    if guided:
        return _run_guided(scope, integration_mode)

    validation_error = _validate_options(integration_mode)
    if validation_error is not None:
        print(f"Error: {validation_error}", file=sys.stderr)
        return 1

    resolved_scope = _resolve_scope(project_root, scope)
    target = _target_path(project_root, resolved_scope)
    updates = _build_updates(
        trunk_branch, integration_mode, integration_branch
    )

    if not updates:
        _log("No config changes requested.")
        return 0

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
    guided: bool = typer.Option(
        False,
        "--guided",
        help="Run the two-question guided setup flow (scope + integration mode).",
    ),
) -> None:
    """Configure the AET project config."""
    rc = _run(
        trunk_branch,
        integration_mode,
        integration_branch,
        scope,
        non_interactive,
        migrate,
        guided,
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
