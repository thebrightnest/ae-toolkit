"""Tests for `aet install` and on-invocation self-repair (src/aet/cli/main.py).

All tests isolate the bin dir via ``AET_BIN_DIR`` pointed at a temp dir —
nothing ever writes to the real ``~/.local/bin``.
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.cli._helpers import make_history, run_typer, write_json_file

# Module object (not the ``main`` function re-exported by ``aet.cli``).
aet = importlib.import_module("aet.cli.main")

_SCRIPT = Path(aet.__file__).resolve()


class InstallTestCase(unittest.TestCase):
    """Shared temp bin dir + CLI invocation helpers."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.bin_dir = Path(self.tmp.name) / "bin"

    def _run_install(self, *args, allow_worktree=False, env_extra=None):
        """Run `aet install <args>` through the Typer app; returns (rc, stdout, stderr).

        By default ``_is_worktree_copy`` is forced to ``False`` so the suite
        passes when executed from a pipeline worktree.
        """
        env = {"AET_BIN_DIR": str(self.bin_dir), "PATH": "/usr/bin:/bin"}
        if env_extra:
            env.update(env_extra)
        wt_patch = (
            patch.object(aet, "_is_worktree_copy", lambda _script: False)
            if not allow_worktree
            else patch.object(aet, "_is_worktree_copy", aet._is_worktree_copy)
        )
        with wt_patch:
            result = run_typer(
                aet.app,
                ["install", *args],
                env=env,
            )
        return result.exit_code, result.stdout, result.stderr


class TestInstallFreshLink(InstallTestCase):
    """`aet install` links <bin-dir>/aet at the resolved running script."""

    def test_fresh_link_created(self):
        rc, out, err = self._run_install("--bin-dir", str(self.bin_dir))
        self.assertEqual(rc, 0, err)
        link = self.bin_dir / "aet"
        self.assertTrue(link.is_symlink())
        self.assertEqual(Path(os.readlink(link)), _SCRIPT)
        self.assertIn("aet ->", out)

    def test_bin_dir_created_if_missing(self):
        nested = Path(self.tmp.name) / "deep" / "bin"
        rc, _, err = self._run_install("--bin-dir", str(nested))
        self.assertEqual(rc, 0, err)
        self.assertTrue((nested / "aet").is_symlink())

    def test_install_uses_aet_bin_dir_env_by_default(self):
        rc, _, err = self._run_install()
        self.assertEqual(rc, 0, err)
        self.assertTrue((self.bin_dir / "aet").is_symlink())

    def test_unknown_flag_exits_2(self):
        rc, _, err = self._run_install("--bogus")
        self.assertEqual(rc, 2)
        self.assertIn("No such option", err)


class TestInstallStaleAndCollision(InstallTestCase):
    """Stale AET symlinks are repaired; foreign files are never touched."""

    def test_stale_link_repointed_to_invoked_copy(self):
        self.bin_dir.mkdir(parents=True)
        other = Path(self.tmp.name) / "other-checkout" / "aet"
        other.parent.mkdir()
        other.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        (self.bin_dir / "aet").symlink_to(other)

        rc, _, err = self._run_install("--bin-dir", str(self.bin_dir))
        self.assertEqual(rc, 0, err)
        self.assertEqual(Path(os.readlink(self.bin_dir / "aet")), _SCRIPT)

    def test_second_run_is_noop(self):
        self._run_install("--bin-dir", str(self.bin_dir))
        link = self.bin_dir / "aet"
        before = os.readlink(link)

        rc, out, _ = self._run_install("--bin-dir", str(self.bin_dir))
        self.assertEqual(rc, 0)
        self.assertEqual(os.readlink(link), before)
        self.assertIn("already linked", out)

    def test_non_symlink_collision_skipped_with_warning(self):
        self.bin_dir.mkdir(parents=True)
        collision = self.bin_dir / "aet"
        collision.write_text("#!/bin/sh\necho foreign\n", encoding="utf-8")

        rc, _, err = self._run_install("--bin-dir", str(self.bin_dir))
        self.assertEqual(rc, 0)
        self.assertFalse(collision.is_symlink())
        self.assertEqual(collision.read_text(encoding="utf-8"), "#!/bin/sh\necho foreign\n")
        self.assertIn("not a symlink", err)


class TestInstallPathWarning(InstallTestCase):
    """The exact export line is printed only when the bin dir is off PATH."""

    def test_warns_with_export_line_when_bin_dir_not_on_path(self):
        _, out, _ = self._run_install("--bin-dir", str(self.bin_dir))
        self.assertIn("not on your PATH", out)
        self.assertIn(f'export PATH="{self.bin_dir}:$PATH"', out)

    def test_no_warning_when_bin_dir_on_path(self):
        _, out, _ = self._run_install(
            "--bin-dir",
            str(self.bin_dir),
            env_extra={"PATH": f"{self.bin_dir}:/usr/bin:/bin"},
        )
        self.assertNotIn("not on your PATH", out)


