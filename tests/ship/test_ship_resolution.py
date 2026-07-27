"""Tests that aet ship's plan-argument resolution still behaves as before (R-11)."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_SHIP_PY = Path(__file__).parents[2] / "src" / "aet" / "cli" / "ship.py"
_spec = importlib.util.spec_from_loader(
    "aet_ship", importlib.machinery.SourceFileLoader("aet_ship", str(_SHIP_PY))
)
ship = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ship)


class MockResult:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _subprocess_mock(responses):
    def mock_run(cmd, **kwargs):
        args = tuple(cmd)
        rc, out, err = responses.get(args, (1, "", ""))
        return MockResult(rc, out, err)

    return mock_run


class TestShipResolution(unittest.TestCase):
    """Plan-argument resolution for ship gate/open/merge/default commands."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

        base = Path(self.tmpdir.name)
        self.plan_path = base / "docs" / "plans" / "t1.md"
        self.plan_path.parent.mkdir(parents=True)
        self.plan_path.write_text(
            "---\n"
            "id: t1\n"
            "status: in_progress\n"
            "---\n\n"
            "# Plan T1\n\n"
            "---\n\n"
            "*Stage: implemented*\n",
            encoding="utf-8",
        )

        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        os.chdir(self.tmpdir.name)

    def _gate_success_responses(self):
        return {
            ("git", "fetch", "origin"): (0, "", ""),
            ("git", "rev-parse", "--abbrev-ref", "HEAD"): (0, "feat-001\n", ""),
            ("git", "rev-list", "--count", "origin/main..HEAD"): (0, "1\n", ""),
            ("git", "log", "origin/main..HEAD", "--format=%H"): (0, "abc1234\n", ""),
            ("git", "log", "-1", "--format=%B", "abc1234"): (0, "feat(t1): do thing\n", ""),
            ("git", "diff", "origin/main", "--name-only"): (0, "src/thing.py\n", ""),
            ("git", "merge-base", "origin/main", "HEAD"): (0, "base1234\n", ""),
            ("git", "status", "--short"): (0, "", ""),
            ("true",): (0, "", ""),
        }

    def _run_gate(self, argv: list[str], env: dict | None = None) -> int:
        """Run a ship command with git subprocess mocked and the test gate disabled."""
        merged_env = {"AET_SHIP_TEST_CMD": "true"}
        if env:
            merged_env.update(env)
        with patch.dict(os.environ, merged_env, clear=False):
            with patch.object(sys, "argv", argv):
                mock = _subprocess_mock(self._gate_success_responses())
                with patch.object(ship.aet_state.subprocess, "run", side_effect=mock):
                    with patch.object(ship.subprocess, "run", side_effect=mock):
                        return ship.main()

    def test_gate_accepts_bare_task_id(self):
        """``aet ship gate <id>`` resolves to the conventional plan path."""
        rc = self._run_gate(["ship", "gate", "t1"])
        self.assertEqual(rc, 0)

    def test_gate_accepts_full_md_path(self):
        """``aet ship gate <path>`` uses the path directly."""
        rc = self._run_gate(["ship", "gate", str(self.plan_path)])
        self.assertEqual(rc, 0)

    def test_gate_rejects_missing_id_naming_both_forms(self):
        """A missing bare id errors naming both the id and path interpretations."""
        rc = self._run_gate(["ship", "gate", "no-such-id"])
        self.assertEqual(rc, 1)
