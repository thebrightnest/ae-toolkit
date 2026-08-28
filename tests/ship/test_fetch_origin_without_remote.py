"""`aet ship` must work in a repository that has no `origin` remote.

`_run_git` raises on a non-zero exit and `git fetch origin` fails when no such
remote exists, so an unguarded fetch took down every `ship` subcommand on a
local-only project: they all run the pre-merge gate, and the gate fetches first.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_SHIP_PY = Path(__file__).parents[2] / "src" / "aet" / "cli" / "ship.py"
_spec = importlib.util.spec_from_loader(
    "aet_ship_no_remote",
    importlib.machinery.SourceFileLoader("aet_ship_no_remote", str(_SHIP_PY)),
)
ship = importlib.util.module_from_spec(_spec)
sys.modules["aet_ship_no_remote"] = ship
_spec.loader.exec_module(ship)


def _init_repo(path: Path) -> None:
    """Create a repository with one commit and no remote."""
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    for key, value in (("user.email", "t@example.com"), ("user.name", "T")):
        subprocess.run(["git", "-C", str(path), "config", key, value], check=True)
    (path / "README.md").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(path), "commit", "-q", "-m", "init"], check=True
    )


class TestFetchOriginWithoutRemote(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "repo"
        self.repo.mkdir()
        _init_repo(self.repo)
        self._cwd = os.getcwd()
        os.chdir(self.repo)

    def tearDown(self):
        os.chdir(self._cwd)
        self._tmp.cleanup()

    def test_no_origin_is_reported_absent(self):
        self.assertFalse(ship._has_origin())

    def test_fetch_origin_is_a_no_op_without_a_remote(self):
        """The bug: this raised CalledProcessError and killed the gate."""
        ship._fetch_origin()

    def test_fetch_origin_runs_when_origin_exists(self):
        """The guard must not disable fetching for a project that has a remote."""
        upstream = Path(self._tmp.name) / "upstream.git"
        subprocess.run(
            ["git", "init", "-q", "--bare", str(upstream)], check=True
        )
        subprocess.run(
            ["git", "remote", "add", "origin", str(upstream)], check=True
        )
        self.assertTrue(ship._has_origin())
        ship._fetch_origin()

    def test_a_real_fetch_failure_still_raises(self):
        """`check=False` would have hidden this; the guard must not."""
        subprocess.run(
            ["git", "remote", "add", "origin", "/nonexistent/repo.git"], check=True
        )
        self.assertTrue(ship._has_origin())
        with self.assertRaises(subprocess.CalledProcessError):
            ship._fetch_origin()


if __name__ == "__main__":
    unittest.main()
