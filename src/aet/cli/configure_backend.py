#!/usr/bin/env python3
"""aet configure — Configure the AET project config.

Usage:
  aet configure [--backend json|git-refs] [--external-config]
                [--non-interactive] [--help]
  aet configure --migrate

In interactive mode (default), the script prompts for the backend (empty
input accepts the default, git-refs). In non-interactive mode, a missing
--backend selects the default (git-refs).

GitHub Issues is no longer a task_backend value; it is configured on the
orthogonal "projections" axis in .agents/aet-config.json (see aet-setup docs).

Use --external-config for a non-invasive project: the config is written to
~/.aet/{slug}/config.json and nothing is written inside the repo. Reads
always resolve external-first: AET_WORK_CONFIG env → ~/.aet/{slug}/config.json
→ .agents/aet-config.json → defaults.

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

from aet.project_id import derive_config_slug

DEFAULT_BACKEND = "git-refs"
NEW_CONFIG_NAME = "aet-config.json"
LEGACY_CONFIG_NAME = "aet-work.json"


def _log(msg: str) -> None:
    print(f"[configure] {msg}", file=sys.stderr)


def _error(msg: str) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def _write_json_config(existing_json: str | None, backend: str, switch_warning: str | None) -> str:
    config: dict = {}
    if existing_json:
        config = json.loads(existing_json)
    config["task_backend"] = backend
    if switch_warning:
        config["switch_warning"] = switch_warning
    return json.dumps(config, indent=2)


def _read_existing_backend(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("task_backend", "")
    except (OSError, json.JSONDecodeError):
        return ""


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

    if new_file.exists():
        _error(
            f"Refusing to migrate: {new_file} already exists. "
            "Resolve the conflict manually and remove one of the files."
        )

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
    else:
        legacy.rename(new_file)

    _log(f"Migrated {legacy} -> {new_file}")
    return 0


def _run(
    backend: str | None,
    external_config: bool,
    non_interactive: bool,
    migrate: bool,
) -> int:
    project_root = Path.cwd()
    agents_dir = project_root / ".agents"
    config_file = agents_dir / NEW_CONFIG_NAME

    if migrate:
        return _migrate_config(project_root)

    if backend is None:
        if non_interactive:
            backend = DEFAULT_BACKEND
        else:
            try:
                choice = input("Choose task backend (json or git-refs) [git-refs]: ")
            except (EOFError, KeyboardInterrupt):
                choice = ""
            backend = choice.strip() or DEFAULT_BACKEND

    if backend not in ("json", "git-refs"):
        _error(
            f"Invalid backend '{backend}'. Choose 'json' or 'git-refs'. "
            "GitHub Issues is configured on the 'projections' axis, not as a task_backend."
        )

    external_config_file: Path | None = None
    if external_config:
        slug = derive_config_slug()
        external_config_dir = Path.home() / ".aet" / slug
        external_config_dir.mkdir(parents=True, exist_ok=True)
        external_config_file = external_config_dir / "config.json"

    existing_backend = ""
    if external_config_file is not None:
        existing_backend = _read_existing_backend(external_config_file)
    else:
        existing_backend = _read_existing_backend(config_file)

    switch_warning = ""
    if existing_backend and existing_backend != backend:
        switch_warning = (
            f"Switching from '{existing_backend}' to '{backend}' is forward-only: "
            "active tasks and settled history are not migrated."
        )
        _log(f"WARNING: {switch_warning}")

    if backend == "json":
        _log(
            "NOTE: json is the documented opt-out, appropriate for non-git or "
            "unconfigured contexts; git-refs is the default backend written by aet-setup."
        )

    if external_config_file is not None:
        existing_json = None
        if external_config_file.exists():
            existing_json = external_config_file.read_text(encoding="utf-8")
        external_config_file.write_text(
            _write_json_config(existing_json, backend, switch_warning or None),
            encoding="utf-8",
        )
        _log(f"Wrote external config to {external_config_file}")
        _log(
            "Config resolution order: AET_WORK_CONFIG env → ~/.aet/{slug}/config.json "
            f"→ .agents/{NEW_CONFIG_NAME} → defaults"
        )
    else:
        agents_dir.mkdir(parents=True, exist_ok=True)
        existing_json = None
        if config_file.exists():
            existing_json = config_file.read_text(encoding="utf-8")
        config_file.write_text(
            _write_json_config(existing_json, backend, switch_warning or None),
            encoding="utf-8",
        )
        _log(f"Wrote {config_file}")

    return 0


app = typer.Typer(invoke_without_command=True)


@app.callback()
def configure(
    backend: str | None = typer.Option(
        None,
        "--backend",
        help="Choose the task backend (default: git-refs).",
    ),
    external_config: bool = typer.Option(
        False,
        "--external-config",
        help=f"Write config to ~/.aet/{{slug}}/config.json instead of .agents/{NEW_CONFIG_NAME}.",
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
    rc = _run(backend, external_config, non_interactive, migrate)
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
