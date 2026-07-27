"""Tests for the aet-ship PR creation command (`aet ship open`)."""

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

# Prefer the worktree source tree over any installed ``aet`` package.
_REPO_SRC = Path(__file__).parents[1] / "src"
if str(_REPO_SRC) not in sys.path:
    sys.path.insert(0, str(_REPO_SRC))

from aet.plan_parser import resolve_plan_arg  # noqa: E402

_SHIP_PY = Path(__file__).parents[1] / "src" / "aet" / "cli" / "ship.py"
_spec = importlib.util.spec_from_loader(
    "aet_ship_open", importlib.machinery.SourceFileLoader("aet_ship_open", str(_SHIP_PY))
)
ship = importlib.util.module_from_spec(_spec)
sys.modules["aet_ship_open"] = ship
_spec.loader.exec_module(ship)


class MockResult:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _subprocess_mock(responses, record=None):
    """Return a mock subprocess.run that answers git and test commands.

    responses maps tuple(program, *args) -> (returncode, stdout, stderr).
    """

    def mock_run(cmd, **kwargs):
        if record is not None:
            record.append(cmd if isinstance(cmd, str) else tuple(cmd))
        args = tuple(cmd)
        if args in responses:
            rc, out, err = responses[args]
            return MockResult(rc, out, err)
        return MockResult(1, "", f"unexpected: {cmd!r}")

    return mock_run


def _open_mock(responses, record=None):
    """Like _subprocess_mock but allows push and gh pr create to succeed."""
    base = _subprocess_mock(responses, record)

    def mock_run(cmd, **kwargs):
        if isinstance(cmd, list):
            if cmd[0] == "git" and cmd[1] == "push":
                if record is not None:
                    record.append(tuple(cmd))
                return MockResult(0, "", "")
            if cmd[0] == "gh" and cmd[1] == "pr" and cmd[2] == "create":
                if record is not None:
                    record.append(tuple(cmd))
                return MockResult(0, "https://github.com/org/repo/pull/42\n", "")
        return base(cmd, **kwargs)

    return mock_run


class TestShipOpenParser(unittest.TestCase):
    def test_open_subcommand_parses_plan_argument(self):
        """aet ship open accepts a plan file path."""
        parser = ship.build_parser()
        args = parser.parse_args(["open", "docs/plans/t1.md"])
        self.assertEqual(args.command, "open")
        self.assertEqual(args.plan, "docs/plans/t1.md")


