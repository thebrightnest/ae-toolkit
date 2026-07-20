"""Tests for `aet install` and on-invocation self-repair (aet-work/bin/aet).

All tests isolate the bin dir via ``AET_BIN_DIR`` pointed at a temp dir —
nothing ever writes to the real ``~/.local/bin``.
"""

import importlib.machinery
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).parents[2]
_AET_PY = _REPO_ROOT / "aet-work" / "bin" / "aet"
_SCRIPT = _AET_PY.resolve()

_aet_spec = importlib.util.spec_from_loader(
    "aet_dispatcher_install",
    importlib.machinery.SourceFileLoader("aet_dispatcher_install", str(_AET_PY)),
)
aet = importlib.util.module_from_spec(_aet_spec)
_aet_spec.loader.exec_module(aet)


class InstallTestCase(unittest.TestCase):
    """Shared temp bin dir + CLI invocation helpers."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.bin_dir = Path(self.tmp.name) / "bin"

    def _run_install(self, *args, env_extra=None, allow_worktree=False):
        """Run `aet install <args>` in-process; returns (rc, stdout, stderr).

        By default ``_is_worktree_copy`` is forced to ``False`` so the suite
        passes when executed from a pipeline worktree. Tests that specifically
        exercise worktree guarding pass ``allow_worktree=True``.
        """
        stdout, stderr = io.StringIO(), io.StringIO()
        env = {"AET_BIN_DIR": str(self.bin_dir), "PATH": "/usr/bin:/bin"}
        if env_extra:
            env.update(env_extra)
        wt_patch = (
            patch.object(aet, "_is_worktree_copy", lambda _script: False)
            if not allow_worktree
            else patch.object(aet, "_is_worktree_copy", aet._is_worktree_copy)
        )
        with patch.object(sys, "argv", ["aet", "install", *args]):
            with patch.dict(os.environ, env):
                with patch.object(sys, "stdout", stdout):
                    with patch.object(sys, "stderr", stderr):
                        with wt_patch:
                            rc = aet.main()
        return rc, stdout.getvalue(), stderr.getvalue()


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
        self.assertIn("unknown flag", err)


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
            env_extra={"PATH": f"{self.bin_dir}:/usr/bin"},
        )
        self.assertNotIn("not on your PATH", out)


class TestInstallPrune(InstallTestCase):
    """Install unconditionally prunes the seven legacy names, guarded by target."""

    def _seed_skill_bin(self):
        skill_bin = Path(self.tmp.name) / "skills" / "aet-work" / "bin"
        skill_bin.mkdir(parents=True)
        for name in aet.LEGACY_NAMES:
            (skill_bin / name).write_text("#!/bin/sh\n", encoding="utf-8")
        return skill_bin

    def test_prune_removes_seven_names_only_when_skills_dir_links(self):
        self.bin_dir.mkdir(parents=True)
        skill_bin = self._seed_skill_bin()

        # Removed: legacy names symlinked into the skills directory.
        removed = (
            "aet-work",
            "orchestrator",
            "mine-learnings",
            "configure-task-backend",
            "install-aet-binaries",
        )
        for name in removed:
            (self.bin_dir / name).symlink_to(skill_bin / name)
        # Kept: regular file carrying a legacy name.
        (self.bin_dir / "aet-state").write_text("keep\n", encoding="utf-8")
        # Kept: legacy-named symlink pointing outside any skills directory.
        (self.bin_dir / "aet-retro").symlink_to("/usr/bin/true")
        # Kept: non-legacy name even though it points into the skills dir.
        (self.bin_dir / "stale-bin").symlink_to(skill_bin / "aet-work")

        rc, _, err = self._run_install(
            "--bin-dir",
            str(self.bin_dir),
            env_extra={"AET_SKILLS_DIR": str(skill_bin.parent.parent)},
        )
        self.assertEqual(rc, 0, err)

        for name in removed:
            self.assertFalse((self.bin_dir / name).exists(), name)
        self.assertTrue((self.bin_dir / "aet-state").is_file())
        self.assertTrue((self.bin_dir / "aet-retro").is_symlink())
        self.assertTrue((self.bin_dir / "stale-bin").is_symlink())
        self.assertTrue((self.bin_dir / "aet").is_symlink())

    def test_install_prunes_legacy_links_by_default(self):
        """No flag needed: install prunes skills-dir legacy links (R-5 flip)."""
        self.bin_dir.mkdir(parents=True)
        skill_bin = self._seed_skill_bin()
        (self.bin_dir / "aet-work").symlink_to(skill_bin / "aet-work")

        rc, out, err = self._run_install(
            "--bin-dir",
            str(self.bin_dir),
            env_extra={"AET_SKILLS_DIR": str(skill_bin.parent.parent)},
        )
        self.assertEqual(rc, 0, err)
        self.assertFalse((self.bin_dir / "aet-work").exists())
        self.assertIn("pruned legacy AET symlink", out)

    def test_prune_flag_rejected(self):
        """The --prune gate is gone with the flag — no deprecation window."""
        rc, _, err = self._run_install("--bin-dir", str(self.bin_dir), "--prune")
        self.assertEqual(rc, 2)
        self.assertIn("unknown flag", err)


class TestSelfRepair(InstallTestCase):
    """Every non-install invocation verifies and repairs the aet symlink."""

    def _dispatch(self, argv):
        """Invoke main() with exec captured; returns rc."""
        with patch.object(sys, "argv", argv):
            with patch.dict(os.environ, {"AET_BIN_DIR": str(self.bin_dir)}):
                with patch.object(aet.os, "execvp", side_effect=SystemExit(0)):
                    with patch.object(
                        aet, "_is_worktree_copy", lambda _script: False
                    ):
                        return aet.main()

    def test_deleted_link_restored_on_invocation(self):
        rc = self._dispatch(["aet", "status"])
        self.assertEqual(rc, 0)
        link = self.bin_dir / "aet"
        self.assertTrue(link.is_symlink())
        self.assertEqual(Path(os.readlink(link)), _SCRIPT)

    def test_stale_link_repointed_on_invocation(self):
        self.bin_dir.mkdir(parents=True)
        other = Path(self.tmp.name) / "elsewhere" / "aet"
        other.parent.mkdir()
        other.write_text("x", encoding="utf-8")
        (self.bin_dir / "aet").symlink_to(other)

        self._dispatch(["aet", "status"])
        self.assertEqual(Path(os.readlink(self.bin_dir / "aet")), _SCRIPT)

    def test_non_symlink_never_touched_by_repair(self):
        self.bin_dir.mkdir(parents=True)
        collision = self.bin_dir / "aet"
        collision.write_text("foreign\n", encoding="utf-8")

        rc = self._dispatch(["aet", "status"])
        self.assertEqual(rc, 0)
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
            [str(_AET_PY), "install", "--bin-dir", str(self.bin_dir)],
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
            env=env,
            cwd=self.tmp.name,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(link.is_symlink())
        self.assertEqual(Path(os.readlink(link)), _SCRIPT)


if __name__ == "__main__":
    unittest.main()
