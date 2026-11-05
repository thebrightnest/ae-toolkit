"""Unit and integration tests for merge train timeouts and bounded validation (alr-02)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from aet.backends.factory import (
    DEFAULT_VALIDATION_TIMEOUT,
    LEGAL_CONFIG_KEYS,
    resolve_validation_timeout,
)


class TestValidationTimeoutConfig(unittest.TestCase):
    def test_validation_timeout_is_legal_config_key(self):
        """validation_timeout is in LEGAL_CONFIG_KEYS and defaults to 600s."""
        self.assertIn("validation_timeout", LEGAL_CONFIG_KEYS)
        self.assertEqual(DEFAULT_VALIDATION_TIMEOUT, 600)

    def test_default_validation_timeout_resolution(self):
        """Without config, resolve_validation_timeout returns default 600s."""
        with tempfile.TemporaryDirectory() as tmpdir:
            timeout = resolve_validation_timeout(repo_root=tmpdir)
            self.assertEqual(timeout, 600)

    def test_configured_validation_timeout_resolution(self):
        """Project config provides custom validation_timeout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_dir = Path(tmpdir) / ".agents"
            agents_dir.mkdir(parents=True)
            config_file = agents_dir / "aet-config.json"
            config_file.write_text(json.dumps({"validation_timeout": 300}))
            timeout = resolve_validation_timeout(repo_root=tmpdir)
            self.assertEqual(timeout, 300)

    def test_env_override_validation_timeout(self):
        """AET_VALIDATION_TIMEOUT env var overrides config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_dir = Path(tmpdir) / ".agents"
            agents_dir.mkdir(parents=True)
            config_file = agents_dir / "aet-config.json"
            config_file.write_text(json.dumps({"validation_timeout": 300}))
            os.environ["AET_VALIDATION_TIMEOUT"] = "150"
            try:
                timeout = resolve_validation_timeout(repo_root=tmpdir)
                self.assertEqual(timeout, 150)
            finally:
                os.environ.pop("AET_VALIDATION_TIMEOUT", None)


class TestRunFlushValidationTimeout(unittest.TestCase):
    def test_run_flush_validation_aborts_on_timeout(self):
        """_run_flush_validation aborts hung commands when timeout expires."""
        import sys
        import time

        from aet.train import _run_flush_validation

        with tempfile.TemporaryDirectory() as tmpdir:
            t0 = time.monotonic()
            proc = _run_flush_validation(
                [sys.executable, "-c", "import time; time.sleep(10)"],
                tmpdir,
                timeout=0.2,
            )
            elapsed = time.monotonic() - t0
            self.assertLess(elapsed, 2.0, "Validation should have timed out within 2s")
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("timed out", proc.stderr.lower())

    def test_process_group_cleanup_no_orphan_processes(self):
        """Process group cleanup terminates child and background descendant processes."""
        import sys
        import time

        from aet.train import _run_flush_validation

        with tempfile.TemporaryDirectory() as tmpdir:
            pid_file = Path(tmpdir) / "bg.pid"
            child_code = (
                "import os, subprocess, sys, time\n"
                "p = subprocess.Popen(['sleep', '60'])\n"
                f"with open(r'{pid_file}', 'w') as f:\n"
                "    f.write(str(p.pid))\n"
                "time.sleep(60)\n"
            )
            proc = _run_flush_validation(
                [sys.executable, "-c", child_code],
                tmpdir,
                timeout=0.3,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertTrue(pid_file.exists(), "Child should have written bg.pid")
            bg_pid = int(pid_file.read_text().strip())

            time.sleep(0.1)

            is_alive = True
            try:
                os.kill(bg_pid, 0)
            except ProcessLookupError:
                is_alive = False
            except PermissionError:
                is_alive = True

            self.assertFalse(is_alive, f"Background process {bg_pid} survived timeout termination!")


def _init_repo(repo_root: str, origin_root: str, branch: str = "main") -> None:
    import subprocess
    subprocess.run(["git", "init", "--bare", "-q", origin_root], check=True)
    subprocess.run(["git", "init", "-q", repo_root], check=True)
    subprocess.run(["git", "-C", repo_root, "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", repo_root, "config", "user.name", "Test User"], check=True)
    Path(repo_root, "README.md").write_text("# Repo\n", encoding="utf-8")
    subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
    subprocess.run(["git", "-C", repo_root, "commit", "-q", "-m", "initial"], check=True)
    subprocess.run(["git", "-C", repo_root, "branch", "-M", branch], check=True)
    subprocess.run(["git", "-C", repo_root, "remote", "add", "origin", origin_root], check=True)
    subprocess.run(["git", "-C", repo_root, "push", "-q", "-u", "origin", branch], check=True)
    subprocess.run(["git", "-C", origin_root, "symbolic-ref", "HEAD", f"refs/heads/{branch}"], check=True)
    subprocess.run(["git", "-C", repo_root, "update-ref", f"refs/remotes/origin/{branch}", "HEAD"], check=True)


class TestMergeTrainFlushTimeouts(unittest.TestCase):
    def test_timed_out_validation_fails_closed_in_flush(self):
        """Timed-out validation aborts and fails closed; culprit task ejected with timeout diagnostics."""
        import subprocess
        import sys

        from aet import train
        from aet.backends import create_backend

        with tempfile.TemporaryDirectory() as origin_dir, tempfile.TemporaryDirectory() as repo_dir:
            _init_repo(repo_dir, origin_dir, "main")
            queue_file = os.path.join(repo_dir, ".agents", "aet-queue")
            os.makedirs(os.path.join(repo_dir, ".agents"), exist_ok=True)
            backend = create_backend(
                config_path=os.path.join(repo_dir, ".agents", "aet-config.json"),
                queue_file=queue_file,
                history_file=os.path.join(repo_dir, ".agents", "work-history.jsonl"),
            )

            Path(repo_dir, "task1.txt").write_text("task1 content", encoding="utf-8")
            subprocess.run(["git", "-C", repo_dir, "add", "."], check=True)
            subprocess.run(["git", "-C", repo_dir, "commit", "-m", "task 1 commit"], check=True)
            c1 = subprocess.check_output(["git", "-C", repo_dir, "rev-parse", "HEAD"], text=True).strip()
            subprocess.run(["git", "-C", repo_dir, "reset", "--hard", "HEAD~1"], check=True)
            initial_main = subprocess.check_output(["git", "-C", repo_dir, "rev-parse", "main"], text=True).strip()

            train.update_train_ref(repo_dir, "main", c1, old_commit="0" * 40)
            queue = [
                {
                    "id": "task-timeout-1",
                    "state": "awaiting_merge",
                    "train": {
                        "branch": "main",
                        "position": 1,
                        "staged_commit": c1,
                        "staged_at": "2026-11-04T12:00:00Z",
                    },
                }
            ]
            backend.save(queue)

            result = train.flush(
                repo_dir,
                "main",
                backend=backend,
                validate_command=[sys.executable, "-c", "import time; time.sleep(10)"],
                validation_timeout=0.3,
            )
            # Culprit ejected, remaining train empty
            self.assertTrue(result.ok)
            self.assertEqual(result.status, "empty")

            # Main branch unmoved (fail closed)
            curr_main = subprocess.check_output(["git", "-C", repo_dir, "rev-parse", "main"], text=True).strip()
            self.assertEqual(curr_main, initial_main)

            # Task remains in awaiting_merge with timeout diagnostics
            saved_queue = backend.load()["queue"]
            t1 = saved_queue[0]
            self.assertEqual(t1["state"], "awaiting_merge")
            self.assertNotIn("train", t1)
            self.assertEqual(t1["conflict_diagnostics"]["reason"], "batch_validation")
            self.assertIn("timed out", t1["conflict_diagnostics"]["stderr_tail"].lower())

    def test_flush_records_batch_failure_verdict_when_halted(self):
        """When flush halts on validation failure/timeout without culprit, batch fail verdict is written."""
        import subprocess
        import sys
        from unittest.mock import patch

        from aet import train
        from aet.backends import create_backend

        with (
            tempfile.TemporaryDirectory() as origin_dir,
            tempfile.TemporaryDirectory() as repo_dir,
            tempfile.TemporaryDirectory() as reports_dir,
        ):
            _init_repo(repo_dir, origin_dir, "main")
            queue_file = os.path.join(repo_dir, ".agents", "aet-queue")
            os.makedirs(os.path.join(repo_dir, ".agents"), exist_ok=True)
            backend = create_backend(
                config_path=os.path.join(repo_dir, ".agents", "aet-config.json"),
                queue_file=queue_file,
                history_file=os.path.join(repo_dir, ".agents", "work-history.jsonl"),
            )

            Path(repo_dir, "task1.txt").write_text("task1 content", encoding="utf-8")
            subprocess.run(["git", "-C", repo_dir, "add", "."], check=True)
            subprocess.run(["git", "-C", repo_dir, "commit", "-m", "task 1 commit"], check=True)
            c1 = subprocess.check_output(["git", "-C", repo_dir, "rev-parse", "HEAD"], text=True).strip()
            subprocess.run(["git", "-C", repo_dir, "reset", "--hard", "HEAD~1"], check=True)

            train.update_train_ref(repo_dir, "main", c1, old_commit="0" * 40)
            queue = [
                {
                    "id": "task-flake-1",
                    "state": "awaiting_merge",
                    "train": {
                        "branch": "main",
                        "position": 1,
                        "staged_commit": c1,
                        "staged_at": "2026-11-04T12:00:00Z",
                    },
                }
            ]
            backend.save(queue)

            with patch.dict(os.environ, {"AET_REPORTS_DIR": reports_dir}):
                # Simulate bisect returning None (flake path), followed by retry timing out
                with patch("aet.train.bisect", return_value=None):
                    result = train.flush(
                        repo_dir,
                        "main",
                        backend=backend,
                        validate_command=[sys.executable, "-c", "import time; time.sleep(10)"],
                        validation_timeout=0.3,
                    )
                    self.assertFalse(result.ok)
                    self.assertEqual(result.status, "halt")
                    self.assertIn("timed out", result.error.lower())

                    # Check that batch failure verdict was recorded
                    from aet import telemetry
                    from aet.evidence import evidence_path
                    slug = telemetry.derive_project_slug(repo_dir)
                    batch_verdict_file = evidence_path("main", "batch", project_slug=slug, reports_root=reports_dir)
                    self.assertTrue(batch_verdict_file.exists())
                    data = json.loads(batch_verdict_file.read_text(encoding="utf-8"))
                    records = data if isinstance(data, list) else [data]
                    self.assertEqual(records[-1]["verdict"], "fail")
                    self.assertIn("timed out", records[-1]["summary"].lower())


class TestSubprocessTimeouts(unittest.TestCase):
    def test_integrate_helpers_handle_timeout(self):
        """Integrate helpers handle subprocess timeout without unhandled exception."""
        import subprocess
        from unittest.mock import patch

        from aet import integrate

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 1)):
            self.assertEqual(integrate.commit_count("main"), 0)
            self.assertEqual(integrate.commit_subjects("main"), [])
            err = integrate.check_release_guard("main")
            self.assertIn("timed out", (err or "").lower())

    def test_ship_run_git_handles_timeout(self):
        """aet.cli.ship._run_git returns returncode 124 when check=False and command times out."""
        import subprocess
        from unittest.mock import patch

        from aet.cli import ship

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 1)):
            res = ship._run_git("status", check=False)
            self.assertEqual(res.returncode, 124)
            self.assertIn("timed out", res.stderr.lower())

    def test_ship_create_pr_handles_timeout(self):
        """aet.cli.ship._create_pr returns (False, msg) upon timeout."""
        import subprocess
        from unittest.mock import patch

        from aet.cli import ship

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("gh", 1)):
            ok, msg = ship._create_pr("main", "title", "body")
            self.assertFalse(ok)
            self.assertIn("timed out", msg.lower())

    def test_ship_find_existing_pr_handles_timeout(self):
        """aet.cli.ship._find_existing_pr returns None upon timeout."""
        import subprocess
        from unittest.mock import patch

        from aet.cli import ship

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("gh", 1)):
            pr = ship._find_existing_pr("feature-branch")
            self.assertIsNone(pr)




