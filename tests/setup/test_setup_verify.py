"""Tests for `aet setup verify` (src/aet/cli/setup.py).

All tests isolate the bin dir via ``AET_BIN_DIR`` and a synthetic ``PATH`` —
nothing ever writes to the real ``~/.local/bin``.
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.cli._helpers import run_typer

# Module under test
aet_setup = importlib.import_module("aet.cli.setup")


class SetupVerifyTestCase(unittest.TestCase):
    """Shared temp bin dir + CLI invocation helpers."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.bin_dir = Path(self.tmp.name) / "bin"
        self.bin_dir.mkdir()

    def _run_verify(self, *, path=None, bin_dir=None, allow_worktree=False):
        """Run `aet setup verify` through the Typer app; returns (rc, stdout, stderr)."""
        env = {"AET_BIN_DIR": str(bin_dir if bin_dir is not None else self.bin_dir)}
        if path is not None:
            env["PATH"] = path
        else:
            env["PATH"] = str(self.bin_dir)
        if allow_worktree:
            result = run_typer(aet_setup.app, ["verify"], env=env)
        else:
            with patch.object(aet_setup, "_is_worktree_copy", lambda _script: False):
                result = run_typer(aet_setup.app, ["verify"], env=env)
        return result.exit_code, result.stdout, result.stderr


class TestSetupVerifyOk(SetupVerifyTestCase):
    """A correct install reports OK."""

    def test_reports_ok_when_link_wins_path(self):
        expected = self.bin_dir / "aet"
        expected.symlink_to(Path(sys.executable).parent / "aet")

        rc, out, err = self._run_verify(path=str(self.bin_dir))
        self.assertEqual(rc, 0, err)
        self.assertIn("already linked", out.lower())
        self.assertIn(str(expected.resolve()), out)

    def test_reports_ok_when_no_link_but_console_script_wins_path(self):
        """Even without a symlink, verify reports the PATH-winning copy."""
        rc, out, err = self._run_verify(path=str(Path(sys.executable).parent))
        self.assertEqual(rc, 0, err)
        self.assertIn(str(Path(sys.executable).parent / "aet"), out)


class TestSetupVerifyShadowing(SetupVerifyTestCase):
    """PATH shadowing is reported by name and still exits 0."""

    def test_reports_shadowing_path_by_name(self):
        other_bin = Path(self.tmp.name) / "other" / "bin"
        other_bin.mkdir(parents=True)
        other_aet = other_bin / "aet"
        other_aet.write_text("#!/bin/sh\necho other\n", encoding="utf-8")
        other_aet.chmod(0o755)

        # Our link exists but is later on PATH than the shadowing copy.
        our_link = self.bin_dir / "aet"
        our_link.symlink_to(Path(sys.executable).parent / "aet")

        rc, out, err = self._run_verify(path=f"{other_bin}:{self.bin_dir}")
        self.assertEqual(rc, 0, err)
        combined = out + err
        self.assertIn(str(other_aet), combined)
        self.assertIn("shadow", combined.lower())

    def test_exits_zero_when_shadowed(self):
        other_bin = Path(self.tmp.name) / "other" / "bin"
        other_bin.mkdir(parents=True)
        other_aet = other_bin / "aet"
        other_aet.write_text("#!/bin/sh\necho other\n", encoding="utf-8")
        other_aet.chmod(0o755)

        our_link = self.bin_dir / "aet"
        our_link.symlink_to(Path(sys.executable).parent / "aet")

        rc, _, _ = self._run_verify(path=f"{other_bin}:{self.bin_dir}")
        self.assertEqual(rc, 0)


class TestSetupVerifyDanglingLink(SetupVerifyTestCase):
    """A dangling symlink is reported, not hidden."""

    def test_reports_dangling_link(self):
        link = self.bin_dir / "aet"
        link.symlink_to(Path(self.tmp.name) / "missing" / "aet")

        rc, out, err = self._run_verify(path=str(self.bin_dir))
        self.assertEqual(rc, 0, err)
        self.assertIn("dangling", (out + err).lower())


class TestSetupVerifyReadOnly(SetupVerifyTestCase):
    """Verify never mutates PATH, the link, or the file system."""

    def test_never_mutates_path_or_link(self):
        other_bin = Path(self.tmp.name) / "other" / "bin"
        other_bin.mkdir(parents=True)
        other_aet = other_bin / "aet"
        other_aet.write_text("#!/bin/sh\necho other\n", encoding="utf-8")
        other_aet.chmod(0o755)

        our_link = self.bin_dir / "aet"
        our_link.symlink_to(Path(sys.executable).parent / "aet")
        before_target = os.readlink(our_link)

        rc, out, err = self._run_verify(path=f"{other_bin}:{self.bin_dir}")
        self.assertEqual(rc, 0, err)
        self.assertEqual(os.readlink(our_link), before_target)
        self.assertFalse("PATH" in out and "=" in out and "export" in out)
