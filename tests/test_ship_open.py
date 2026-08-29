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

from aet import plan_parser
from aet.backends.git_refs_backend import GitRefsBackend

# Prefer the worktree source tree over any installed ``aet`` package.
_REPO_SRC = Path(__file__).parents[1] / "src"
if str(_REPO_SRC) not in sys.path:
    sys.path.insert(0, str(_REPO_SRC))

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


def _subprocess_mock(responses, record=None, branch="feat-001"):
    """Return a mock subprocess.run that answers git and test commands.

    Unknown commands are delegated to the real subprocess so the git-refs backend
    can operate on the temporary repository.
    """
    real_run = subprocess.run

    def _lookup(cmd):
        if isinstance(cmd, str):
            if cmd in responses:
                return responses[cmd]
            return None
        args = list(cmd)
        if len(args) >= 3 and args[0] == "git" and args[1] == "-C":
            args = ["git"] + args[3:]
        t_args = tuple(args)
        if t_args in responses:
            return responses[t_args]

        for key in responses:
            if not isinstance(key, tuple):
                continue
            if len(key) == len(args):
                match = True
                for a, k in zip(args, key):
                    if a == k:
                        continue
                    if ".." in a and ".." in k and a.split("..")[0] == k.split("..")[0]:
                        continue
                    if a in ("HEAD", branch, f"origin/{branch}") and k in ("HEAD", branch, f"origin/{branch}"):
                        continue
                    match = False
                    break
                if match:
                    return responses[key]
            # Match ("git", "diff", "base..branch", "--name-only") with ("git", "diff", "base", "--name-only")
            if len(args) == len(key) and len(args) >= 3 and args[1] == "diff" and ".." in args[2]:
                normalized = [args[0], args[1], args[2].split("..")[0]] + args[3:]
                if tuple(normalized) == key:
                    return responses[key]

        if len(args) >= 3 and args[1] == "-c":
            for key, value in responses.items():
                if isinstance(key, tuple) and len(key) >= 3 and key[1] == "-c" and key[2] == args[2]:
                    return value
        return None

    def mock_run(cmd, **kwargs):
        if record is not None:
            record.append(cmd if isinstance(cmd, str) else tuple(cmd))
        hit = _lookup(cmd)
        if hit is not None:
            rc, out, err = hit
            return MockResult(rc, out, err)
        return real_run(cmd, **kwargs)

    return mock_run


def _open_mock(responses, record=None):
    """Like _subprocess_mock but allows push and gh pr create to succeed."""
    sub_mock = _subprocess_mock(responses, record)

    def mock_run(cmd, **kwargs):
        if isinstance(cmd, list):
            is_push = (cmd[0] == "git" and cmd[1] == "push") or (
                len(cmd) >= 4 and cmd[0] == "git" and cmd[1] == "-C" and cmd[3] == "push"
            )
            if is_push:
                if record is not None:
                    record.append(tuple(cmd))
                return MockResult(0, "", "")
            if cmd[0] == "gh" and cmd[1] == "pr" and cmd[2] == "create":
                if record is not None:
                    record.append(tuple(cmd))
                return MockResult(0, "https://github.com/org/repo/pull/42\n", "")
        return sub_mock(cmd, **kwargs)

    return mock_run


class TestShipOpenParser(unittest.TestCase):
    def test_open_subcommand_parses_task_argument(self):
        """aet ship open accepts a task id."""
        parser = ship.build_parser()
        args = parser.parse_args(["open", "t1"])
        self.assertEqual(args.command, "open")
        self.assertEqual(args.plan, "t1")


