"""Tests for scripts/check-editable-install.py — worktree detection and skip logic."""

import contextlib
import importlib.util
import io
import pathlib
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

_REPO_ROOT = pathlib.Path(__file__).parents[2]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "check-editable-install.py"

_spec = importlib.util.spec_from_file_location("check_editable_install", _SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["check_editable_install"] = _mod
_spec.loader.exec_module(_mod)


class TestIsLinkedWorktree(unittest.TestCase):
    """Test detection of linked git worktrees vs standard repos."""

    def test_active_linked_worktree_detected(self):
        """In the active worktree, git-dir differs from git-common-dir."""
        self.assertTrue(_mod.is_linked_worktree(_REPO_ROOT))

    def test_root_repository_is_not_linked_worktree(self):
        """In the root git repository, git-dir equals git-common-dir."""
        common_proc = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            cwd=_REPO_ROOT,
        )
        if common_proc.returncode == 0:
            root_dir = (_REPO_ROOT / common_proc.stdout.strip()).resolve().parent
            self.assertFalse(_mod.is_linked_worktree(root_dir))

    def test_fresh_git_repo_is_not_linked_worktree(self):
        """A standard git repo created with git init is not a linked worktree."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = pathlib.Path(tmpdir)
            subprocess.run(["git", "init", "-q"], cwd=tmppath, check=True)
            self.assertFalse(_mod.is_linked_worktree(tmppath))

    def test_linked_worktree_created_with_git_worktree_add(self):
        """A worktree created with git worktree add is identified as a linked worktree."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_repo = pathlib.Path(tmpdir) / "base"
            wt_path = pathlib.Path(tmpdir) / "wt"
            subprocess.run(["git", "init", "-q", str(base_repo)], check=True)
            subprocess.run(
                ["git", "-C", str(base_repo), "commit", "--allow-empty", "-m", "init", "-q"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(base_repo), "worktree", "add", "-q", str(wt_path)],
                check=True,
            )
            self.assertFalse(_mod.is_linked_worktree(base_repo))
            self.assertTrue(_mod.is_linked_worktree(wt_path))

    def test_non_git_directory_returns_false(self):
        """A directory that is not inside any git repo returns False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertFalse(_mod.is_linked_worktree(pathlib.Path(tmpdir)))

    def test_git_rev_parse_error_handling(self):
        """Subprocess failure in git rev-parse returns False cleanly."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=128, stdout="", stderr="fatal: not a git repo"
            )
            self.assertFalse(_mod.is_linked_worktree(pathlib.Path("/fake/path")))


class TestCheckEditableInstallMain(unittest.TestCase):
    """Test main() logic under linked worktree and non-worktree scenarios."""

    def test_main_succeeds_in_linked_worktree_when_aet_importable(self):
        """In a linked worktree, main() returns 0 when aet is importable."""
        stderr_buf = io.StringIO()
        with contextlib.redirect_stderr(stderr_buf):
            rc = _mod.main()
        self.assertEqual(rc, 0)
        self.assertEqual(stderr_buf.getvalue(), "")

    def test_main_fails_in_linked_worktree_when_aet_unimportable(self):
        """In a linked worktree, main() returns 1 if aet cannot be imported."""
        with patch.dict(sys.modules, {"aet": None}):
            stderr_buf = io.StringIO()
            with contextlib.redirect_stderr(stderr_buf):
                with patch("builtins.__import__", side_effect=ImportError("No module named 'aet'")):
                    rc = _mod.main()
            self.assertEqual(rc, 1)
            self.assertIn("aet is not importable", stderr_buf.getvalue())

    def test_main_checks_installed_root_in_non_worktree(self):
        """In a non-worktree repository, installed_root mismatch returns 1."""
        fake_aet = types.ModuleType("aet")
        fake_aet.__file__ = "/some/other/root/src/aet/__init__.py"
        with patch.object(_mod, "is_linked_worktree", return_value=False):
            with patch.dict(sys.modules, {"aet": fake_aet}):
                stderr_buf = io.StringIO()
                with contextlib.redirect_stderr(stderr_buf):
                    rc = _mod.main()
                self.assertEqual(rc, 1)
                self.assertIn("wrong path", stderr_buf.getvalue())

    def test_main_succeeds_in_non_worktree_when_version_matches(self):
        """In a non-worktree repository, matching root and version returns 0."""
        fake_aet = types.ModuleType("aet")
        fake_aet.__file__ = str(_REPO_ROOT / "src" / "aet" / "__init__.py")

        def fake_subprocess_run(cmd, *args, **kwargs):
            if "describe" in cmd:
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="v1.2.3\n", stderr="")
            if "rev-parse" in cmd:
                return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="abc1234\n", stderr="")
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="")

        with patch.object(_mod, "is_linked_worktree", return_value=False):
            with patch.dict(sys.modules, {"aet": fake_aet}):
                with patch("importlib.metadata.version", return_value="1.2.3"):
                    with patch("subprocess.run", side_effect=fake_subprocess_run):
                        stderr_buf = io.StringIO()
                        with contextlib.redirect_stderr(stderr_buf):
                            rc = _mod.main()
                        self.assertEqual(rc, 0)
                        self.assertEqual(stderr_buf.getvalue(), "")


class TestMakefileWorktreeGuard(unittest.TestCase):
    """Test Makefile install-editable target execution in linked worktree."""

    def test_make_install_editable_in_linked_worktree(self):
        """Running make install-editable in active worktree verifies without pip install."""
        proc = subprocess.run(
            ["make", "install-editable"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("✓ Editable install verified (linked worktree)", proc.stdout)
        self.assertNotIn("reinstalling", proc.stdout)

    def test_make_install_editable_guards_on_failure_in_worktree(self):
        """If check-editable-install fails in worktree, make fails without pip install."""
        script = (
            "git_dir=$(git rev-parse --git-dir 2>/dev/null)\n"
            "common_dir=$(git rev-parse --git-common-dir 2>/dev/null)\n"
            'if [ -n "$git_dir" ] && [ -n "$common_dir" ] && '
            '[ "$(cd "$git_dir" 2>/dev/null && pwd)" != "$(cd "$common_dir" 2>/dev/null && pwd)" ]; then\n'
            '    stale="simulated check failure"\n'
            '    echo "Editable install check failed in linked worktree: $stale" >&2\n'
            '    echo "Skipping pip install -e in linked worktree to protect shared venv." >&2\n'
            "    exit 1\n"
            "fi\n"
        )
        proc = subprocess.run(["bash", "-c", script], cwd=_REPO_ROOT, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Skipping pip install -e in linked worktree to protect shared venv", proc.stderr)
