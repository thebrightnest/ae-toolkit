"""Tests for `aet setup link` (src/aet/cli/setup.py).

All tests isolate the bin dir via ``AET_BIN_DIR`` pointed at a temp dir —
nothing ever writes to the real ``~/.local/bin``.
"""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.cli._helpers import make_history, run_typer, write_json_file

# Module under test
aet_setup = importlib.import_module("aet.cli.setup")
aet_main = importlib.import_module("aet.cli.main")

_CONSOLE_SCRIPT = (Path(sys.executable).parent / "aet").resolve()


class SetupLinkTestCase(unittest.TestCase):
    """Shared temp bin dir + CLI invocation helpers."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.bin_dir = Path(self.tmp.name) / "bin"

    def _run_link(self, *args, allow_worktree=False, env_extra=None):
        """Run `aet setup link <args>` through the Typer app; returns (rc, stdout, stderr).

        By default ``_is_worktree_copy`` is forced to ``False`` so the suite
        passes when executed from a pipeline worktree.
        """
        env = {"AET_BIN_DIR": str(self.bin_dir), "PATH": "/usr/bin:/bin"}
        if env_extra:
            env.update(env_extra)
        if allow_worktree:
            result = run_typer(aet_setup.app, ["link", *args], env=env)
        else:
            with patch.object(aet_setup, "_is_worktree_copy", lambda _script: False):
                result = run_typer(aet_setup.app, ["link", *args], env=env)
        return result.exit_code, result.stdout, result.stderr


class TestSetupLinkFreshLink(SetupLinkTestCase):
    """`aet setup link` links <bin-dir>/aet at the console script."""

    def test_fresh_link_targets_console_script(self):
        rc, out, err = self._run_link("--bin-dir", str(self.bin_dir))
        self.assertEqual(rc, 0, err)
        link = self.bin_dir / "aet"
        self.assertTrue(link.is_symlink())
        self.assertEqual(Path(os.readlink(link)), _CONSOLE_SCRIPT)
        self.assertIn("aet ->", out)

    def test_bin_dir_created_if_missing(self):
        nested = Path(self.tmp.name) / "deep" / "bin"
        rc, _, err = self._run_link("--bin-dir", str(nested))
        self.assertEqual(rc, 0, err)
        self.assertTrue((nested / "aet").is_symlink())

    def test_setup_link_uses_aet_bin_dir_env_by_default(self):
        rc, _, err = self._run_link()
        self.assertEqual(rc, 0, err)
        self.assertTrue((self.bin_dir / "aet").is_symlink())

    def test_unknown_flag_exits_2(self):
        rc, _, err = self._run_link("--bogus")
        self.assertEqual(rc, 2)
        self.assertIn("No such option", err)


class TestSetupLinkStaleAndCollision(SetupLinkTestCase):
    """Stale AET symlinks are repaired; foreign files are never touched."""

    def test_stale_link_repaired(self):
        self.bin_dir.mkdir(parents=True)
        other = Path(self.tmp.name) / "other-checkout" / "aet"
        other.parent.mkdir()
        other.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        (self.bin_dir / "aet").symlink_to(other)

        rc, _, err = self._run_link("--bin-dir", str(self.bin_dir))
        self.assertEqual(rc, 0, err)
        self.assertEqual(Path(os.readlink(self.bin_dir / "aet")), _CONSOLE_SCRIPT)

    def test_second_run_is_noop(self):
        self._run_link("--bin-dir", str(self.bin_dir))
        link = self.bin_dir / "aet"
        before = os.readlink(link)

        rc, out, _ = self._run_link("--bin-dir", str(self.bin_dir))
        self.assertEqual(rc, 0)
        self.assertEqual(os.readlink(link), before)
        self.assertIn("already linked", out)

    def test_non_symlink_collision_skipped(self):
        self.bin_dir.mkdir(parents=True)
        collision = self.bin_dir / "aet"
        collision.write_text("#!/bin/sh\necho foreign\n", encoding="utf-8")

        rc, _, err = self._run_link("--bin-dir", str(self.bin_dir))
        self.assertEqual(rc, 0)
        self.assertFalse(collision.is_symlink())
        self.assertEqual(
            collision.read_text(encoding="utf-8"),
            "#!/bin/sh\necho foreign\n",
        )
        self.assertIn("not a symlink", err)


class TestSetupLinkRequiresConsoleScript(SetupLinkTestCase):
    """Without a console script the command refuses instead of guessing."""

    def _bin_without_console_script(self) -> Path:
        """A dir holding an interpreter but no ``aet`` console script."""
        fake = Path(self.tmp.name) / "no-console" / "bin"
        fake.mkdir(parents=True)
        return fake

    def test_refuses_when_console_script_missing(self):
        """A module file is not an entry point, so no link is better than one.

        The earlier fallback linked ``Path(__file__)`` — ``setup.py``, mode 644
        with no shebang — and reported success. The link could not execute:
        exactly the failure this command exists to remove.
        """
        fake_bin = self._bin_without_console_script()
        with patch.object(aet_setup.sys, "executable", str(fake_bin / "python")):
            self.assertIsNone(aet_setup._link_target())
            rc, _, err = self._run_link("--bin-dir", str(self.bin_dir))

        self.assertEqual(rc, 1)
        self.assertIn("console script", err)
        self.assertFalse((self.bin_dir / "aet").exists())

    def test_never_links_a_non_executable_module_file(self):
        """Whatever gets linked must be runnable, not merely present."""
        rc, _, err = self._run_link("--bin-dir", str(self.bin_dir))
        self.assertEqual(rc, 0, err)
        target = Path(os.readlink(self.bin_dir / "aet"))
        self.assertNotEqual(target.suffix, ".py", f"linked a module file: {target}")
        self.assertTrue(os.access(target, os.X_OK), f"link target not executable: {target}")


class TestSetupLinkIdempotence(SetupLinkTestCase):
    """A correct link is reported as correct, not repaired every run."""

    def test_second_run_is_noop_under_symlinked_path(self):
        """``/tmp`` is a symlink on macOS; the target must still compare equal.

        ``_link_target_resolves_to`` resolves the readlink, so an unresolved
        script made an already-correct link look stale — relinking on every
        invocation and misreporting a repair that never happened.
        """
        venv_bin = Path(self.tmp.name) / "venvbin"
        venv_bin.mkdir()
        console = venv_bin / "aet"
        console.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        console.chmod(0o755)

        # Reach the same dir through a symlinked parent, as /tmp -> /private/tmp does.
        aliased = Path(self.tmp.name) / "alias"
        aliased.symlink_to(venv_bin)

        with patch.object(aet_setup.sys, "executable", str(aliased / "python")):
            rc, out, err = self._run_link("--bin-dir", str(self.bin_dir))
            self.assertEqual(rc, 0, err)
            self.assertIn("aet ->", out)

            rc, out, err = self._run_link("--bin-dir", str(self.bin_dir))

        self.assertEqual(rc, 0, err)
        self.assertIn("already linked", out)
        self.assertNotIn("updated stale symlink", out)


class TestSetupLinkPathWarning(SetupLinkTestCase):
    """The exact export line is printed only when the bin dir is off PATH."""

    def test_path_warning_prints_export_line(self):
        _, out, _ = self._run_link("--bin-dir", str(self.bin_dir))
        self.assertIn("not on your PATH", out)
        self.assertIn(f'export PATH="{self.bin_dir}:$PATH"', out)

    def test_no_warning_when_bin_dir_on_path(self):
        _, out, _ = self._run_link(
            "--bin-dir",
            str(self.bin_dir),
            env_extra={"PATH": f"{self.bin_dir}:/usr/bin:/bin"},
        )
        self.assertNotIn("not on your PATH", out)


class TestSetupLinkWorktreeCopyGuard(SetupLinkTestCase):
    """An ephemeral worktree copy never becomes the global install target."""

    def _worktree_copy(self):
        return (
            Path(self.tmp.name) / ".worktrees" / "t-1" / "aet-work" / "bin" / "aet"
        )

    def test_refuses_worktree_copy(self):
        wt = self._worktree_copy()
        with patch.object(aet_setup, "_link_target", lambda: wt):
            rc, _, err = self._run_link(
                "--bin-dir", str(self.bin_dir), allow_worktree=True
            )

        self.assertEqual(rc, 1)
        self.assertIn("worktree", err)
        self.assertFalse((self.bin_dir / "aet").exists())


class TestSetupLinkSubcommandDoesNotTouchLink(SetupLinkTestCase):
    """Ordinary subcommands do not mutate the AET-managed symlink."""

    def _dispatch(self, argv, cwd=None):
        """Invoke the main app; returns the result."""
        env = {"AET_BIN_DIR": str(self.bin_dir), "PATH": "/usr/bin:/bin"}
        # The retired self-repair bailed out early whenever the running copy
        # lived under ``.worktrees`` — which is exactly where the pipeline runs
        # this suite, so leaving the guard in place lets the test pass against
        # the very code it exists to reject. Neutralise it so the assertion is
        # about self-repair being gone. Post-change nothing consults this name
        # and the patch is inert.
        with patch.object(
            aet_main, "_is_worktree_copy", lambda _script: False, create=True
        ):
            return run_typer(aet_main.app, argv, cwd=cwd, env=env)

    def test_subcommand_does_not_touch_link(self):
        self.bin_dir.mkdir(parents=True)
        other = Path(self.tmp.name) / "other-aet"
        other.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        link = self.bin_dir / "aet"
        link.symlink_to(other)

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
        self.assertTrue(link.is_symlink())
        self.assertEqual(Path(os.readlink(link)), other)


class TestSetupLinkIntegration(SetupLinkTestCase):
    """Subprocess integration: a real subcommand run against a seeded link."""

    def _staged_package_root(self) -> Path:
        """Copy the ``aet`` package somewhere outside ``.worktrees``.

        The retired self-repair skipped any copy living under ``.worktrees``.
        Running this suite from a pipeline worktree therefore masks a
        regression: the mechanism would be reinstated and the link still left
        alone, because the guard fired first. Staging the package under the
        temp dir removes that escape hatch, so this test fails if on-invocation
        link mutation ever comes back — without patching first-party code.
        """
        pkg = Path(aet_main.__file__).resolve().parents[1]
        root = Path(self.tmp.name) / "pkgroot"
        shutil.copytree(
            pkg, root / "aet", ignore=shutil.ignore_patterns("__pycache__")
        )
        self.assertNotIn(".worktrees", (root / "aet").parts)
        return root

    def test_status_through_seeded_link_does_not_repair_it(self):
        self.bin_dir.mkdir(parents=True)
        other = Path(self.tmp.name) / "other-aet"
        other.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        link = self.bin_dir / "aet"
        link.symlink_to(other)

        root = self._staged_package_root()
        env = os.environ.copy()
        env["AET_BIN_DIR"] = str(self.bin_dir)
        env["PYTHONPATH"] = str(root)

        run_dir = Path(self.tmp.name) / "run"
        run_dir.mkdir()
        plans_dir = run_dir / "plans"
        plans_dir.mkdir()
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "aet.cli.main",
                "status",
                "--queue-file",
                str(run_dir / "queue.json"),
                "--history-file",
                str(run_dir / "history.jsonl"),
                "--plans-dir",
                str(plans_dir),
            ],
            capture_output=True,
            text=True,
            env=env,
            cwd=run_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(link.is_symlink())
        self.assertEqual(Path(os.readlink(link)), other)


if __name__ == "__main__":
    unittest.main()
