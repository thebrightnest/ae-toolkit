#!/usr/bin/env python3
"""aet configure-backend — Configure the task backend for aet-work.

Usage:
  aet configure-backend [--backend json|git-refs] [--external-config]
                        [--non-interactive] [--help]

In interactive mode (default), the script prompts for the backend (empty
input accepts the default, git-refs). In non-interactive mode, a missing
--backend selects the default (git-refs).

GitHub Issues is no longer a task_backend value; it is configured on the
orthogonal "projections" axis in .agents/aet-work.json (see aet-setup docs).

Use --external-config for a non-invasive project: the config is written to
~/.aet/{slug}/config.json and nothing is written inside the repo. Reads
always resolve external-first: AET_WORK_CONFIG env → ~/.aet/{slug}/config.json
→ .agents/aet-work.json → defaults.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from aet.project_id import derive_project_slug

DEFAULT_BACKEND = "git-refs"


def _usage() -> str:
    return """Usage: aet configure-backend [options]

Configure the task backend for aet-work.

Options:
  --backend json|git-refs
                          Choose the task backend. Defaults to git-refs, the
                          recommended backend: live tasks are stored as local
                          git refs (refs/aet/tasks/*). json is the documented
                          opt-out for non-git or unconfigured contexts.
  --external-config       Write config to ~/.aet/{slug}/config.json instead of
                          .agents/aet-work.json. Keeps AET config out of the
                          shared repo (non-invasive setup).
  --non-interactive       Fail if a required value is missing instead of prompting.
  --help                  Show this help message.

Examples:
  aet configure-backend --non-interactive
  aet configure-backend --backend json --non-interactive
  aet configure-backend --backend git-refs --external-config --non-interactive
"""


def _log(msg: str) -> None:
    print(f"[configure-backend] {msg}", file=sys.stderr)


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aet configure-backend",
        description="Configure the task backend for aet-work.",
        add_help=True,
    )
    parser.add_argument(
        "--backend",
        default=None,
        help="Choose the task backend (default: git-refs).",
    )
    parser.add_argument(
        "--external-config",
        action="store_true",
        help="Write config to ~/.aet/{slug}/config.json instead of .agents/aet-work.json.",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Fail if a required value is missing instead of prompting.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    project_root = Path.cwd()
    config_dir = project_root / ".agents"
    config_file = config_dir / "aet-work.json"

    backend = args.backend
    if backend is None:
        if args.non_interactive:
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
    if args.external_config:
        slug = derive_project_slug()
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
            "→ .agents/aet-work.json → defaults"
        )
    else:
        config_dir.mkdir(parents=True, exist_ok=True)
        existing_json = None
        if config_file.exists():
            existing_json = config_file.read_text(encoding="utf-8")
        config_file.write_text(
            _write_json_config(existing_json, backend, switch_warning or None),
            encoding="utf-8",
        )
        _log(f"Wrote {config_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
