"""Tests that `aet setup verify` reports the resolved trunk and provenance.

Each test creates an isolated git repository so the trunk resolver sees the
intended symbolic-ref/config state instead of the AE Toolkit repo's own trunk.
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.cli._helpers import run_typer

# Module under test
aet_setup = importlib.import_module("aet.cli.setup")


class VerifyReportsTrunkTestCase(unittest.TestCase):
    """Shared helpers for isolated repo + verify invocation."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        self.bin_dir = Path(self.tmp.name) / "bin"
        self.bin_dir.mkdir()
        self.link = self.bin_dir / "aet"
        self.link.symlink_to(Path(sys.executable).parent / "aet")

        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(
            ["git", "-C", str(self.repo), "commit", "--allow-empty", "-m", "init"],
            check=True,
        )

    def _run_verify(self, *, env_extra=None):
        """Run `aet setup verify` against the isolated repo; returns (rc, stdout, stderr)."""
        env = {
            "AET_BIN_DIR": str(self.bin_dir),
            "AET_REPO_ROOT": str(self.repo),
            "PATH": f"{self.bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        }
        if env_extra:
            env.update(env_extra)
        result = run_typer(aet_setup.app, ["verify"], env=env)
        return result.exit_code, result.stdout, result.stderr


class TestVerifyReportsFallbackTrunk(VerifyReportsTrunkTestCase):
    """When origin/HEAD is unset and no config exists, the fallback is reported."""

    def test_reports_fallback_main(self):
        rc, out, err = self._run_verify()
        self.assertEqual(rc, 0, err)
        self.assertIn("trunk: main (fallback)", out.lower())


class TestVerifyReportsDetectedTrunk(VerifyReportsTrunkTestCase):
    """When origin/HEAD points at a remote ref, the detected trunk is reported."""

    def test_reports_detected_dev_trunk(self):
        # Simulate a remote whose HEAD points at origin/dev.
        head = subprocess.run(
            ["git", "-C", str(self.repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "-C", str(self.repo), "update-ref", "refs/remotes/origin/dev", head],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self.repo),
                "symbolic-ref",
                "refs/remotes/origin/HEAD",
                "refs/remotes/origin/dev",
            ],
            check=True,
        )

        rc, out, err = self._run_verify()
        self.assertEqual(rc, 0, err)
        self.assertIn("trunk: dev (detected)", out.lower())


class TestVerifyReportsConfigTrunk(VerifyReportsTrunkTestCase):
    """When config sets trunk_branch, that value is reported."""

    def test_reports_config_trunk(self):
        config = Path(self.tmp.name) / "aet-work.json"
        config.write_text('{"trunk_branch": "custom-trunk"}', encoding="utf-8")

        rc, out, err = self._run_verify(env_extra={"AET_WORK_CONFIG": str(config)})
        self.assertEqual(rc, 0, err)
        self.assertIn("trunk: custom-trunk (config)", out.lower())


if __name__ == "__main__":
    unittest.main()
