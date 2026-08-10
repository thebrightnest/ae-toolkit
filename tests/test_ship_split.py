"""Tests for the aet-ship split command (`aet ship split`)."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_SHIP_PY = Path(__file__).parents[1] / "src" / "aet" / "cli" / "ship.py"
_spec = importlib.util.spec_from_loader(
    "aet_ship_split", importlib.machinery.SourceFileLoader("aet_ship_split", str(_SHIP_PY))
)
ship = importlib.util.module_from_spec(_spec)
sys.modules["aet_ship_split"] = ship
_spec.loader.exec_module(ship)


class MockResult:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestShipSplitParser(unittest.TestCase):
    """Argument parsing for the split subcommand."""

    def test_split_subcommand_parses_plan_and_groups(self):
        """aet ship split accepts a plan and repeated message/paths groups."""
        parser = ship.build_parser()
        args = parser.parse_args(
            [
                "split",
                "docs/plans/t1.md",
                "--message",
                "feat: add alpha",
                "--paths",
                "alpha.py",
                "--message",
                "feat: add beta",
                "--paths",
                "beta.py",
                "gamma.py",
            ]
        )
        self.assertEqual(args.command, "split")
        self.assertEqual(args.plan, "docs/plans/t1.md")
        self.assertEqual(args.message, ["feat: add alpha", "feat: add beta"])
        self.assertEqual(args.paths, [["alpha.py"], ["beta.py", "gamma.py"]])


class TestShipSplitCommand(unittest.TestCase):
    """Behavior-driven tests for `cmd_split`."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        base = Path(self.tmpdir.name)

        self.plan_path = base / "docs" / "plans" / "t1.md"
        self.plan_path.parent.mkdir(parents=True)
        self._write_plan(
            "---\n"
            "id: t1\n"
            "status: awaiting_merge\n"
            "---\n\n"
            "# Plan T1\n\n"
            "## Task List\n\n"
            "- [x] task one\n"
            "- [x] task two\n\n"
            "---\n\n"
            "*Stage: implemented*\n",
        )

        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)

    def _write_plan(self, content: str) -> None:
        self.plan_path.write_text(content, encoding="utf-8")

    def test_split_refuses_dirty_tree(self):
        """A dirty working tree stops split before resetting."""
        responses = {
            ("git", "rev-parse", "--show-toplevel"): (0, "/repo\n", ""),
            ("git", "status", "--short"): (0, " M src/aet/cli/ship.py\n", ""),
        }
        with patch.object(ship.subprocess, "run", side_effect=self._mock_run(responses)):
            rc = ship.cmd_split(
                ship.parse_args(
                    [
                        "split",
                        str(self.plan_path),
                        "--message",
                        "feat: one",
                        "--paths",
                        "a.py",
                    ]
                )
            )
        self.assertNotEqual(rc, 0)

    def test_split_refuses_empty_range(self):
        """No commits between base and HEAD stops split."""
        responses = {
            ("git", "rev-parse", "--show-toplevel"): (0, "/repo\n", ""),
            ("git", "status", "--short"): (0, "", ""),
            ("git", "rev-list", "--count", "origin/main..HEAD"): (0, "0\n", ""),
        }
        with patch.object(ship.subprocess, "run", side_effect=self._mock_run(responses)):
            rc = ship.cmd_split(
                ship.parse_args(
                    [
                        "split",
                        str(self.plan_path),
                        "--message",
                        "feat: one",
                        "--paths",
                        "a.py",
                    ]
                )
            )
        self.assertNotEqual(rc, 0)

    def test_split_refuses_mismatched_message_paths_count(self):
        """Different numbers of --message and --paths groups is an error."""
        responses = {
            ("git", "rev-parse", "--show-toplevel"): (0, "/repo\n", ""),
            ("git", "status", "--short"): (0, "", ""),
        }
        with patch.object(ship.subprocess, "run", side_effect=self._mock_run(responses)):
            rc = ship.cmd_split(
                ship.parse_args(
                    [
                        "split",
                        str(self.plan_path),
                        "--message",
                        "feat: one",
                        "--paths",
                        "a.py",
                        "--paths",
                        "b.py",
                    ]
                )
            )
        self.assertNotEqual(rc, 0)

    @staticmethod
    def _mock_run(responses):
        def mock_run(cmd, **kwargs):
            args = tuple(cmd)
            if args in responses:
                rc, out, err = responses[args]
                return MockResult(rc, out, err)
            return MockResult(1, "", f"unexpected: {cmd!r}")

        return mock_run


