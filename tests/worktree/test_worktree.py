"""Tests for aet-work worktree helpers."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from aet import worktree


class TestCopyUntrackedFiles(unittest.TestCase):
    def test_copies_untracked_plan_prd_and_adr_into_worktree(self):
        """Untracked docs referenced by a plan are copied to the worktree."""
        with tempfile.TemporaryDirectory() as repo_root:
            worktree_dir = os.path.join(repo_root, ".worktrees", "x-demo")

            # Initialize a repo so git ls-files works.
            subprocess.run(["git", "init", "-q", repo_root], check=True)
            subprocess.run(
                ["git", "-C", repo_root, "config", "user.email", "test@example.com"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", repo_root, "config", "user.name", "Test User"],
                check=True,
            )

            # Create tracked directories so pathspecs match.
            for subdir in [
                "docs/plans",
                "docs/prds",
                "docs/adr",
                "docs/audits",
                "docs/retros",
                "docs/product-briefs",
            ]:
                Path(repo_root, subdir).mkdir(parents=True, exist_ok=True)

            # Create untracked files.
            untracked_files = [
                "docs/plans/x-demo.md",
                "docs/prds/x-demo-prd.md",
                "docs/adr/099-x-demo.md",
                "docs/audits/x-demo-audit.md",
                "docs/retros/x-demo-retro.md",
                "docs/product-briefs/x-demo-brief.md",
            ]
            for rel_path in untracked_files:
                Path(repo_root, rel_path).write_text("content", encoding="utf-8")

            worktree.copy_untracked_files(repo_root, worktree_dir)

            for rel_path in untracked_files:
                dest = Path(worktree_dir, rel_path)
                self.assertTrue(dest.exists(), f"Expected {rel_path} to be copied")
                self.assertEqual(dest.read_text(encoding="utf-8"), "content")


class TestPrepareWorktreeDependencies(unittest.TestCase):
    def test_creates_relative_symlinks_for_configured_dependencies(self):
        """Configured dependencies are symlinked from repo root into the worktree."""
        with tempfile.TemporaryDirectory() as repo_root:
            worktree_dir = os.path.join(repo_root, ".worktrees", "x-demo")
            Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
            Path(repo_root, "app", "node_modules", "pkg").mkdir(parents=True, exist_ok=True)
            Path(repo_root, "api", "vendor", "lib").mkdir(parents=True, exist_ok=True)

            config = {
                "symlink_dependencies": [
                    {"name": "node_modules", "source": "app/node_modules", "target": "app/node_modules"},
                    {"name": "vendor", "source": "api/vendor", "target": "api/vendor"},
                ]
            }
            Path(repo_root, ".agents", "aet-work.json").write_text(
                json.dumps(config), encoding="utf-8"
            )

            results = worktree.prepare_worktree_dependencies(repo_root, worktree_dir)

            self.assertEqual(len(results), 2)
            self.assertEqual(results[0]["status"], "created")
            self.assertEqual(results[1]["status"], "created")

            node_link = Path(worktree_dir, "app", "node_modules")
            vendor_link = Path(worktree_dir, "api", "vendor")
            self.assertTrue(node_link.is_symlink())
            self.assertTrue(vendor_link.is_symlink())
            self.assertTrue(node_link.resolve().samefile(Path(repo_root, "app", "node_modules")))
            self.assertTrue(vendor_link.resolve().samefile(Path(repo_root, "api", "vendor")))

            # Symlinks should be relative so they survive repo relocation.
            self.assertFalse(os.path.isabs(os.readlink(node_link)))

    def test_reports_missing_source_directories_as_failed(self):
        """Missing source directories are reported, not silently ignored."""
        with tempfile.TemporaryDirectory() as repo_root:
            worktree_dir = os.path.join(repo_root, ".worktrees", "x-demo")
            Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
            config = {
                "symlink_dependencies": [
                    {"name": "node_modules", "source": "app/node_modules", "target": "app/node_modules"},
                ]
            }
            Path(repo_root, ".agents", "aet-work.json").write_text(
                json.dumps(config), encoding="utf-8"
            )

            results = worktree.prepare_worktree_dependencies(repo_root, worktree_dir)

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["status"], "failed")
            self.assertIn("source does not exist", results[0]["message"])

    def test_skips_existing_targets(self):
        """Existing directories or symlinks are left in place."""
        with tempfile.TemporaryDirectory() as repo_root:
            worktree_dir = os.path.join(repo_root, ".worktrees", "x-demo")
            Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
            Path(repo_root, "app", "node_modules").mkdir(parents=True, exist_ok=True)
            Path(worktree_dir, "app", "node_modules").mkdir(parents=True, exist_ok=True)

            config = {
                "symlink_dependencies": [
                    {"name": "node_modules", "source": "app/node_modules", "target": "app/node_modules"},
                ]
            }
            Path(repo_root, ".agents", "aet-work.json").write_text(
                json.dumps(config), encoding="utf-8"
            )

            results = worktree.prepare_worktree_dependencies(repo_root, worktree_dir)

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["status"], "skipped")

    def test_returns_empty_when_config_missing(self):
        """No config means no action."""
        with tempfile.TemporaryDirectory() as repo_root:
            worktree_dir = os.path.join(repo_root, ".worktrees", "x-demo")
            results = worktree.prepare_worktree_dependencies(repo_root, worktree_dir)
            self.assertEqual(results, [])


class TestDependencyWarmupRequired(unittest.TestCase):
    def test_returns_missing_dependencies_when_configured_but_absent(self):
        with tempfile.TemporaryDirectory() as repo_root:
            worktree_dir = os.path.join(repo_root, ".worktrees", "x-demo")
            Path(worktree_dir).mkdir(parents=True, exist_ok=True)
            Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
            config = {
                "symlink_dependencies": [
                    {"name": "node_modules", "source": "app/node_modules", "target": "app/node_modules"},
                    {"name": "vendor", "source": "api/vendor", "target": "api/vendor"},
                ]
            }
            Path(repo_root, ".agents", "aet-work.json").write_text(
                json.dumps(config), encoding="utf-8"
            )

            missing = worktree.dependency_warmup_required(repo_root, worktree_dir)
            self.assertEqual(len(missing), 2)
            self.assertEqual(missing[0]["name"], "node_modules")
            self.assertEqual(missing[0]["target"], "app/node_modules")

    def test_returns_empty_when_dependencies_present(self):
        with tempfile.TemporaryDirectory() as repo_root:
            worktree_dir = os.path.join(repo_root, ".worktrees", "x-demo")
            Path(worktree_dir, "app", "node_modules").mkdir(parents=True, exist_ok=True)
            Path(repo_root, ".agents").mkdir(parents=True, exist_ok=True)
            config = {
                "symlink_dependencies": [
                    {"name": "node_modules", "source": "app/node_modules", "target": "app/node_modules"},
                ]
            }
            Path(repo_root, ".agents", "aet-work.json").write_text(
                json.dumps(config), encoding="utf-8"
            )

            missing = worktree.dependency_warmup_required(repo_root, worktree_dir)
            self.assertEqual(missing, [])

    def test_returns_empty_when_config_missing(self):
        with tempfile.TemporaryDirectory() as repo_root:
            worktree_dir = os.path.join(repo_root, ".worktrees", "x-demo")
            missing = worktree.dependency_warmup_required(repo_root, worktree_dir)
            self.assertEqual(missing, [])


class TestCheckMainHygiene(unittest.TestCase):
    def _init_repo(self, repo_root: str) -> None:
        subprocess.run(["git", "init", "-q", repo_root], check=True)
        subprocess.run(
            ["git", "-C", repo_root, "config", "user.email", "test@example.com"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", repo_root, "config", "user.name", "Test User"],
            check=True,
        )
        Path(repo_root, "README.md").write_text("# test", encoding="utf-8")
        subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
        subprocess.run(["git", "-C", repo_root, "commit", "-q", "-m", "init"], check=True)

    def test_queue_sidecars_do_not_trip_dirty_check(self):
        """The lock and lease sidecars linger by design; hygiene must ignore them."""
        with tempfile.TemporaryDirectory() as repo_root:
            self._init_repo(repo_root)
            agents_dir = Path(repo_root, ".agents")
            agents_dir.mkdir()
            for sidecar in ("work-queue.json.lock", "work-queue.lease"):
                (agents_dir / sidecar).write_text("", encoding="utf-8")

            ok, msg = worktree.check_main_hygiene(repo_root)

            self.assertTrue(ok, f"sidecars should be ignored, got: {msg}")

    def test_other_untracked_files_still_fail_hygiene(self):
        """Control: the ignore list must not widen beyond the queue artifacts."""
        with tempfile.TemporaryDirectory() as repo_root:
            self._init_repo(repo_root)
            agents_dir = Path(repo_root, ".agents")
            agents_dir.mkdir()
            (agents_dir / "notes.txt").write_text("x", encoding="utf-8")

            ok, msg = worktree.check_main_hygiene(repo_root)

            self.assertFalse(ok)
            self.assertEqual(msg, "Working tree is dirty")


if __name__ == "__main__":
    unittest.main()
