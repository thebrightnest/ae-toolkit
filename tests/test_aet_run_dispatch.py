"""Tests for the `aet run` / `aet run-one` detached dispatch (nc-06-run-daemonization)."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).parents[1]
_AET_PY = _REPO_ROOT / "src" / "aet" / "cli" / "main.py"

_aet_spec = importlib.util.spec_from_loader(
    "aet_run_dispatch",
    importlib.machinery.SourceFileLoader("aet_run_dispatch", str(_AET_PY)),
)
aet = importlib.util.module_from_spec(_aet_spec)
_aet_spec.loader.exec_module(aet)


class _IsolatedBinDir(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.bin_dir = Path(self._tmp.name) / "bin"

    def _bin_env(self):
        return patch.dict(os.environ, {"AET_BIN_DIR": str(self.bin_dir)})


class TestRunIdGeneration(unittest.TestCase):
    def test_run_id_has_expected_prefix_and_length(self):
        run_id = aet._generate_run_id()
        self.assertTrue(run_id.startswith("run-"))
        parts = run_id.split("-")
        self.assertEqual(len(parts), 4)  # run, YYYYMMDD, HHMMSS, suffix
        self.assertEqual(len(parts[3]), 8)


class TestRunPaths(unittest.TestCase):
    def test_run_dir_and_log_under_cwd_agents_runs(self):
        run_id = "run-test"
        self.assertEqual(aet._run_dir(run_id), Path.cwd() / ".agents" / "runs" / run_id)
        self.assertEqual(
            aet._run_log_file(run_id),
            Path.cwd() / ".agents" / "runs" / run_id / "output.log",
        )


class TestParseRunArgs(_IsolatedBinDir):
    def test_parse_run_args_returns_dispatcher_flags(self):
        flags, dispatcher = aet._parse_run_args(["--foreground", "--max-jobs", "2"])
        self.assertIn("--max-jobs", flags)
        self.assertIn("2", flags)
        self.assertTrue(dispatcher["foreground"])
        self.assertIsNone(dispatcher["follow"])

    def test_parse_run_args_extracts_follow(self):
        flags, dispatcher = aet._parse_run_args(["--follow", "run-abc"])
        self.assertEqual(dispatcher["follow"], "run-abc")

    def test_parse_run_args_forwards_orchestrator_flags(self):
        flags, _dispatcher = aet._parse_run_args(
            [
                "--isolation",
                "full",
                "--task-timeout",
                "600",
                "--stall-timeout",
                "120",
                "--on-failure",
                "halt",
                "--cli-bin",
                "/bin/cli",
            ]
        )
        self.assertEqual(
            flags,
            [
                "--max-jobs",
                "4",
                "--isolation",
                "full",
                "--on-failure",
                "halt",
                "--task-timeout",
                "600",
                "--stall-timeout",
                "120",
                "--cli-bin",
                "/bin/cli",
            ],
        )


class TestRunDetachedByDefault(_IsolatedBinDir):
    def test_run_spawns_detached_and_prints_run_id(self):
        captured_proc = {}

        def fake_popen(cmd, **kwargs):
            captured_proc["cmd"] = cmd
            captured_proc["kwargs"] = kwargs
            mock = unittest.mock.MagicMock()
            mock.pid = 12345
            return mock

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            old_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                with patch.object(sys, "argv", ["aet", "run"]):
                    with self._bin_env():
                        with patch.object(aet.subprocess, "Popen", side_effect=fake_popen) as popen_mock:
                            with patch.object(aet, "_generate_run_id", return_value="run-detached-abc"):
                                with patch("builtins.print") as print_mock:
                                    rc = aet.main()
            finally:
                os.chdir(old_cwd)

            self.assertEqual(rc, 0)
            popen_mock.assert_called_once()
            self.assertEqual(captured_proc["kwargs"]["start_new_session"], True)
            self.assertTrue(hasattr(captured_proc["kwargs"]["stdout"], "name"))
            self.assertTrue(
                captured_proc["kwargs"]["stdout"].name.endswith("run-detached-abc/output.log")
            )
            printed = " ".join(str(call.args[0]) for call in print_mock.call_args_list)
            self.assertIn("run-detached-abc", printed)
            run_dir = tmp_path / ".agents" / "runs" / "run-detached-abc"
            self.assertTrue(run_dir.is_dir())
            self.assertEqual((run_dir / "pid").read_text(encoding="utf-8"), "12345")

    def test_run_one_spawns_detached_by_default(self):
        captured_proc = {}

        def fake_popen(cmd, **kwargs):
            captured_proc["cmd"] = cmd
            captured_proc["kwargs"] = kwargs
            mock = unittest.mock.MagicMock()
            mock.pid = 12346
            return mock

        with tempfile.TemporaryDirectory() as tmp:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                with patch.object(sys, "argv", ["aet", "run-one", "docs/plans/x.md"]):
                    with self._bin_env():
                        with patch.object(aet.subprocess, "Popen", side_effect=fake_popen):
                            with patch.object(aet, "_generate_run_id", return_value="run-one-abc"):
                                rc = aet.main()
            finally:
                os.chdir(old_cwd)

            self.assertEqual(rc, 0)
            self.assertEqual(captured_proc["kwargs"]["start_new_session"], True)
            self.assertIn("--plan-file", captured_proc["cmd"])
            self.assertIn("docs/plans/x.md", captured_proc["cmd"])
            self.assertIn("--run-id", captured_proc["cmd"])
            self.assertIn("run-one-abc", captured_proc["cmd"])


class TestRunForeground(_IsolatedBinDir):
    def test_run_foreground_routes_through_exec(self):
        captured = {}

        def mock_execvp(path, exec_argv):
            captured["path"] = path
            captured["argv"] = exec_argv
            raise SystemExit(0)

        with patch.object(sys, "argv", ["aet", "run", "--foreground"]):
            with self._bin_env():
                with patch.object(aet.os, "execvp", mock_execvp):
                    rc = aet.main()

        self.assertEqual(rc, 0)
        self.assertEqual(Path(captured["path"]), Path(sys.executable))
        self.assertEqual(captured["argv"][1], str(_REPO_ROOT / "src" / "aet" / "cli" / "orchestrator.py"))
        self.assertIn("--queue-file", captured["argv"])
        self.assertNotIn("--run-id", captured["argv"])

    def test_run_one_foreground_routes_through_exec(self):
        captured = {}

        def mock_execvp(path, exec_argv):
            captured["path"] = path
            captured["argv"] = exec_argv
            raise SystemExit(0)

        with patch.object(sys, "argv", ["aet", "run-one", "docs/plans/x.md", "--foreground"]):
            with self._bin_env():
                with patch.object(aet.os, "execvp", mock_execvp):
                    rc = aet.main()

        self.assertEqual(rc, 0)
        self.assertIn("--plan-file", captured["argv"])
        self.assertIn("docs/plans/x.md", captured["argv"])
        self.assertNotIn("--run-id", captured["argv"])

    def test_exec_mode_subcommand_still_uses_exec(self):
        """`_exec()` itself is untouched for non-run subcommands."""
        captured = {}

        def mock_execvp(path, exec_argv):
            captured["path"] = path
            captured["argv"] = exec_argv
            raise SystemExit(0)

        with patch.object(sys, "argv", ["aet", "status", "--queue-file", "q.json"]):
            with self._bin_env():
                with patch.object(aet.os, "execvp", mock_execvp):
                    rc = aet.main()

        self.assertEqual(rc, 0)
        self.assertEqual(captured["argv"][1], str(_REPO_ROOT / "src" / "aet" / "cli" / "status.py"))
        self.assertIn("--queue-file", captured["argv"])


class TestFollowRun(_IsolatedBinDir):
    def test_follow_unknown_run_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(sys, "argv", ["aet", "run", "--follow", "run-missing"]):
                with self._bin_env():
                    with patch.dict(os.environ, {"PWD": tmp}):
                        rc = aet.main()
        self.assertEqual(rc, 1)

    def test_follow_prints_existing_log_and_returns_rc(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / ".agents" / "runs" / "run-done"
            run_dir.mkdir(parents=True)
            (run_dir / "output.log").write_text("hello log\n", encoding="utf-8")
            (run_dir / "pid").write_text("12345", encoding="utf-8")
            (run_dir / "returncode").write_text("0", encoding="utf-8")

            old_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                with patch.object(sys, "argv", ["aet", "run", "--follow", "run-done"]):
                    with self._bin_env():
                        with patch("builtins.print") as print_mock:
                            rc = aet.main()
            finally:
                os.chdir(old_cwd)

            self.assertEqual(rc, 0)
            self.assertIn("hello log\n", [call.args[0] for call in print_mock.call_args_list])


class TestIntegrationDetachedSpawn(_IsolatedBinDir):
    def test_run_spawns_real_orchestrator_that_exits_quickly(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            agents_dir = tmp_path / ".agents"
            agents_dir.mkdir(parents=True)
            queue_file = agents_dir / "work-queue.json"
            history_file = agents_dir / "work-history.jsonl"
            queue_file.write_text('{"queue_updated_at": "2026-01-01T00:00:00Z", "tasks": []}', encoding="utf-8")
            history_file.write_text("", encoding="utf-8")

            env = {**os.environ, "AET_BIN_DIR": str(self.bin_dir), "PYTHONPATH": str(_REPO_ROOT / "src")}
            result = subprocess.run(
                [
                    sys.executable,
                    str(_AET_PY),
                    "run",
                ],
                capture_output=True,
                text=True,
                cwd=tmp,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Started run", result.stdout)
            run_id = result.stdout.split("Started run ")[1].split("\n")[0].strip()
            log_file = tmp_path / ".agents" / "runs" / run_id / "output.log"
            self.assertTrue(log_file.is_file(), f"log file not found: {log_file}")
            # Wait briefly for the orchestrator to finish.
            log_text = ""
            for _ in range(50):
                log_text = log_file.read_text(encoding="utf-8")
                if "Orchestrator finished" in log_text or "Queue is empty" in log_text:
                    break
                time.sleep(0.1)
            self.assertTrue(
                "Orchestrator finished" in log_text or "Queue is empty" in log_text,
                f"unexpected log content: {log_text}",
            )


if __name__ == "__main__":
    unittest.main()