class TestShipSplitIntegration(unittest.TestCase):
    """Integration test using a real scratch git repository."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        base = Path(self.tmpdir.name)

        self.origin = base / "origin.git"
        self.origin.mkdir()
        self.clone = base / "repo"
        self.clone.mkdir()

        subprocess.run(["git", "init", "--bare", str(self.origin)], check=True, capture_output=True)
        subprocess.run(
            ["git", "clone", str(self.origin), str(self.clone)],
            check=True,
            capture_output=True,
        )
        self._git("config", "user.email", "test@example.com")
        self._git("config", "user.name", "Test User")
        readme = self.clone / "README.md"
        readme.write_text("hello\n", encoding="utf-8")
        self._git("add", "README.md")
        self._git("commit", "-m", "initial")
        self._git("push", "-u", "origin", "main")

        self._git("checkout", "-b", "feat-001")
        plan_dir = self.clone / "docs" / "plans"
        plan_dir.mkdir(parents=True)
        self.plan_path = plan_dir / "t1.md"
        self.plan_path.write_text(
            "---\n"
            "id: t1\n"
            "status: awaiting_merge\n"
            "---\n\n"
            "# Plan T1\n\n"
            "## Task List\n\n"
            "- [x] task one\n"
            "- [x] task two\n\n"
            "---\n\n"
            "*Stage: implemented*\n",
            encoding="utf-8",
        )
        (self.clone / "alpha.py").write_text("alpha\n", encoding="utf-8")
        (self.clone / "beta.py").write_text("beta\n", encoding="utf-8")
        self._git("add", ".")
        self._git("commit", "-m", "feat: add alpha and beta")

        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)

    def _git(self, *args):
        return subprocess.run(
            ["git", *args],
            cwd=str(self.clone),
            check=True,
            capture_output=True,
            text=True,
        )

    def _head_sha(self) -> str:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(self.clone),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def test_split_creates_commits_that_reproduce_original_tree(self):
        """Splitting into groups reproduces the original HEAD tree."""
        os.chdir(str(self.clone))
        original_sha = self._head_sha()
        rc = ship.cmd_split(
            ship.parse_args(
                [
                    "split",
                    str(self.plan_path),
                    "--message",
                    "feat: add alpha",
                    "--paths",
                    "alpha.py",
                    "--message",
                    "feat: add beta and plan",
                    "--paths",
                    "beta.py",
                    str(self.plan_path),
                ]
            )
        )
        self.assertEqual(rc, 0)
        diff = subprocess.run(
            ["git", "diff", f"{original_sha}..HEAD"],
            cwd=str(self.clone),
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertEqual(diff.strip(), "")
        log = subprocess.run(
            ["git", "log", "--oneline", "origin/main..HEAD"],
            cwd=str(self.clone),
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertIn("feat: add alpha", log)
        self.assertIn("feat: add beta and plan", log)

    def test_split_incomplete_grouping_exits_nonzero_with_recovery_sha(self):
        """Leaving paths uncommitted fails closed and names the recovery SHA."""
        os.chdir(str(self.clone))
        original_sha = self._head_sha()
        rc = ship.cmd_split(
            ship.parse_args(
                [
                    "split",
                    str(self.plan_path),
                    "--message",
                    "feat: add alpha only",
                    "--paths",
                    "alpha.py",
                ]
            )
        )
        self.assertNotEqual(rc, 0)
        diff = subprocess.run(
            ["git", "diff", f"{original_sha}..HEAD"],
            cwd=str(self.clone),
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertNotEqual(diff.strip(), "")


if __name__ == "__main__":
    unittest.main()
