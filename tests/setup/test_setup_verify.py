"""Tests for `aet setup verify` (src/aet/cli/setup.py).

All tests isolate the bin dir via ``AET_BIN_DIR`` and a synthetic ``PATH`` —
nothing ever writes to the real ``~/.local/bin``.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.cli._helpers import run_typer, seed_legacy_epic

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


class TestSetupVerifyConfigProvenance(SetupVerifyTestCase):
    """``setup verify`` prints resolved mode/branches with provenance labels."""

    def _init_repo(self, repo: Path) -> None:
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "test@example.com"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.name", "Test User"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "commit", "--allow-empty", "-m", "init"],
            check=True,
        )

    def _run_verify_in_repo(self, repo: Path):
        """Run ``aet setup verify`` against an isolated repo."""
        env = {
            "AET_BIN_DIR": str(self.bin_dir),
            "AET_REPO_ROOT": str(repo),
            "PATH": f"{self.bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        }
        with patch.object(aet_setup, "_is_worktree_copy", lambda _script: False):
            result = run_typer(aet_setup.app, ["verify"], env=env)
        return result.exit_code, result.stdout, result.stderr

    def test_prints_mode_and_branches_with_project_provenance(self):
        repo = Path(self.tmp.name) / "repo"
        repo.mkdir()
        self._init_repo(repo)

        config = {
            "integration_mode": "single-pr",
            "integration_branch": "feat/epic",
            "trunk_branch": "develop",
        }
        config_path = repo / ".agents" / "aet-config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config), encoding="utf-8")

        rc, out, err = self._run_verify_in_repo(repo)
        self.assertEqual(rc, 0, err)
        self.assertIn("integration_mode: single-pr (config (project))", out)
        self.assertIn("integration_branch: feat/epic (config (project))", out)
        self.assertIn("trunk: develop (config (project))", out)

    def test_marks_default_and_fallback_provenance(self):
        repo = Path(self.tmp.name) / "repo"
        repo.mkdir()
        self._init_repo(repo)

        rc, out, err = self._run_verify_in_repo(repo)
        self.assertEqual(rc, 0, err)
        self.assertIn("integration_mode: pr-per-task (default)", out)
        self.assertIn("integration_branch: main (trunk)", out)
        self.assertIn("trunk: main (fallback)", out)

    def test_finds_project_config_when_package_root_differs_from_repo_root(self):
        """When aet is installed in a venv, config is still resolved from cwd repo."""
        repo = Path(self.tmp.name) / "repo"
        repo.mkdir()
        self._init_repo(repo)

        config = {
            "integration_mode": "single-pr",
            "integration_branch": "feat/epic",
            "trunk_branch": "develop",
        }
        config_path = repo / ".agents" / "aet-config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config), encoding="utf-8")

        venv_root = Path(self.tmp.name) / "venv" / "lib" / "site-packages"
        venv_root.mkdir(parents=True)

        env = {
            "AET_BIN_DIR": str(self.bin_dir),
            "PATH": f"{self.bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        }
        # Simulate a venv install: _repo_root() points to site-packages, but the
        # process cwd is the actual repo. Config resolution must use cwd repo.
        with patch.object(aet_setup, "_repo_root", lambda: venv_root):
            with patch.object(aet_setup, "_is_worktree_copy", lambda _script: False):
                result = run_typer(aet_setup.app, ["verify"], env=env, cwd=str(repo))

        rc, out, err = result.exit_code, result.stdout, result.stderr
        self.assertEqual(rc, 0, err)
        self.assertIn("integration_mode: single-pr (config (project))", out)
        self.assertIn("integration_branch: feat/epic (config (project))", out)
        self.assertIn("trunk: develop (config (project))", out)

    def test_verify_reports_epic_branches(self):
        """R-12: verify lists the epic branches of queued tasks, not the envelope epic."""
        from aet.backends.factory import create_backend

        repo = Path(self.tmp.name) / "repo"
        repo.mkdir()
        self._init_repo(repo)

        rc, out, err = self._run_verify_in_repo(repo)
        self.assertEqual(rc, 0, err)
        self.assertNotIn("epic_branch", out)

        (repo / ".agents").mkdir(exist_ok=True)
        (repo / ".agents" / "aet-config.json").write_text(
            '{"integration_mode": "single-pr"}', encoding="utf-8"
        )
        prds = repo / "docs" / "prds"
        prds.mkdir(parents=True)
        (prds / "alpha-prd.md").write_text("# Alpha\n", encoding="utf-8")
        (prds / "beta-prd.md").write_text("# Beta\n", encoding="utf-8")
        seed_legacy_epic(repo, {"branch": "feat/legacy-epic"})
        backend = create_backend(
            queue_file=str(repo / ".agents" / "aet-queue"),
            history_file=str(repo / ".agents" / "work-history.jsonl"),
        )
        backend.save(
            [
                {"id": "a-1", "state": "queued", "spec": {"frontmatter": {"source_prd": "docs/prds/alpha-prd.md"}}},
                {"id": "b-1", "state": "queued", "spec": {"frontmatter": {"source_prd": "docs/prds/beta-prd.md"}}},
            ]
        )
        backend.close()

        rc, out, err = self._run_verify_in_repo(repo)
        self.assertEqual(rc, 0, err)
        self.assertIn("epic_branch: feat/alpha (prd)", out)
        self.assertIn("epic_branch: feat/beta (prd)", out)
        self.assertNotIn("active_epic", out)
        self.assertNotIn("feat/legacy-epic", out)


class TestSetupVerifyVersionCurrency(SetupVerifyTestCase):
    """`aet setup verify` reports whether the installed aet is current."""

    def setUp(self):
        super().setUp()
        from importlib.metadata import version

        from aet import version_check

        self.version_check = version_check
        self.current = version("aet")
        self.data_dir = Path(self.tmp.name) / "data"
        self.cache = self.data_dir / "version-cache.json"
        (self.bin_dir / "aet").symlink_to(Path(sys.executable).parent / "aet")

    def _run_currency(self, *, tty=True, extra_env=None):
        env = {
            "AET_BIN_DIR": str(self.bin_dir),
            "PATH": str(self.bin_dir),
            "AET_DATA_DIR": str(self.data_dir),
            "CI": None,
            "AET_NO_UPDATE_CHECK": None,
            **(extra_env or {}),
        }
        with (
            patch.object(aet_setup, "_is_worktree_copy", lambda _script: False),
            patch.object(self.version_check, "_stdout_is_tty", lambda: tty),
        ):
            result = run_typer(aet_setup.app, ["verify"], env=env)
        return result.exit_code, result.stdout, result.stderr

    def test_reports_up_to_date(self):
        self.version_check.write_version_cache(self.current, path=self.cache)
        rc, out, err = self._run_currency()
        self.assertEqual(rc, 0, err)
        self.assertIn(f"= aet version: v{self.current} (up to date)", out)

    def test_warns_when_update_available(self):
        self.version_check.write_version_cache("999.0.0", path=self.cache)
        rc, out, err = self._run_currency()
        self.assertEqual(rc, 0, err)
        self.assertIn(
            f"⚠ aet version: v{self.current} (update available: v999.0.0; run aet update)",
            err,
        )

    def test_reports_skipped_when_last_lookup_failed(self):
        self.version_check.write_version_cache(None, path=self.cache)
        rc, out, err = self._run_currency()
        self.assertEqual(rc, 0, err)
        self.assertIn(f"= aet version: v{self.current} (version check skipped/offline)", out)

    def test_reports_skipped_when_suppressed(self):
        self.version_check.write_version_cache("999.0.0", path=self.cache)
        for kwargs in ({"tty": False}, {"extra_env": {"CI": "1"}}, {"extra_env": {"AET_NO_UPDATE_CHECK": "1"}}):
            with self.subTest(**kwargs):
                rc, out, err = self._run_currency(**kwargs)
                self.assertEqual(rc, 0, err)
                self.assertIn(f"= aet version: v{self.current} (version check skipped/offline)", out)
                self.assertNotIn("update available", err)