class TestSelfRepair(InstallTestCase):
    """Every non-install invocation verifies and repairs the aet symlink."""

    def _dispatch(self, argv, cwd=None):
        """Invoke the main app; returns the result."""
        env = {"AET_BIN_DIR": str(self.bin_dir)}
        with patch.object(aet, "_is_worktree_copy", lambda _script: False):
            return run_typer(aet.app, argv, cwd=cwd, env=env)

    def test_deleted_link_restored_on_invocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            queue_file = write_json_file([])
            history_file = make_history([])
            plans_dir = Path(tmp) / "plans"
            plans_dir.mkdir()
            result = self._dispatch(
                [
                    "status",
                    "--queue-file",
                    queue_file,
                    "--history-file",
                    history_file,
                    "--plans-dir",
                    str(plans_dir),
                ],
                cwd=tmp,
            )
        self.assertEqual(result.exit_code, 0, result.output + result.stderr)
        link = self.bin_dir / "aet"
        self.assertTrue(link.is_symlink())
        self.assertEqual(Path(os.readlink(link)), _SCRIPT)

    def test_stale_link_repointed_on_invocation(self):
        self.bin_dir.mkdir(parents=True)
        other = Path(self.tmp.name) / "elsewhere" / "aet"
        other.parent.mkdir()
        other.write_text("x", encoding="utf-8")
        (self.bin_dir / "aet").symlink_to(other)

        with tempfile.TemporaryDirectory() as tmp:
            queue_file = write_json_file([])
            history_file = make_history([])
            plans_dir = Path(tmp) / "plans"
            plans_dir.mkdir()
            self._dispatch(
                [
                    "status",
                    "--queue-file",
                    queue_file,
                    "--history-file",
                    history_file,
                    "--plans-dir",
                    str(plans_dir),
                ],
                cwd=tmp,
            )
        self.assertEqual(Path(os.readlink(self.bin_dir / "aet")), _SCRIPT)

    def test_non_symlink_never_touched_by_repair(self):
        self.bin_dir.mkdir(parents=True)
        collision = self.bin_dir / "aet"
        collision.write_text("foreign\n", encoding="utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            queue_file = write_json_file([])
            history_file = make_history([])
            plans_dir = Path(tmp) / "plans"
            plans_dir.mkdir()
            result = self._dispatch(
                [
                    "status",
                    "--queue-file",
                    queue_file,
                    "--history-file",
                    history_file,
                    "--plans-dir",
                    str(plans_dir),
                ],
                cwd=tmp,
            )
        self.assertEqual(result.exit_code, 0)
        self.assertFalse(collision.is_symlink())
        self.assertEqual(collision.read_text(encoding="utf-8"), "foreign\n")

    def test_repair_skipped_on_install_itself(self):
        # If self-repair ran during `install`, the link would pre-exist and
        # install's own report would read "already linked" instead of fresh.
        rc, out, _ = self._run_install("--bin-dir", str(self.bin_dir))
        self.assertEqual(rc, 0)
        self.assertIn("✓ aet ->", out)
        self.assertNotIn("already linked", out)


class TestWorktreeCopyGuard(InstallTestCase):
    """An ephemeral worktree copy never becomes the global install target."""

    def _worktree_copy(self):
        return (
            Path(self.tmp.name) / ".worktrees" / "t-1" / "aet-work" / "bin" / "aet"
        )

    def test_self_repair_skips_worktree_copy(self):
        self.bin_dir.mkdir(parents=True)
        main_copy = Path(self.tmp.name) / "main-checkout" / "aet"
        main_copy.parent.mkdir()
        main_copy.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        (self.bin_dir / "aet").symlink_to(main_copy)

        wt = self._worktree_copy()
        with patch.object(aet, "_running_script", lambda: wt):
            aet._ensure_path_link()

        self.assertEqual(Path(os.readlink(self.bin_dir / "aet")), main_copy)

    def test_install_refuses_worktree_copy(self):
        wt = self._worktree_copy()
        with patch.object(aet, "_running_script", lambda: wt):
            rc, _, err = self._run_install(
                "--bin-dir", str(self.bin_dir), allow_worktree=True
            )

        self.assertEqual(rc, 1)
        self.assertIn("worktree", err)
        self.assertFalse((self.bin_dir / "aet").exists())


@unittest.skipIf(
    aet._is_worktree_copy(_SCRIPT),
    "subprocess integration cannot override worktree-copy guard",
)
class TestInstallIntegration(InstallTestCase):
    """Subprocess integration: real install, then self-repair via `aet status`."""

    def test_install_then_status_self_repairs_deleted_link(self):
        env = os.environ.copy()
        env["AET_BIN_DIR"] = str(self.bin_dir)

        result = subprocess.run(
            [sys.executable, "-m", "aet.cli.main", "install", "--bin-dir", str(self.bin_dir)],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        link = self.bin_dir / "aet"
        self.assertTrue(link.is_symlink())

        link.unlink()
        queue_file = Path(self.tmp.name) / "queue.json"
        history_file = Path(self.tmp.name) / "history.jsonl"
        plans_dir = Path(self.tmp.name) / "plans"
        plans_dir.mkdir()
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "aet.cli.main",
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
            env=env,
            cwd=self.tmp.name,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(link.is_symlink())
        self.assertEqual(Path(os.readlink(link)), _SCRIPT)


if __name__ == "__main__":
    unittest.main()
