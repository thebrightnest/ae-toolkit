"""Shared helpers for the consolidated Typer CLI tests."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import typer
from typer.testing import CliRunner


class Result:
    """Thin wrapper so callers can use either attribute or tuple unpacking."""

    def __init__(self, typer_result: Any) -> None:
        self._result = typer_result

    @property
    def exit_code(self) -> int:
        return self._result.exit_code

    @property
    def output(self) -> str:
        return self._result.output

    @property
    def stdout(self) -> str:
        return self._result.stdout

    @property
    def stderr(self) -> str:
        return self._result.stderr


def run_typer(
    app: typer.Typer,
    argv: list[str] | None = None,
    *,
    cwd: str | Path | None = None,
    env: dict[str, str | None] | None = None,
) -> Result:
    """Invoke a Typer app and return a result object.

    ``cwd`` is changed for the duration of the invocation and restored
    afterwards.  The default ``catch_exceptions=True`` means expected CLI
    errors are surfaced through ``result.exit_code`` rather than propagated.
    """
    runner = CliRunner()
    old_cwd = os.getcwd()
    if cwd is not None:
        os.chdir(cwd)
    try:
        result = runner.invoke(app, argv or [], env=env, catch_exceptions=True)
    finally:
        if cwd is not None:
            os.chdir(old_cwd)
    return Result(result)


def write_json_file(data: Any) -> str:
    """Write ``data`` to a temp JSON file and return its path."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        return f.name


def make_history(tasks: list[dict]) -> str:
    """Write task records to a temp JSONL file and return its path."""
    path = Path(tempfile.mkstemp(suffix=".jsonl")[1])
    with open(path, "w", encoding="utf-8") as f:
        for task in tasks:
            json.dump(task, f)
            f.write("\n")
    return str(path)


def make_plan(
    plans_dir: Path,
    name: str,
    *,
    footer_stage: str = "plan-approved",
    status: str = "approved",
    blocked_by: list[str] | None = None,
) -> Path:
    """Create a minimal atomic plan file in ``plans_dir``."""
    path = plans_dir / name
    blocked_lines = "".join(f"  - {b}\n" for b in (blocked_by or []))
    body = f"""---
id: {Path(name).stem}
size: M
status: {status}
blocked_by:
{blocked_lines}---

# Plan: {name}

## Context
PRD: docs/prds/default-prd.md

## Task List

1. Do something (traces: R-1).

## Files to Modify

- `src/widget.py` (new)

## Validation Steps

- [ ] test_widget_creation verifies widget.py

---

_Stage: {footer_stage}_
_Next step: run `aet-work`_
"""
    path.write_text(body, encoding="utf-8")
    return path


def git(args: list[str], cwd: str | Path) -> None:
    """Run a git command, raising on failure."""
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)