class TestDeterminePrBase(unittest.TestCase):
    """Regression guard for _determine_pr_base ref resolution.

    A branch whose fork point is behind origin/main (the normal state of a queued
    worktree once other plans have merged ahead of it) must resolve its PR base to
    origin/main, not to itself. The bug: the branch's own tip decoration
    ``HEAD -> <branch>`` was stripped and returned as if it were a stacked parent,
    so ``gh pr create`` rejected head == base.
    """

    def _walk_responses(self, log_stdout, trunk_ref="origin/main"):
        """Git responses that force _determine_pr_base into the ancestry-path walk."""
        return {
            ("git", "rev-parse", "--show-toplevel"): (0, "/repo\n", ""),
            ("git", "merge-base", "HEAD", trunk_ref): (0, "old-fork\n", ""),
            ("git", "rev-parse", trunk_ref): (0, "new-trunk\n", ""),
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
        responses = self._walk_responses("22400d8c (HEAD -> feat-001, origin/feat-001) feat: do a thing\n")
        with patch.object(ship.subprocess, "run", side_effect=_subprocess_mock(responses)):
            stack = ship._determine_pr_base()
        self.assertEqual(stack.base_ref, "origin/main")
        self.assertIsNone(stack.parent)
        self.assertEqual(stack.trunk_ref, "origin/main")

    def test_genuinely_stacked_branch_resolves_to_parent(self):
        """A branch stacked on a parent feature branch keeps the parent as its base."""
        responses = self._walk_responses(
            "aaaaaaa (HEAD -> feat-child, origin/feat-child) child commit\n"
            "bbbbbbb (feat-parent, origin/feat-parent) parent commit\n"
        )
        with patch.object(ship.subprocess, "run", side_effect=_subprocess_mock(responses)):
            stack = ship._determine_pr_base()
        self.assertEqual(stack.base_ref, "feat-parent")
        self.assertEqual(stack.parent, "feat-parent")
        self.assertEqual(stack.trunk_ref, "origin/main")

    def test_stacked_branch_reports_position_and_trunk(self):
        """The stack result names the parent branch, position, and resolved trunk."""
        responses = self._walk_responses(
            "aaaaaaa (HEAD -> feat-child, origin/feat-child) child commit\n"
            "bbbbbbb (feat-parent, origin/feat-parent) parent commit\n"
        )
        with patch.object(ship.subprocess, "run", side_effect=_subprocess_mock(responses)):
            stack = ship._determine_pr_base()
        self.assertIn("PR", stack.position)
        self.assertIn("feat-parent", stack.position)


class TestShipOpenChecks(unittest.TestCase):
    """Behavior-driven tests for aet ship open decisions."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        base = Path(self.tmpdir.name)

        self.repo = base / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "-C", str(self.repo), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Test User"], check=True)
        (self.repo / ".agents").mkdir(parents=True, exist_ok=True)
        (self.repo / "README.md").write_text("hello\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-q", "-m", "initial"], check=True)

        self.plan_path = self.repo / "docs" / "plans" / "t1.md"
        self.plan_path.parent.mkdir(parents=True)
        self._default_content = (
            "---\n"
            "id: t1\n"
            "status: awaiting_merge\n"
            "---\n\n"
            "# Plan T1\n\n"
            "## Task List\n\n"
            "- [x] task one\n\n"
            "---\n\n"
            "*Stage: implemented*\n"
        )
        self.plan_path.write_text(self._default_content, encoding="utf-8")
        self._save_task(self._spec())

        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        os.chdir(self.repo)

    def _spec(self, content: str | None = None) -> dict:
        """Build a spec dict from the given plan content."""
        text = content if content is not None else self.plan_path.read_text(encoding="utf-8")
        return plan_parser.extract_plan_spec_from_text(text, "t1")

    def _save_task(self, spec: dict, task_id: str = "t1") -> None:
        backend = GitRefsBackend(
            queue_file=str(self.repo / ".agents" / "aet-queue"),
            history_file=str(self.repo / ".agents" / "work-history.jsonl"),
        )
        data = backend.load()
        queue = data["queue"]
        task = next((t for t in queue if t.get("id") == task_id), None)
        if task is None:
            task = {
                "id": task_id,
                "state": "awaiting_merge",
                "stage": "qa-complete",
                "branch": "feat-001",
                "plan_file": str(Path("docs/plans") / f"{task_id}.md"),
            }
            queue.append(task)
        task["spec"] = spec
        backend.save(queue)

    def _base_responses(self, branch="feat-001", pr_base="origin/main"):
        """Default happy-path git responses (independent branch, no rebase)."""
        origin_main = "origin-main-sha"
        return {
            ("git", "rev-parse", "--show-toplevel"): (0, f"{self.repo}\n", ""),
            ("git", "fetch", "origin"): (0, "", ""),
            ("git", "rev-parse", "--verify", "--quiet", branch): (0, "", ""),
            ("git", "rev-parse", "--verify", "--quiet", f"origin/{branch}"): (0, "", ""),
            ("git", "rev-parse", "--verify", "--quiet", "t1"): (0, "", ""),
            ("git", "rev-parse", "--verify", "--quiet", "origin/t1"): (0, "", ""),
            ("git", "worktree", "list", "--porcelain"): (0, f"worktree {self.repo}\nbranch refs/heads/{branch}\n", ""),
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
            with patch.object(ship.subprocess, "run", side_effect=_open_mock(responses, commands)):
                rc = ship.cmd_open(ship.parse_args(["open", "t1"]))

        self.assertNotEqual(rc, 0)
        self.assertFalse(any(c[0] == "gh" for c in commands))
        self.assertFalse(any(c[0] == "git" and c[1] == "push" for c in commands))

    def test_open_stops_on_monolithic_commit(self):
        """A single commit spanning the range with >1 task stops the PR."""
        content = (
            "---\n"
            "id: t1\n"
            "status: awaiting_merge\n"
            "---\n\n"
            "# Plan T1\n\n"
            "## Task List\n\n"
            "- [x] task one\n"
            "- [x] task two\n\n"
            "---\n\n"
            "*Stage: implemented*\n"
        )
        self._save_task(self._spec(content))
        responses = self._base_responses()
        env = {"AET_SHIP_TEST_CMD": "true"}
        commands: list[tuple[str, ...]] = []

        with patch.dict(os.environ, env):
            with patch.object(ship.subprocess, "run", side_effect=_open_mock(responses, commands)):
                rc = ship.cmd_open(ship.parse_args(["open", "t1"]))

        self.assertNotEqual(rc, 0)
        self.assertFalse(any(c[0] == "gh" for c in commands))
        self.assertFalse(any(c[0] == "git" and c[1] == "push" for c in commands))

    def test_open_generates_changelog_entry(self):
        """The changelog entry references the task id and title and lists commit subjects."""
        entry = ship._generate_changelog_entry(["feat: add open", "feat: wire parser"], self._spec())
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
        responses[("git", "rebase", "--onto", "origin/main", "old-merge-base", "feat-001")] = (0, "", "")
        responses[("git", "log", "--oneline", "--decorate", "--ancestry-path", "old-merge-base..HEAD")] = (0, "", "")
        env = {"AET_SHIP_TEST_CMD": "true"}
        commands: list[tuple[str, ...]] = []

        with patch.dict(os.environ, env):
            with patch.object(ship.subprocess, "run", side_effect=_open_mock(responses, commands)):
                rc = ship.cmd_open(ship.parse_args(["open", "t1"]))

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
            with patch.object(ship.subprocess, "run", side_effect=_open_mock(responses, commands)):
                rc = ship.cmd_open(ship.parse_args(["open", "t1"]))

        self.assertEqual(rc, 0)
        push_cmds = [c for c in commands if c[0] == "git" and c[1] == "push"]
        self.assertEqual(len(push_cmds), 1)
        self.assertNotIn("--force-with-lease", push_cmds[0])

    def test_open_missing_task_fails_cleanly(self):
        """aet ship open fails with a clear error when no task record exists."""
        responses = self._base_responses()

        with patch.object(ship.subprocess, "run", side_effect=_subprocess_mock(responses)):
            rc = ship.cmd_open(ship.parse_args(["open", "no-such-task"]))

        self.assertNotEqual(rc, 0)

    def test_open_pr_body_includes_scope_audit_when_present(self):
        """The PR body contains a scope-audit section when files are flagged."""
        content = (
            "---\n"
            "id: t1\n"
            "status: awaiting_merge\n"
            "---\n\n"
            "# Plan T1\n\n"
            "Source: `docs/prds/demo-prd.md`\n\n"
            "---\n\n"
            "*Stage: implemented*\n"
        )
        body = ship._build_pr_body(
            self._spec(content),
            ship.StackInfo(trunk_ref="origin/main", base_ref="origin/main", parent=None, position=None),
            ["docs/prds/OTHER-01.md"],
            "changelog\n",
        )
        self.assertIn("Scope audit", body)
        self.assertIn("OTHER-01.md", body)

    def test_open_pr_body_omits_scope_audit_when_empty(self):
        """The PR body has no scope-audit section when nothing is flagged."""
        body = ship._build_pr_body(
            self._spec(),
            ship.StackInfo(trunk_ref="origin/main", base_ref="origin/main", parent=None, position=None),
            [],
            "changelog\n",
        )
        self.assertNotIn("Scope audit", body)

    def test_open_pr_body_includes_stacked_warning_when_not_main(self):
        """The PR body warns when the base is a feature branch."""
        body = ship._build_pr_body(
            self._spec(),
            ship.StackInfo(
                trunk_ref="origin/main",
                base_ref="feat-parent",
                parent="feat-parent",
                position="PR 2 of 2",
            ),
            [],
            "changelog\n",
        )
        self.assertIn("STACKED PR", body)
        self.assertIn("feat-parent", body)
        self.assertIn("PR 2 of 2", body)
        self.assertIn("origin/main", body)

    def test_open_pr_body_omits_stacked_warning_when_main(self):
        """The PR body has no stacked-PR warning when the base is origin/main."""
        body = ship._build_pr_body(
            self._spec(),
            ship.StackInfo(trunk_ref="origin/main", base_ref="origin/main", parent=None, position=None),
            [],
            "changelog\n",
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
            with patch.object(ship.subprocess, "run", side_effect=_open_mock(responses, commands)):
                rc = ship.cmd_open(ship.parse_args(["open", "t1"]))

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
            with patch.object(ship.subprocess, "run", side_effect=_open_mock(responses, commands)):
                rc = ship.cmd_open(ship.parse_args(["open", "t1"]))

        self.assertNotEqual(rc, 0)
        self.assertFalse(any(c[0] == "gh" for c in commands))

    def test_open_stacked_branch_prints_trunk_in_stop_note(self):
        """The terminal stop-note names the resolved trunk, not hardcoded main."""
        stack = ship.StackInfo(
            trunk_ref="origin/trunk",
            base_ref="origin/feat-parent",
            parent="feat-parent",
            position="PR 2 of 2",
        )
        gate_result = ship.GateResult(
            ok=True,
            pr_base="origin/feat-parent",
            stack=stack,
            rebased=False,
            scope_audit=[],
            dry_run=False,
            message="Gate passed.",
        )
        with (
            patch.object(ship, "_run_gate", return_value=gate_result),
            patch.object(ship, "_check_release_guard", return_value=None),
            patch.object(ship, "_is_monolithic_commit", return_value=False),
            patch.object(ship, "_push_branch", return_value=(True, "")),
            patch.object(ship, "_create_pr", return_value=(True, "https://github.com/org/repo/pull/99\n")),
        ):
            from io import StringIO

            stdout_capture = StringIO()
            with patch.object(sys, "stdout", stdout_capture):
                rc = ship.cmd_open(ship.parse_args(["open", "t1"]))
        self.assertEqual(rc, 0)
        output = stdout_capture.getvalue()
        self.assertIn("STACKED PR", output)
        self.assertIn("trunk", output)
        self.assertNotIn("main", output)

    def test_open_stacked_branch_writes_cut_ledger_event(self):
        """A successful stacked PR open records a cut/pr ledger fact."""
        stack = ship.StackInfo(
            trunk_ref="origin/main",
            base_ref="origin/feat-parent",
            parent="feat-parent",
            position="PR 2 of 2",
        )
        gate_result = ship.GateResult(
            ok=True,
            pr_base="origin/feat-parent",
            stack=stack,
            rebased=False,
            scope_audit=[],
            dry_run=False,
            message="Gate passed.",
        )
        captured = []

        def fake_write_event(**kwargs):
            captured.append(kwargs)
            return {"id": "fake"}

        with (
            patch.object(ship, "_run_gate", return_value=gate_result),
            patch.object(ship, "_check_release_guard", return_value=None),
            patch.object(ship, "_is_monolithic_commit", return_value=False),
            patch.object(ship, "_push_branch", return_value=(True, "")),
            patch.object(ship, "_create_pr", return_value=(True, "https://github.com/org/repo/pull/99\n")),
            patch.object(ship.Ledger, "write_event", side_effect=fake_write_event),
        ):
            rc = ship.cmd_open(ship.parse_args(["open", "t1"]))

        self.assertEqual(rc, 0)
        self.assertEqual(len(captured), 1)
        event = captured[0]
        self.assertEqual(event["source"], "aet-ship")
        self.assertEqual(event["task"], "t1")
        self.assertEqual(event["kind"], "cut")
        self.assertEqual(event["ref"], "https://github.com/org/repo/pull/99")
        self.assertEqual(event["ref_kind"], "pr")
        self.assertEqual(event["payload"]["pr_base"], "origin/feat-parent")
        self.assertTrue(event["payload"]["stacked"])
        self.assertEqual(event["payload"]["parent"], "feat-parent")


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
        (self.clone / ".agents").mkdir(parents=True, exist_ok=True)
        self._git("add", "README.md")
        self._git("commit", "-m", "initial")
        self._git("push", "-u", "origin", "main")

        self._git("checkout", "-b", "feat-001")
        plan_dir = self.clone / "docs" / "plans"
        plan_dir.mkdir(parents=True)
        self.plan_path = plan_dir / "t1.md"
        plan_content = (
            "---\n"
            "id: t1\n"
            "status: awaiting_merge\n"
            "---\n\n"
            "# Plan T1\n\n"
            "## Task List\n\n"
            "- [x] task one\n\n"
            "---\n\n"
            "*Stage: implemented*\n"
        )
        self.plan_path.write_text(plan_content, encoding="utf-8")
        spec = plan_parser.extract_plan_spec_from_text(plan_content, "t1")
        backend = GitRefsBackend(
            queue_file=str(self.clone / ".agents" / "aet-queue"),
            history_file=str(self.clone / ".agents" / "work-history.jsonl"),
        )
        backend.save(
            [
                {
                    "id": "t1",
                    "state": "awaiting_merge",
                    "stage": "qa-complete",
                    "branch": "feat-001",
                    "plan_file": "docs/plans/t1.md",
                    "spec": spec,
                }
            ]
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
                rc = ship.cmd_open(ship.parse_args(["open", "t1"]))

        self.assertEqual(rc, 0)
        self.assertTrue(any(c[0] == "gh" for c in commands))
        push_cmds = [c for c in commands if c[0] == "git" and c[1] == "push"]

        self.assertEqual(len(push_cmds), 1)
        self.assertNotIn("--force-with-lease", push_cmds[0])


if __name__ == "__main__":
    unittest.main()
