"""Tests for the aet multicall dispatcher (src/aet/cli/main.py).

Every test that calls ``aet.main()`` isolates the bin dir via
``AET_BIN_DIR`` pointed at a temp dir: ``main()`` runs the on-invocation
symlink self-repair, and an unisolated call from a worktree checkout would
re-point the real ``~/.local/bin/aet`` at the ephemeral worktree copy.
"""

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).parents[2]
_AET_PY = _REPO_ROOT / "src" / "aet" / "cli" / "main.py"

_aet_spec = importlib.util.spec_from_loader(
    "aet_dispatcher",
    importlib.machinery.SourceFileLoader("aet_dispatcher", str(_AET_PY)),
)
aet = importlib.util.module_from_spec(_aet_spec)
_aet_spec.loader.exec_module(aet)


class _IsolatedBinDir(unittest.TestCase):
    """Temp ``AET_BIN_DIR`` so self-repair never touches ``~/.local/bin``."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.bin_dir = Path(self._tmp.name) / "bin"

    def _bin_env(self):
        return patch.dict(os.environ, {"AET_BIN_DIR": str(self.bin_dir)})


class TestAetSpecTable(unittest.TestCase):
    """The SUBCOMMANDS spec is importable data shared by dispatch and tooling."""

    def test_spec_covers_all_operational_subcommands(self):
        """SUBCOMMANDS lists every operational toolkit command from R-1."""
        expected = {
            "sprint",
            "backlog",
            "desk",
            "review",
            "status",
            "next",
            "sync",
            "report",
            "metrics",
            "reconcile",
            "init-queue",
            "state",
            "gate",
            "plan",
            "plans",
            "docs",
            "panel",
            "run",
            "run-one",
            "ship",
            "retro",
            "mine-learnings",
            "configure-backend",
            "hooks",
            "harness-guard",
            "release-prep",
            "install",
        }
        self.assertEqual(set(aet.SUBCOMMANDS), expected)

    def test_spec_entries_declare_target_and_mode(self):
        """Every entry has a (skill-dir, bin-name) target and a dispatch mode."""
        for name, spec in aet.SUBCOMMANDS.items():
            with self.subTest(name=name):
                skill_dir, bin_name = spec["target"]
                self.assertIn(spec["mode"], ("exec", "run", "run-one", "internal"))
                self.assertTrue(skill_dir)
                self.assertTrue(bin_name)

    def test_spec_targets_exist_in_repo(self):
        """Every spec target resolves to a real runnable file in the repo layout."""
        for name, spec in aet.SUBCOMMANDS.items():
            skill_dir, bin_name = spec["target"]
            with self.subTest(name=name):
                if skill_dir == "aet.cli":
                    binary = _REPO_ROOT / "src" / "aet" / "cli" / f"{bin_name}.py"
                else:
                    binary = _REPO_ROOT / skill_dir / "bin" / bin_name
                self.assertTrue(binary.is_file(), f"missing {binary}")


class TestAetExecRouting(_IsolatedBinDir):
    """Exec-mode subcommands reach their target binary with argv forwarded."""

    @classmethod
    def setUpClass(cls):
        cls.skills_root = _REPO_ROOT

    def _expect_exec(self, expected_bin, expected_argv):
        def mock_execvp(path, argv):
            self.assertEqual(Path(path), Path(sys.executable))
            self.assertEqual(
                argv, [sys.executable, str(expected_bin), *expected_argv[1:]]
            )
            raise SystemExit(0)

        return mock_execvp

    def _dispatch(self, argv, expected_bin, expected_argv):
        with patch.object(sys, "argv", argv):
            with self._bin_env():
                with patch.object(
                    aet.os, "execvp", self._expect_exec(expected_bin, expected_argv)
                ):
                    return aet.main()

    def test_status_routes_to_aet_work_status(self):
        """`aet status --queue-file foo.json` execs src/aet/cli/status.py verbatim."""
        rc = self._dispatch(
            ["aet", "status", "--queue-file", "foo.json"],
            self.skills_root / "src" / "aet" / "cli" / "status.py",
            ["status", "--queue-file", "foo.json"],
        )
        self.assertEqual(rc, 0)

    def test_state_routes_to_aet_state_binary(self):
        """`aet state audit` execs src/aet/cli/aet-state.py with args verbatim."""
        rc = self._dispatch(
            ["aet", "state", "audit"],
            self.skills_root / "src" / "aet" / "cli" / "aet-state.py",
            ["aet-state", "audit"],
        )
        self.assertEqual(rc, 0)

    def test_sprint_routes_to_aet_work_sprint_binary(self):
        """`aet sprint add <plan>` execs src/aet/cli/sprint.py with args verbatim."""
        rc = self._dispatch(
            ["aet", "sprint", "add", "docs/plans/x.md"],
            self.skills_root / "src" / "aet" / "cli" / "sprint.py",
            ["sprint", "add", "docs/plans/x.md"],
        )
        self.assertEqual(rc, 0)

    def test_reconcile_routes_to_aet_work_reconcile_binary(self):
        """`aet reconcile` execs src/aet/cli/reconcile.py with args verbatim."""
        rc = self._dispatch(
            ["aet", "reconcile", "--apply"],
            self.skills_root / "src" / "aet" / "cli" / "reconcile.py",
            ["reconcile", "--apply"],
        )
        self.assertEqual(rc, 0)

    def test_backlog_routes_to_aet_work_backlog_binary(self):
        """`aet backlog add <plan>` execs src/aet/cli/backlog.py with args verbatim."""
        rc = self._dispatch(
            ["aet", "backlog", "add", "docs/plans/x.md"],
            self.skills_root / "src" / "aet" / "cli" / "backlog.py",
            ["backlog", "add", "docs/plans/x.md"],
        )
        self.assertEqual(rc, 0)

    def test_top_level_add_is_unknown_subcommand(self):
        """Bare `aet add` is no longer a valid subcommand."""
        import io

        stderr = io.StringIO()
        with patch.object(sys, "argv", ["aet", "add", "docs/plans/x.md"]):
            with patch.object(sys, "stderr", stderr):
                with self._bin_env():
                    with patch.object(aet.os, "execvp") as mock_exec:
                        rc = aet.main()
        self.assertEqual(rc, 2)
        mock_exec.assert_not_called()
        self.assertIn("unknown subcommand 'add'", stderr.getvalue())

    def test_ship_routes_to_package(self):
        """`aet ship t1 plan.md` execs src/aet/cli/ship.py."""
        rc = self._dispatch(
            ["aet", "ship", "t1", "docs/plans/t1.md"],
            self.skills_root / "src" / "aet" / "cli" / "ship.py",
            ["ship", "t1", "docs/plans/t1.md"],
        )
        self.assertEqual(rc, 0)

    def test_retro_routes_to_package(self):
        """`aet retro` execs src/aet/cli/retro.py."""
        rc = self._dispatch(
            ["aet", "retro"],
            self.skills_root / "src" / "aet" / "cli" / "retro.py",
            ["retro"],
        )
        self.assertEqual(rc, 0)

    def test_configure_backend_routes_to_package(self):
        """`aet configure-backend` execs src/aet/cli/configure-backend.py."""
        rc = self._dispatch(
            ["aet", "configure-backend"],
            self.skills_root / "src" / "aet" / "cli" / "configure-backend.py",
            ["configure-backend"],
        )
        self.assertEqual(rc, 0)


class TestRunMapping(_IsolatedBinDir):
    """run/run-one map user flags to the documented orchestrator argv.

    Since nc-06-run-daemonization the default is detached spawn; the blocking
    exec path is preserved under ``--foreground``.
    """

    def _capture_exec(self, argv):
        """Run main() with execvp captured; return (rc, path, argv)."""
        captured = {}

        def mock_execvp(path, exec_argv):
            captured["path"] = path
            captured["argv"] = exec_argv
            raise SystemExit(0)

        with patch.object(sys, "argv", argv):
            with self._bin_env():
                with patch.object(aet.os, "execvp", mock_execvp):
                    rc = aet.main()
        return rc, captured.get("path"), captured.get("argv")

    def _expected_run_argv(self, *extra):
        return [sys.executable, str(_REPO_ROOT / "src" / "aet" / "cli" / "orchestrator.py"), *extra]

    def test_run_with_all_flags_foreground(self):
        """`aet run --foreground <flags>` execs the orchestrator with mapped argv."""
        argv = [
            "aet",
            "run",
            "--foreground",
            "--max-jobs",
            "2",
            "--isolation",
            "full",
            "--task-timeout",
            "600",
            "--stall-timeout",
            "120",
            "--cli-bin",
            "/bin/cli",
        ]
        rc, path, exec_argv = self._capture_exec(argv)
        self.assertEqual(rc, 0)
        self.assertEqual(Path(path), Path(sys.executable))
        self.assertEqual(
            exec_argv,
            self._expected_run_argv(
                "--queue-file",
                ".agents/work-queue.json",
                "--max-jobs",
                "2",
                "--isolation",
                "full",
                "--task-timeout",
                "600",
                "--stall-timeout",
                "120",
                "--cli-bin",
                "/bin/cli",
            ),
        )

    def test_run_defaults_foreground(self):
        """`aet run --foreground` produces the default orchestrator argv."""
        rc, _, exec_argv = self._capture_exec(["aet", "run", "--foreground"])
        self.assertEqual(rc, 0)
        self.assertEqual(
            exec_argv,
            self._expected_run_argv(
                "--queue-file",
                ".agents/work-queue.json",
                "--max-jobs",
                "4",
                "--isolation",
                "standard",
            ),
        )

    def test_run_one_maps_plan_positional_foreground(self):
        """`aet run-one --foreground <plan>` maps the plan positional to --plan-file."""
        rc, _, exec_argv = self._capture_exec(
            ["aet", "run-one", "docs/plans/FEAT-001.md", "--foreground", "--cli-bin", "/bin/kimi"]
        )
        self.assertEqual(rc, 0)
        self.assertEqual(
            exec_argv,
            self._expected_run_argv(
                "--plan-file",
                "docs/plans/FEAT-001.md",
                "--max-jobs",
                "4",
                "--isolation",
                "standard",
                "--cli-bin",
                "/bin/kimi",
            ),
        )

    def test_run_one_without_plan_exits_2(self):
        """`aet run-one` without a plan file exits 2 without exec."""
        with patch.object(sys, "argv", ["aet", "run-one"]):
            with self._bin_env():
                with patch.object(aet.os, "execvp") as mock_exec:
                    rc = aet.main()
        self.assertEqual(rc, 2)
        mock_exec.assert_not_called()

    def test_run_maps_on_failure_flag_foreground(self):
        """`aet run --foreground --on-failure` forwards the flag to the orchestrator."""
        rc, _, exec_argv = self._capture_exec(
            ["aet", "run", "--foreground", "--on-failure", "halt"]
        )
        self.assertEqual(rc, 0)
        self.assertIn("--on-failure", exec_argv)
        self.assertEqual(exec_argv[exec_argv.index("--on-failure") + 1], "halt")

    def test_run_spawns_detached_by_default(self):
        """`aet run` with no flags spawns the orchestrator detached."""
        captured = {}

        def fake_popen(cmd, **kwargs):
            captured["cmd"] = cmd
            captured["kwargs"] = kwargs
            mock = unittest.mock.MagicMock()
            mock.pid = 12345
            return mock

        with tempfile.TemporaryDirectory() as tmp:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                with patch.object(sys, "argv", ["aet", "run"]):
                    with self._bin_env():
                        with patch.object(aet.subprocess, "Popen", side_effect=fake_popen) as popen_mock:
                            with patch.object(aet, "_generate_run_id", return_value="run-detached-abc"):
                                rc = aet.main()
            finally:
                os.chdir(old_cwd)

            self.assertEqual(rc, 0)
            popen_mock.assert_called_once()
            self.assertEqual(captured["kwargs"]["start_new_session"], True)
            self.assertIn("--run-id", captured["cmd"])
            self.assertIn("run-detached-abc", captured["cmd"])
            self.assertIn("--log-file", captured["cmd"])


class TestAetErrorPaths(_IsolatedBinDir):
    """Unknown subcommands and missing siblings fail with clear errors."""

    def test_unknown_subcommand_exits_2_with_usage(self):
        """An unknown subcommand prints usage listing the spec and exits 2."""
        import io

        stderr = io.StringIO()
        with patch.object(sys, "argv", ["aet", "nope"]):
            with patch.object(sys, "stderr", stderr):
                with self._bin_env():
                    with patch.object(aet.os, "execvp") as mock_exec:
                        rc = aet.main()
        self.assertEqual(rc, 2)
        mock_exec.assert_not_called()
        err = stderr.getvalue()
        self.assertIn("unknown subcommand 'nope'", err)
        self.assertIn("usage: aet", err)
        for name in ("status", "run", "ship"):
            self.assertIn(name, err)

    def test_no_subcommand_exits_2_with_usage(self):
        """Bare `aet` prints usage and exits 2."""
        with patch.object(sys, "argv", ["aet"]):
            with self._bin_env():
                with patch.object(aet.os, "execvp") as mock_exec:
                    rc = aet.main()
        self.assertEqual(rc, 2)
        mock_exec.assert_not_called()

    def test_missing_sibling_exits_1_naming_skill(self):
        """A missing target skill exits 1 with an error naming the skill dir."""
        import io

        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(aet, "_skills_root", lambda: Path(tmp)):
                with patch.object(sys, "argv", ["aet", "ship"]):
                    with patch.object(sys, "stderr", stderr):
                        with self._bin_env():
                            with patch.object(aet.os, "execvp") as mock_exec:
                                with self.assertRaises(SystemExit) as ctx:
                                    aet.main()
        self.assertEqual(ctx.exception.code, 1)
        mock_exec.assert_not_called()
        self.assertIn("aet.cli", stderr.getvalue())


class TestAetIntegration(_IsolatedBinDir):
    """Subprocess integration: the real exec path reaches the target binary."""

    def test_status_via_real_exec(self):
        """`aet status` execs the real status binary against a temp queue."""
        with tempfile.TemporaryDirectory() as tmp:
            queue_file = Path(tmp) / "queue.json"
            history_file = Path(tmp) / "history.jsonl"
            plans_dir = Path(tmp) / "plans"
            plans_dir.mkdir()
            env = {**os.environ, "AET_BIN_DIR": str(self.bin_dir)}
            result = subprocess.run(
                [
                    sys.executable,
                    str(_AET_PY),
                    "status",
                    "--queue-file",
                    str(queue_file),
                    "--history-file",
                    str(history_file),
                    "--plans-dir",
                    str(plans_dir),
                ],
                capture_output=True,
                text=True,
                cwd=tmp,
                env=env,
            )
        self.assertEqual(result.returncode, 0, result.stderr)


class TestPackageEntryPoint(unittest.TestCase):
    """The installed console script resolves to the same dispatcher interface."""

    def _import_aet_cli_from_repo(self):
        """Import aet.cli from the repo under test.

        ``tests/conftest.py`` already puts the worktree ``src`` directory at the
        front of ``sys.path`` and propagates it via ``PYTHONPATH``, so the
        normal import resolves to the code under test without mutating already
        loaded modules.
        """
        import aet.cli

        return aet.cli

    def test_aet_cli_re_exports_dispatcher_main(self):
        """aet.cli:main is the dispatcher main exposed for the entry point."""
        aet_cli = self._import_aet_cli_from_repo()

        self.assertTrue(callable(aet_cli.main))
        self.assertIn("status", aet_cli.SUBCOMMANDS)
        self.assertEqual(aet_cli.SUBCOMMANDS["status"]["target"], ("aet.cli", "status"))

    def test_aet_cli_subprocess_entry_point_runs_dispatcher(self):
        """The editable-install console script loads aet.cli and prints usage."""
        import subprocess

        env = os.environ.copy()
        env["PYTHONPATH"] = str(_REPO_ROOT / "src")
        result = subprocess.run(
            [str(Path(sys.executable).parent / "aet")],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("usage: aet", result.stderr)
        self.assertIn("subcommands:", result.stderr)


if __name__ == "__main__":
    unittest.main()