class TestResolvePlanArg(unittest.TestCase):
    """Bare task ids resolve to the conventional docs/plans/<id>.md path."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        base = Path(self.tmpdir.name)
        plan_dir = base / "docs" / "plans"
        plan_dir.mkdir(parents=True)
        self.plan_path = plan_dir / "t1.md"
        self.plan_path.write_text("---\nid: t1\n---\n", encoding="utf-8")
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)

    def test_md_path_passes_through(self):
        """A .md argument is returned unchanged, even if the file is missing."""
        self.assertEqual(
            resolve_plan_arg("docs/plans/elsewhere.md"),
            "docs/plans/elsewhere.md",
        )

    def test_bare_id_resolves_to_conventional_plan_path(self):
        """A bare task id resolves to docs/plans/<id>.md when that file exists."""
        os.chdir(self.tmpdir.name)
        self.assertEqual(resolve_plan_arg("t1"), "docs/plans/t1.md")

    def test_bare_id_without_plan_file_raises(self):
        """A bare id with no conventional plan file errors naming both interpretations."""
        os.chdir(self.tmpdir.name)
        with self.assertRaises(ValueError) as ctx:
            resolve_plan_arg("no-such-task")
        self.assertIn("no-such-task", str(ctx.exception))
        self.assertIn("docs/plans/no-such-task.md", str(ctx.exception))


class TestDeterminePrBase(unittest.TestCase):
    """Regression guard for _determine_pr_base ref resolution.

    A branch whose fork point is behind origin/main (the normal state of a queued
    worktree once other plans have merged ahead of it) must resolve its PR base to
    origin/main, not to its own name. The bug: the branch's own tip decoration
    ``HEAD -> <branch>`` was stripped and returned as if it were a stacked parent,
    so ``gh pr create`` rejected head == base.
    """

    def _walk_responses(self, log_stdout):
        """Git responses that force _determine_pr_base into the ancestry-path walk."""
        return {
            ("git", "merge-base", "HEAD", "origin/main"): (0, "old-fork\n", ""),
            ("git", "rev-parse", "origin/main"): (0, "new-main\n", ""),
            (
                "git",
                "log",
                "--oneline",
                "--decorate",
                "--ancestry-path",
                "old-fork..HEAD",
            ): (0, log_stdout, ""),
        }

    def test_behind_main_independent_branch_resolves_to_origin_main(self):
        """A branch merely behind origin/main bases its PR on origin/main, not itself."""
        responses = self._walk_responses(
            "22400d8c (HEAD -> feat-001, origin/feat-001) feat: do a thing\n"
        )
        with patch.object(
            ship.subprocess, "run", side_effect=_subprocess_mock(responses)
        ):
            self.assertEqual(ship._determine_pr_base(), "origin/main")

    def test_genuinely_stacked_branch_resolves_to_parent(self):
        """A branch stacked on a parent feature branch keeps the parent as its base."""
        responses = self._walk_responses(
            "aaaaaaa (HEAD -> feat-child, origin/feat-child) child commit\n"
            "bbbbbbb (feat-parent, origin/feat-parent) parent commit\n"
        )
        with patch.object(
            ship.subprocess, "run", side_effect=_subprocess_mock(responses)
        ):
            self.assertEqual(ship._determine_pr_base(), "feat-parent")


class TestShipOpenChecks(unittest.TestCase):
    """Behavior-driven tests for aet ship open decisions."""

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
            "- [x] task one\n\n"
            "---\n\n"
            "*Stage: implemented*\n",
        )

        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)

    def _write_plan(self, content: str) -> None:
        self.plan_path.write_text(content, encoding="utf-8")

    def _base_responses(self, branch="feat-001", pr_base="origin/main"):
        """Default happy-path git responses (independent branch, no rebase)."""
        origin_main = "origin-main-sha"
        return {
            ("git", "fetch", "origin"): (0, "", ""),
            ("git", "merge-base", "HEAD", "origin/main"): (
                0,
                f"{origin_main}\n",
                "",
            ),
            ("git", "rev-parse", "origin/main"): (0, f"{origin_main}\n", ""),
            ("git", "branch", "--show-current"): (0, f"{branch}\n", ""),
            ("git", "status", "--short"): (0, "", ""),
            ("git", "diff", pr_base, "--name-only"): (
                0,
                "src/aet/cli/ship.py\n",
                "",
            ),
            ("git", "rev-list", "--count", f"{pr_base}..HEAD"): (0, "1\n", ""),
            (
                "git",
                "log",
                f"{pr_base}..HEAD",
                "--pretty=format:%s",
            ): (0, "feat: add open command\n", ""),
            ("true",): (0, "", ""),
        }

    def test_open_refuses_to_proceed_when_gate_fails(self):
        """If the gate reports failure, open exits before pushing or creating a PR."""
        responses = self._base_responses()
        responses[("git", "status", "--short")] = (
            0,
            " M src/aet/cli/ship.py\n",
            "",
        )
        env = {"AET_SHIP_TEST_CMD": "true"}
        commands: list[tuple[str, ...]] = []

        with patch.dict(os.environ, env):
            with patch.object(
                ship.subprocess, "run", side_effect=_open_mock(responses, commands)
            ):
                rc = ship.cmd_open(ship.parse_args(["open", str(self.plan_path)]))

        self.assertNotEqual(rc, 0)
        self.assertFalse(any(c[0] == "gh" for c in commands))
        self.assertFalse(any(c[0] == "git" and c[1] == "push" for c in commands))

    def test_open_stops_on_monolithic_commit(self):
        """A single commit spanning the range with >1 task stops the PR."""
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
        responses = self._base_responses()
        env = {"AET_SHIP_TEST_CMD": "true"}
        commands: list[tuple[str, ...]] = []

        with patch.dict(os.environ, env):
            with patch.object(
                ship.subprocess, "run", side_effect=_open_mock(responses, commands)
            ):
                rc = ship.cmd_open(ship.parse_args(["open", str(self.plan_path)]))

        self.assertNotEqual(rc, 0)
        self.assertFalse(any(c[0] == "gh" for c in commands))
        self.assertFalse(any(c[0] == "git" and c[1] == "push" for c in commands))

    def test_open_generates_changelog_entry(self):
        """The changelog entry references the plan and lists commit subjects."""
        entry = ship._generate_changelog_entry(
            ["feat: add open", "feat: wire parser"], self.plan_path
        )
        self.assertIn("Plan T1", entry)
        self.assertIn("t1", entry)
        self.assertIn("feat: add open", entry)
        self.assertIn("feat: wire parser", entry)

    def test_open_pushes_force_with_lease_after_rebase(self):
        """When the gate rebased onto origin/main, push uses force-with-lease."""
        responses = self._base_responses()
        # Make the branch independent but behind origin/main so the gate rebases.
        responses[("git", "merge-base", "HEAD", "origin/main")] = (
            0,
            "old-merge-base\n",
            "",
        )
        responses[
            ("git", "rebase", "--onto", "origin/main", "old-merge-base", "feat-001")
        ] = (0, "", "")
        env = {"AET_SHIP_TEST_CMD": "true"}
        commands: list[tuple[str, ...]] = []

        with patch.dict(os.environ, env):
            with patch.object(
                ship.subprocess, "run", side_effect=_open_mock(responses, commands)
            ):
                rc = ship.cmd_open(ship.parse_args(["open", str(self.plan_path)]))

        self.assertEqual(rc, 0)
        push_cmds = [c for c in commands if c[0] == "git" and c[1] == "push"]
        self.assertEqual(len(push_cmds), 1)
        self.assertIn("--force-with-lease", push_cmds[0])
        gh_cmds = [c for c in commands if c[0] == "gh"]
        self.assertEqual(len(gh_cmds), 1)
        self.assertIn("pr", gh_cmds[0])
        self.assertIn("create", gh_cmds[0])

    def test_open_pushes_normal_when_not_rebased(self):
        """When no rebase occurs, open uses a plain git push."""
        responses = self._base_responses()
        env = {"AET_SHIP_TEST_CMD": "true"}
        commands: list[tuple[str, ...]] = []

        with patch.dict(os.environ, env):
            with patch.object(
                ship.subprocess, "run", side_effect=_open_mock(responses, commands)
            ):
                rc = ship.cmd_open(ship.parse_args(["open", str(self.plan_path)]))

        self.assertEqual(rc, 0)
        push_cmds = [c for c in commands if c[0] == "git" and c[1] == "push"]
        self.assertEqual(len(push_cmds), 1)
        self.assertNotIn("--force-with-lease", push_cmds[0])

    def test_open_accepts_bare_task_id(self):
        """aet ship open <task-id> resolves the plan via docs/plans/<id>.md."""
        os.chdir(self.tmpdir.name)
        responses = self._base_responses()
        env = {"AET_SHIP_TEST_CMD": "true"}
        commands: list[tuple[str, ...]] = []

        with patch.dict(os.environ, env):
            with patch.object(
                ship.subprocess, "run", side_effect=_open_mock(responses, commands)
            ):
                rc = ship.cmd_open(ship.parse_args(["open", "t1"]))

        self.assertEqual(rc, 0)
        gh_cmds = [c for c in commands if c[0] == "gh"]
        self.assertEqual(len(gh_cmds), 1)

    def test_open_bare_id_without_plan_file_fails_cleanly(self):
        """aet ship open <task-id> fails with a clear error when no plan matches."""
        os.chdir(self.tmpdir.name)
        responses = self._base_responses()

        with patch.object(
            ship.subprocess, "run", side_effect=_subprocess_mock(responses)
        ):
            rc = ship.cmd_open(ship.parse_args(["open", "no-such-task"]))

        self.assertNotEqual(rc, 0)

    def test_open_pr_body_includes_scope_audit_when_present(self):
        """The PR body contains a scope-audit section when files are flagged."""
        body = ship._build_pr_body(
            self.plan_path,
            "origin/main",
            ["docs/plans/OTHER-01.md"],
            "changelog\n",
        )
        self.assertIn("Scope audit", body)
        self.assertIn("OTHER-01.md", body)

    def test_open_pr_body_omits_scope_audit_when_empty(self):
        """The PR body has no scope-audit section when nothing is flagged."""
        body = ship._build_pr_body(
            self.plan_path, "origin/main", [], "changelog\n"
        )
        self.assertNotIn("Scope audit", body)

    def test_open_pr_body_includes_stacked_warning_when_not_main(self):
        """The PR body warns when the base is a feature branch."""
        body = ship._build_pr_body(
            self.plan_path, "origin/feat-parent", [], "changelog\n"
        )
        self.assertIn("STACKED PR", body)
        self.assertIn("origin/feat-parent", body)

    def test_open_pr_body_omits_stacked_warning_when_main(self):
        """The PR body has no stacked-PR warning when the base is origin/main."""
        body = ship._build_pr_body(
            self.plan_path, "origin/main", [], "changelog\n"
        )
        self.assertNotIn("STACKED PR", body)

    def test_open_release_guard_blocks_chore_release_commit(self):
        """A chore(release) commit in the range stops PR creation."""
        responses = self._base_responses()
        responses[("git", "log", "origin/main..HEAD", "--pretty=format:%s")] = (
            0,
            "chore(release): bump version\n",
            "",
        )
        env = {"AET_SHIP_TEST_CMD": "true"}
        commands: list[tuple[str, ...]] = []

        with patch.dict(os.environ, env):
            with patch.object(
                ship.subprocess, "run", side_effect=_open_mock(responses, commands)
            ):
                rc = ship.cmd_open(ship.parse_args(["open", str(self.plan_path)]))

        self.assertNotEqual(rc, 0)
        self.assertFalse(any(c[0] == "gh" for c in commands))

    def test_open_release_guard_blocks_version_change(self):
        """A VERSION file change in the diff stops PR creation."""
        responses = self._base_responses()
        responses[("git", "diff", "origin/main", "--name-only")] = (
            0,
            "src/aet/cli/ship.py\nVERSION\n",
            "",
        )
        env = {"AET_SHIP_TEST_CMD": "true"}
        commands: list[tuple[str, ...]] = []

        with patch.dict(os.environ, env):
            with patch.object(
                ship.subprocess, "run", side_effect=_open_mock(responses, commands)
            ):
                rc = ship.cmd_open(ship.parse_args(["open", str(self.plan_path)]))

        self.assertNotEqual(rc, 0)
        self.assertFalse(any(c[0] == "gh" for c in commands))


class TestShipOpenIntegration(unittest.TestCase):
    """Integration test using a real scratch git repository."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        base = Path(self.tmpdir.name)

        self.origin = base / "origin.git"
        self.origin.mkdir()
        self.clone = base / "repo"
        self.clone.mkdir()

        subprocess.run(
            ["git", "init", "--bare", str(self.origin)], check=True, capture_output=True
        )
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
            "- [x] task one\n\n"
            "---\n\n"
            "*Stage: implemented*\n",
            encoding="utf-8",
        )
        src_dir = self.clone / "src" / "aet" / "cli"
        src_dir.mkdir(parents=True)
        (src_dir / "ship.py").write_text("# ship\n", encoding="utf-8")
        self._git("add", ".")
        self._git("commit", "-m", "feat: ship open")

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

    def test_open_integration_happy_path(self):
        """The full open flow runs against a real git repo with mocked gh."""
        os.chdir(str(self.clone))
        env = {"AET_SHIP_TEST_CMD": "true"}
        commands: list[tuple[str, ...]] = []

        original_run = ship.subprocess.run

        def _recording_run(cmd, **kwargs):
            commands.append(tuple(cmd))
            if isinstance(cmd, list):
                if cmd[0] == "git" and cmd[1] == "push":
                    return MockResult(0, "", "")
                if cmd[0] == "gh" and cmd[1:3] == ["pr", "create"]:
                    return MockResult(0, "https://github.com/org/repo/pull/7\n", "")
            return original_run(cmd, **kwargs)

        with patch.dict(os.environ, env):
            with patch.object(ship.subprocess, "run", side_effect=_recording_run):
                rc = ship.cmd_open(ship.parse_args(["open", str(self.plan_path)]))

        self.assertEqual(rc, 0)
        self.assertTrue(any(c[0] == "gh" for c in commands))
        push_cmds = [c for c in commands if c[0] == "git" and c[1] == "push"]
        self.assertEqual(len(push_cmds), 1)
