"""Tests for the aet-work multicall dispatcher and installer prune behavior."""

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_DISPATCHER_PY = Path(__file__).parent.parent / "aet-work" / "bin" / "aet-work"
_spec = importlib.util.spec_from_loader(
    "aet_work_dispatcher",
    importlib.machinery.SourceFileLoader("aet_work_dispatcher", str(_DISPATCHER_PY)),
)
dispatcher = importlib.util.module_from_spec(_spec)


class TestAetWorkDispatcher(unittest.TestCase):
    """Behavior-driven tests for aet-work/bin/aet-work dispatch logic."""

    @classmethod
    def setUpClass(cls):
        cls.script_dir = _DISPATCHER_PY.parent
        # Load the module once for the class; tests patch os.execvp before
        # invoking main() so no real exec occurs.
        _spec.loader.exec_module(dispatcher)

    def _expect_exec(self, expected_bin, expected_argv):
        """Return a mock os.execvp that asserts on the invoked binary and argv."""

        def mock_execvp(path, argv):
            self.assertEqual(Path(path), expected_bin)
            self.assertEqual(argv, expected_argv)
            raise SystemExit(0)

        return mock_execvp

    def test_dispatch_status_forwards_argv(self):
        """`aet-work status --queue-file foo.json` forwards argv to the status binary."""
        with patch.object(sys, "argv", ["aet-work", "status", "--queue-file", "foo.json"]):
            with patch.object(
                dispatcher.os,
                "execvp",
                self._expect_exec(
                    self.script_dir / "status",
                    ["status", "--queue-file", "foo.json"],
                ),
            ):
                rc = dispatcher.main()
        self.assertEqual(rc, 0)

    def test_dispatch_add_forwards_argv(self):
        """`aet-work add FEAT-001` forwards argv to the add binary."""
        with patch.object(sys, "argv", ["aet-work", "add", "FEAT-001"]):
            with patch.object(
                dispatcher.os,
                "execvp",
                self._expect_exec(
                    self.script_dir / "add",
                    ["add", "FEAT-001"],
                ),
            ):
                rc = dispatcher.main()
        self.assertEqual(rc, 0)

    def test_run_maps_to_orchestrator_queue_mode(self):
        """`aet-work run` invokes orchestrator in queue-file mode with forwarded flags."""
        with patch.object(
            sys,
            "argv",
            [
                "aet-work",
                "run",
                "--max-jobs",
                "2",
                "--isolation",
                "full",
                "--task-timeout",
                "600",
                "--cli-bin",
                "/bin/cli",
            ],
        ):
            with patch.object(
                dispatcher.os,
                "execvp",
                self._expect_exec(
                    self.script_dir / "orchestrator",
                    [
                        "orchestrator",
                        "--queue-file",
                        ".agents/work-queue.json",
                        "--max-jobs",
                        "2",
                        "--isolation",
                        "full",
                        "--task-timeout",
                        "600",
                        "--cli-bin",
                        "/bin/cli",
                    ],
                ),
            ):
                rc = dispatcher.main()
        self.assertEqual(rc, 0)

    def test_run_defaults_max_jobs_and_isolation(self):
        """`aet-work run` with no flags uses default max-jobs and isolation."""
        with patch.object(sys, "argv", ["aet-work", "run"]):
            with patch.object(
                dispatcher.os,
                "execvp",
                self._expect_exec(
                    self.script_dir / "orchestrator",
                    [
                        "orchestrator",
                        "--queue-file",
                        ".agents/work-queue.json",
                        "--max-jobs",
                        "4",
                        "--isolation",
                        "standard",
                    ],
                ),
            ):
                rc = dispatcher.main()
        self.assertEqual(rc, 0)

    def test_run_one_maps_to_orchestrator_plan_mode(self):
        """`aet-work run-one <plan>` invokes orchestrator in single-plan mode."""
        with patch.object(
            sys, "argv", ["aet-work", "run-one", "docs/plans/FEAT-001.md"]
        ):
            with patch.object(
                dispatcher.os,
                "execvp",
                self._expect_exec(
                    self.script_dir / "orchestrator",
                    [
                        "orchestrator",
                        "--plan-file",
                        "docs/plans/FEAT-001.md",
                        "--max-jobs",
                        "4",
                        "--isolation",
                        "standard",
                    ],
                ),
            ):
                rc = dispatcher.main()
        self.assertEqual(rc, 0)

    def test_run_one_forwards_cli_bin(self):
        """`aet-work run-one` forwards --cli-bin when provided."""
        with patch.object(
            sys,
            "argv",
            [
                "aet-work",
                "run-one",
                "docs/plans/FEAT-001.md",
                "--cli-bin",
                "/bin/kimi",
            ],
        ):
            with patch.object(
                dispatcher.os,
                "execvp",
                self._expect_exec(
                    self.script_dir / "orchestrator",
                    [
                        "orchestrator",
                        "--plan-file",
                        "docs/plans/FEAT-001.md",
                        "--max-jobs",
                        "4",
                        "--isolation",
                        "standard",
                        "--cli-bin",
                        "/bin/kimi",
                    ],
                ),
            ):
                rc = dispatcher.main()
        self.assertEqual(rc, 0)

    def test_unknown_subcommand_exits_2(self):
        """An unknown subcommand prints usage and exits with status 2."""
        with patch.object(sys, "argv", ["aet-work", "nope"]):
            with patch.object(dispatcher.os, "execvp") as mock_exec:
                rc = dispatcher.main()
        self.assertEqual(rc, 2)
        mock_exec.assert_not_called()


