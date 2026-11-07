"""Tests for worktree editable .pth self-healing (R-4, wvi-03)."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from aet import worktree
from tests.worktree.test_worktree import _init_repo_with_origin


class TestHealEditablePth(unittest.TestCase):
    """Unit tests for heal_editable_pth helper in src/aet/worktree.py."""

    def _setup_repo_with_venv(
        self, tmpdir: str
    ) -> tuple[Path, Path]:
        repo_root = Path(tmpdir)
        src_dir = repo_root / "src"
        src_dir.mkdir(parents=True, exist_ok=True)
        site_packages = repo_root / ".venv" / "lib" / "python3.11" / "site-packages"
        site_packages.mkdir(parents=True, exist_ok=True)
        pth_path = site_packages / "_editable_impl_aet.pth"
        return repo_root, pth_path

    def test_heal_rewrites_nonexistent_pth_target(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root, pth_path = self._setup_repo_with_venv(tmpdir)
            pth_path.write_text("/nonexistent/ephemeral/worktree/src\n", encoding="utf-8")

            healed = worktree.heal_editable_pth(repo_root)

            self.assertTrue(healed)
            expected_src = str((repo_root / "src").resolve())
            self.assertEqual(pth_path.read_text(encoding="utf-8").strip(), expected_src)

    def test_heal_rewrites_foreign_worktree_pth_target(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root, pth_path = self._setup_repo_with_venv(tmpdir)
            foreign_src = repo_root / ".worktrees" / "other-task" / "src"
            foreign_src.mkdir(parents=True, exist_ok=True)
            pth_path.write_text(f"{foreign_src}\n", encoding="utf-8")

            healed = worktree.heal_editable_pth(repo_root)

            self.assertTrue(healed)
            expected_src = str((repo_root / "src").resolve())
            self.assertEqual(pth_path.read_text(encoding="utf-8").strip(), expected_src)

    def test_heal_leaves_valid_pth_unchanged(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root, pth_path = self._setup_repo_with_venv(tmpdir)
            expected_src = str((repo_root / "src").resolve())
            pth_path.write_text(f"{expected_src}\n", encoding="utf-8")

            healed = worktree.heal_editable_pth(repo_root)

            self.assertFalse(healed)
            self.assertEqual(pth_path.read_text(encoding="utf-8").strip(), expected_src)

    def test_heal_creates_missing_pth_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root, pth_path = self._setup_repo_with_venv(tmpdir)
            self.assertFalse(pth_path.exists())

            healed = worktree.heal_editable_pth(repo_root)

            self.assertTrue(healed)
            self.assertTrue(pth_path.exists())
            expected_src = str((repo_root / "src").resolve())
            self.assertEqual(pth_path.read_text(encoding="utf-8").strip(), expected_src)

    def test_heal_handles_no_venv_gracefully(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            healed = worktree.heal_editable_pth(repo_root)
            self.assertFalse(healed)

    def test_heal_dry_run_does_not_modify_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root, pth_path = self._setup_repo_with_venv(tmpdir)
            corrupted = "/nonexistent/corrupted/path\n"
            pth_path.write_text(corrupted, encoding="utf-8")

            needed = worktree.heal_editable_pth(repo_root, dry_run=True)

            self.assertTrue(needed)
            self.assertEqual(pth_path.read_text(encoding="utf-8"), corrupted)

    def test_heal_resolves_root_when_called_from_linked_worktree(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root, root_pth = self._setup_repo_with_venv(tmpdir)
            wt_dir = repo_root / ".worktrees" / "task-x"
            wt_dir.mkdir(parents=True, exist_ok=True)
            wt_venv = wt_dir / ".venv"
            wt_venv.symlink_to((repo_root / ".venv").resolve())

            root_pth.write_text("/tmp/aet-train-flush-dead/src\n", encoding="utf-8")

            healed = worktree.heal_editable_pth(wt_dir)

            self.assertTrue(healed)
            expected_src = str((repo_root / "src").resolve())
            self.assertEqual(root_pth.read_text(encoding="utf-8").strip(), expected_src)

    def test_teardown_worktree_heals_corrupted_editable_pth(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root, pth_path = self._setup_repo_with_venv(tmpdir)
            _init_repo_with_origin(str(repo_root))
            gitignore = repo_root / ".gitignore"
            gitignore.write_text(".venv\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo_root), "add", ".gitignore"], check=True)
            subprocess.run(["git", "-C", str(repo_root), "commit", "-m", "ignore venv"], check=True)
            wt_dir = worktree.create_worktree(str(repo_root), "task-01")
            self.assertTrue(Path(wt_dir).is_dir())

            corrupted = "/tmp/aet-train-flush-dead/src\n"
            pth_path.write_text(corrupted, encoding="utf-8")

            res = worktree.teardown_worktree(str(repo_root), "task-01")

            self.assertTrue(res["removed"])
            expected_src = str((repo_root / "src").resolve())
            self.assertEqual(pth_path.read_text(encoding="utf-8").strip(), expected_src)

