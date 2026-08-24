"""A config the operator has to edit is refused by name, not by traceback."""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from aet.cli.main import main


def _repo_with_config(tmp_path: Path, config: dict) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    agents = tmp_path / ".agents"
    agents.mkdir()
    (agents / "aet-config.json").write_text(json.dumps(config), encoding="utf-8")
    return tmp_path


@contextlib.contextmanager
def _invoked_in(repo_root: Path, argv: list[str], monkeypatch):
    """Run ``main()`` from ``repo_root`` with a clean AET environment."""
    for name in list(os.environ):
        if name.startswith("AET_"):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(sys, "argv", ["aet", *argv])
    yield


def _run(repo_root: Path, argv: list[str], monkeypatch) -> tuple[int, str]:
    err = io.StringIO()
    with _invoked_in(repo_root, argv, monkeypatch):
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            rc = main()
    return rc, err.getvalue()


def test_removed_task_backend_key_refuses_a_read_only_command(tmp_path, monkeypatch):
    """`state audit` is the natural first command after an upgrade."""
    repo = _repo_with_config(tmp_path, {"task_backend": "github"})

    rc, err = _run(repo, ["state", "audit"], monkeypatch)

    assert rc == 1
    assert "task_backend" in err
    assert "Traceback" not in err


def test_the_refusal_names_the_remedy(tmp_path, monkeypatch):
    repo = _repo_with_config(tmp_path, {"task_backend": "github"})

    _rc, err = _run(repo, ["state", "audit"], monkeypatch)

    assert "Remove 'task_backend'" in err


def test_a_clean_config_is_not_refused(tmp_path, monkeypatch):
    repo = _repo_with_config(tmp_path, {"trunk_branch": "main"})

    rc, err = _run(repo, ["state", "audit"], monkeypatch)

    assert rc == 0, err


def test_the_legacy_config_filename_is_refused_the_same_way(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    agents = tmp_path / ".agents"
    agents.mkdir()
    (agents / "aet-work.json").write_text("{}", encoding="utf-8")

    rc, err = _run(tmp_path, ["state", "audit"], monkeypatch)

    assert rc == 1
    assert "aet configure --migrate" in err
    assert "Traceback" not in err


if __name__ == "__main__":
    sys.exit(pytest.main([__file__]))