class TestInstallAetBinariesPrune(unittest.TestCase):
    """Behavior-driven tests for install-aet-binaries prune policy."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.bin_dir = Path(self.tmpdir.name) / "bin"
        self.bin_dir.mkdir()
        self.skills_dir = Path(self.tmpdir.name) / "skills"
        self.skills_dir.mkdir()

        # Create fake skill tree with only allowed binaries.
        (self.skills_dir / "aet-work" / "bin").mkdir(parents=True)
        (self.skills_dir / "aet-ship" / "bin").mkdir(parents=True)
        (self.skills_dir / "aet-setup" / "bin").mkdir(parents=True)
        (self.skills_dir / "aet-evolve" / "bin").mkdir(parents=True)

        for name in ["aet-work", "aet-state", "orchestrator"]:
            (self.skills_dir / "aet-work" / "bin" / name).write_text(
                "#!/usr/bin/env bash\necho ok\n", encoding="utf-8"
            )
            (self.skills_dir / "aet-work" / "bin" / name).chmod(0o755)

        for name in ["aet-ship"]:
            (self.skills_dir / "aet-ship" / "bin" / name).write_text(
                "#!/usr/bin/env bash\necho ok\n", encoding="utf-8"
            )
            (self.skills_dir / "aet-ship" / "bin" / name).chmod(0o755)

        for name in ["install-aet-binaries", "configure-task-backend"]:
            (self.skills_dir / "aet-setup" / "bin" / name).write_text(
                "#!/usr/bin/env bash\necho ok\n", encoding="utf-8"
            )
            (self.skills_dir / "aet-setup" / "bin" / name).chmod(0o755)

        for name in ["mine-learnings", "aet-retro"]:
            (self.skills_dir / "aet-evolve" / "bin" / name).write_text(
                "#!/usr/bin/env bash\necho ok\n", encoding="utf-8"
            )
            (self.skills_dir / "aet-evolve" / "bin" / name).chmod(0o755)

        self.installer = (
            Path(__file__).parent.parent
            / "aet-setup"
            / "bin"
            / "install-aet-binaries"
        )

    def _run_installer(self):
        env = os.environ.copy()
        env["AET_SKILLS_DIR"] = str(self.skills_dir)
        env["HOME"] = str(self.tmpdir.name)
        result = subprocess.run(
            ["bash", str(self.installer), str(self.bin_dir)],
            capture_output=True,
            text=True,
            env=env,
        )
        return result

    def test_installer_prunes_stale_and_bare_links(self):
        """Installer removes stale AET symlinks and bare-name links, preserves foreign links."""
        skill_work = self.skills_dir / "aet-work" / "bin"
        stale_target = skill_work / "stale-bin"
        stale_target.write_text("#!/bin/bash\necho stale\n", encoding="utf-8")
        stale_target.chmod(0o755)

        # Stale link pointing into a skill directory (target no longer in install set).
        (self.bin_dir / "stale-bin").symlink_to(stale_target)
        # Bare-name link that shadows a system command.
        (self.bin_dir / "sync").symlink_to(skill_work / "aet-state")
        # Foreign symlink that must not be touched.
        (self.bin_dir / "foreign").symlink_to("/usr/bin/true")
        # Real file that must not be touched.
        (self.bin_dir / "real-file").write_text("keep\n", encoding="utf-8")

        result = self._run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)

        self.assertFalse(
            (self.bin_dir / "stale-bin").exists(),
            "stale AET symlink should be pruned",
        )
        self.assertFalse(
            (self.bin_dir / "sync").exists(),
            "bare-name AET symlink should be pruned",
        )
        self.assertTrue(
            (self.bin_dir / "foreign").is_symlink(),
            "foreign symlink must be preserved",
        )
        self.assertTrue(
            (self.bin_dir / "real-file").is_file(),
            "real file must be preserved",
        )

        # Allowed links should exist.
        for name in ["aet-work", "aet-state", "orchestrator", "install-aet-binaries"]:
            with self.subTest(name=name):
                self.assertTrue(
                    (self.bin_dir / name).is_symlink(),
                    f"{name} should be linked",
                )

    def test_installer_links_aet_prefixed_and_allowlist(self):
        """Installer links aet-* binaries and the explicit allowlist names."""
        result = self._run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)

        linked = {p.name for p in self.bin_dir.iterdir() if p.is_symlink()}
        expected = {
            "aet-work",
            "aet-state",
            "orchestrator",
            "aet-ship",
            "install-aet-binaries",
            "configure-task-backend",
            "mine-learnings",
            "aet-retro",
        }
        self.assertTrue(
            expected.issubset(linked),
            f"expected {expected} to be subset of linked {linked}",
        )


if __name__ == "__main__":
    unittest.main()
