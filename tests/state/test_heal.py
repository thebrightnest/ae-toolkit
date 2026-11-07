"""Tests for aet state heal self-healing guards (R-4, wvi-03)."""

from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from aet.cli import aet_state
from tests.state._helpers import init_git_repo, seed_git_queue


class TestStateHealEditablePth(unittest.TestCase):
    """Verify aet state heal detects and repairs corrupted _editable_impl_aet.pth."""

    def _setup_repo_with_queue_and_venv(
        self, tmpdir: str, corrupted_pth_target: str | None = None
    ) -> tuple[Path, Path, Path]:
        repo_root = Path(tmpdir)
        init_git_repo(repo_root)
        src_dir = repo_root / "src"
        src_dir.mkdir(parents=True, exist_ok=True)
        queue_path, _ = seed_git_queue(repo_root, [])

        site_packages = repo_root / ".venv" / "lib" / "python3.11" / "site-packages"
        site_packages.mkdir(parents=True, exist_ok=True)
        pth_path = site_packages / "_editable_impl_aet.pth"
        if corrupted_pth_target is not None:
            pth_path.write_text(f"{corrupted_pth_target}\n", encoding="utf-8")
        else:
            pth_path.write_text(f"{src_dir.resolve()}\n", encoding="utf-8")

        return repo_root, queue_path, pth_path

    def test_heal_dry_run_reports_corrupted_pth(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root, queue_path, pth_path = self._setup_repo_with_queue_and_venv(
                tmpdir, corrupted_pth_target="/nonexistent/foreign/worktree/src"
            )

            args = aet_state.argparse.Namespace(
                command="heal",
                queue=str(queue_path),
                apply=False,
                force=False,
            )
            out = io.StringIO()
            with redirect_stdout(out):
                rc = aet_state.cmd_heal(args)

            self.assertEqual(rc, 0)
            output = out.getvalue()
            self.assertIn("_editable_impl_aet.pth", output)
            self.assertIn("Run with --apply to apply these changes.", output)
            # Dry-run must not modify the file
            self.assertEqual(
                pth_path.read_text(encoding="utf-8").strip(),
                "/nonexistent/foreign/worktree/src",
            )

    def test_heal_apply_repairs_corrupted_pth(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root, queue_path, pth_path = self._setup_repo_with_queue_and_venv(
                tmpdir, corrupted_pth_target="/nonexistent/foreign/worktree/src"
            )

            args = aet_state.argparse.Namespace(
                command="heal",
                queue=str(queue_path),
                apply=True,
                force=False,
            )
            out = io.StringIO()
            with redirect_stdout(out):
                rc = aet_state.cmd_heal(args)

            self.assertEqual(rc, 0)
            output = out.getvalue()
            self.assertIn("Healed _editable_impl_aet.pth", output)
            expected_src = str((repo_root / "src").resolve())
            self.assertEqual(pth_path.read_text(encoding="utf-8").strip(), expected_src)

    def test_heal_leaves_valid_pth_alone(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root, queue_path, pth_path = self._setup_repo_with_queue_and_venv(
                tmpdir, corrupted_pth_target=None
            )

            args = aet_state.argparse.Namespace(
                command="heal",
                queue=str(queue_path),
                apply=True,
                force=False,
            )
            out = io.StringIO()
            with redirect_stdout(out):
                rc = aet_state.cmd_heal(args)

            self.assertEqual(rc, 0)
            expected_src = str((repo_root / "src").resolve())
            self.assertEqual(pth_path.read_text(encoding="utf-8").strip(), expected_src)

    def test_heal_repairs_corrupted_pth_alongside_queue_tasks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            init_git_repo(repo_root)
            src_dir = repo_root / "src"
            src_dir.mkdir(parents=True, exist_ok=True)
            plans_dir = repo_root / "docs" / "plans"
            plans_dir.mkdir(parents=True, exist_ok=True)
            (plans_dir / "t1.md").write_text("# Plan\n", encoding="utf-8")

            queue_path, _ = seed_git_queue(
                repo_root,
                [
                    {
                        "id": "t1",
                        "state": "in_progress",
                        "plan_file": str(plans_dir / "t1.md"),
                        "branch": "feat-t1",
                    }
                ],
            )

            site_packages = repo_root / ".venv" / "lib" / "python3.11" / "site-packages"
            site_packages.mkdir(parents=True, exist_ok=True)
            pth_path = site_packages / "_editable_impl_aet.pth"
            pth_path.write_text("/nonexistent/dead/src\n", encoding="utf-8")

            args = aet_state.argparse.Namespace(
                command="heal",
                queue=str(queue_path),
                apply=True,
                force=False,
            )
            out = io.StringIO()
            with redirect_stdout(out):
                rc = aet_state.cmd_heal(args)

            self.assertEqual(rc, 0)
            output = out.getvalue()
            self.assertIn("Healed _editable_impl_aet.pth", output)
            expected_src = str(src_dir.resolve())
            self.assertEqual(pth_path.read_text(encoding="utf-8").strip(), expected_src)

    def test_aet_state_subprocess_execution_resolves_local_src_without_pythonpath(self):
        """Verify aet_state.py run directly as a script imports local src without relying on PYTHONPATH."""
        aet_state_bin = Path(aet_state.__file__).resolve()
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        res = subprocess.run(
            [sys.executable, str(aet_state_bin), "--help"],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("aet_state.py", res.stdout)
