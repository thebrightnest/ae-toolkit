"""Tests for the aet multicall dispatcher (aet-work/bin/aet)."""

import importlib.machinery
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).parent.parent
_AET_PY = _REPO_ROOT / "aet-work" / "bin" / "aet"
_LEGACY_PY = _REPO_ROOT / "aet-work" / "bin" / "aet-work"

_aet_spec = importlib.util.spec_from_loader(
    "aet_dispatcher",
    importlib.machinery.SourceFileLoader("aet_dispatcher", str(_AET_PY)),
)
aet = importlib.util.module_from_spec(_aet_spec)

_legacy_spec = importlib.util.spec_from_loader(
    "aet_work_legacy_dispatcher",
    importlib.machinery.SourceFileLoader("aet_work_legacy_dispatcher", str(_LEGACY_PY)),
)
legacy = importlib.util.module_from_spec(_legacy_spec)


class TestAetSpecTable(unittest.TestCase):
    """The SUBCOMMANDS spec is importable data shared by dispatch and tooling."""

    @classmethod
    def setUpClass(cls):
        _aet_spec.loader.exec_module(aet)

    def test_spec_covers_all_operational_subcommands(self):
        """SUBCOMMANDS lists every operational toolkit command from R-1."""
        expected = {
            "add",
            "review",
            "status",
            "next",
            "sync",
            "report",
            "init-queue",
            "state",
            "run",
            "run-one",
            "ship",
            "retro",
            "mine-learnings",
            "configure-backend",
        }
        self.assertEqual(set(aet.SUBCOMMANDS), expected)

    def test_spec_entries_declare_target_and_mode(self):
        """Every entry has a (skill-dir, bin-name) target and a dispatch mode."""
        for name, spec in aet.SUBCOMMANDS.items():
            with self.subTest(name=name):
                skill_dir, bin_name = spec["target"]
                self.assertIn(spec["mode"], ("exec", "run", "run-one"))
                self.assertTrue(skill_dir)
                self.assertTrue(bin_name)

    def test_spec_targets_exist_in_repo(self):
        """Every spec target resolves to a real binary in the repo layout."""
        for name, spec in aet.SUBCOMMANDS.items():
            skill_dir, bin_name = spec["target"]
            with self.subTest(name=name):
                binary = _REPO_ROOT / skill_dir / "bin" / bin_name
                self.assertTrue(binary.is_file(), f"missing {binary}")


class TestAetExecRouting(unittest.TestCase):
    """Exec-mode subcommands reach their target binary with argv forwarded."""

    @classmethod
    def setUpClass(cls):
        cls.skills_root = _REPO_ROOT

    def _expect_exec(self, expected_bin, expected_argv):
        def mock_execvp(path, argv):
            self.assertEqual(Path(path), expected_bin)
            self.assertEqual(argv, expected_argv)
            raise SystemExit(0)

        return mock_execvp

    def _dispatch(self, argv, expected_bin, expected_argv):
        with patch.object(sys, "argv", argv):
            with patch.object(
                aet.os, "execvp", self._expect_exec(expected_bin, expected_argv)
            ):
                return aet.main()

    def test_status_routes_to_aet_work_status(self):
        """`aet status --queue-file foo.json` execs aet-work/bin/status verbatim."""
        rc = self._dispatch(
            ["aet", "status", "--queue-file", "foo.json"],
            self.skills_root / "aet-work" / "bin" / "status",
            ["status", "--queue-file", "foo.json"],
        )
        self.assertEqual(rc, 0)

    def test_state_routes_to_aet_state_binary(self):
        """`aet state audit` execs aet-work/bin/aet-state with args verbatim."""
        rc = self._dispatch(
            ["aet", "state", "audit"],
            self.skills_root / "aet-work" / "bin" / "aet-state",
            ["aet-state", "audit"],
        )
        self.assertEqual(rc, 0)

    def test_ship_routes_cross_skill(self):
        """`aet ship t1 plan.md` execs aet-ship/bin/ship via the skills root."""
        rc = self._dispatch(
            ["aet", "ship", "t1", "docs/plans/t1.md"],
            self.skills_root / "aet-ship" / "bin" / "ship",
            ["ship", "t1", "docs/plans/t1.md"],
        )
        self.assertEqual(rc, 0)

    def test_retro_routes_to_aet_evolve(self):
        """`aet retro` execs aet-evolve/bin/aet-retro."""
        rc = self._dispatch(
            ["aet", "retro"],
            self.skills_root / "aet-evolve" / "bin" / "aet-retro",
            ["aet-retro"],
        )
        self.assertEqual(rc, 0)

    def test_configure_backend_routes_to_aet_setup(self):
        """`aet configure-backend` execs aet-setup/bin/configure-task-backend."""
        rc = self._dispatch(
            ["aet", "configure-backend"],
            self.skills_root / "aet-setup" / "bin" / "configure-task-backend",
            ["configure-task-backend"],
        )
        self.assertEqual(rc, 0)


class TestRunMappingParity(unittest.TestCase):
    """run/run-one flag mapping is identical to the frh-05 aet-work dispatcher."""

    @classmethod
    def setUpClass(cls):
        _legacy_spec.loader.exec_module(legacy)

    def _capture_exec(self, module, argv):
        """Run a dispatcher's main() with execvp captured; return (rc, path, argv)."""
        captured = {}

        def mock_execvp(path, exec_argv):
            captured["path"] = path
            captured["argv"] = exec_argv
            raise SystemExit(0)

        with patch.object(sys, "argv", argv):
            with patch.object(module.os, "execvp", mock_execvp):
                rc = module.main()
        return rc, captured.get("path"), captured.get("argv")

    def test_run_with_all_flags_matches_legacy(self):
        """`aet run <flags>` execs the same orchestrator argv as `aet-work run`."""
        argv = [
            "aet",
            "run",
            "--max-jobs",
            "2",
            "--isolation",
            "full",
            "--task-timeout",
            "600",
            "--cli-bin",
            "/bin/cli",
        ]
        rc_new, path_new, exec_new = self._capture_exec(aet, argv)
        legacy_argv = ["aet-work", *argv[1:]]
        rc_old, path_old, exec_old = self._capture_exec(legacy, legacy_argv)
        self.assertEqual(rc_new, rc_old)
        self.assertEqual(Path(path_new), Path(path_old))
        self.assertEqual(exec_new, exec_old)

    def test_run_defaults_match_legacy(self):
        """`aet run` with no flags produces the legacy default orchestrator argv."""
        rc_new, _, exec_new = self._capture_exec(aet, ["aet", "run"])
        rc_old, _, exec_old = self._capture_exec(legacy, ["aet-work", "run"])
        self.assertEqual(rc_new, rc_old)
        self.assertEqual(exec_new, exec_old)
        self.assertIn("--queue-file", exec_new)
        self.assertIn(".agents/work-queue.json", exec_new)

    def test_run_one_matches_legacy(self):
        """`aet run-one <plan>` maps the plan positional to --plan-file like legacy."""
        rc_new, _, exec_new = self._capture_exec(
            aet, ["aet", "run-one", "docs/plans/FEAT-001.md", "--cli-bin", "/bin/kimi"]
        )
        rc_old, _, exec_old = self._capture_exec(
            legacy,
            ["aet-work", "run-one", "docs/plans/FEAT-001.md", "--cli-bin", "/bin/kimi"],
        )
        self.assertEqual(rc_new, rc_old)
        self.assertEqual(exec_new, exec_old)
        self.assertIn("--plan-file", exec_new)
        self.assertIn("docs/plans/FEAT-001.md", exec_new)

    def test_run_one_without_plan_exits_2(self):
        """`aet run-one` without a plan file exits 2 without exec."""
        with patch.object(sys, "argv", ["aet", "run-one"]):
            with patch.object(aet.os, "execvp") as mock_exec:
                rc = aet.main()
        self.assertEqual(rc, 2)
        mock_exec.assert_not_called()


class TestAetErrorPaths(unittest.TestCase):
    """Unknown subcommands and missing siblings fail with clear errors."""

    def test_unknown_subcommand_exits_2_with_usage(self):
        """An unknown subcommand prints usage listing the spec and exits 2."""
        import io

        stderr = io.StringIO()
        with patch.object(sys, "argv", ["aet", "nope"]):
            with patch.object(sys, "stderr", stderr):
                with patch.object(aet.os, "execvp") as mock_exec:
                    rc = aet.main()
        self.assertEqual(rc, 2)
        mock_exec.assert_not_called()
        err = stderr.getvalue()
        self.assertIn("unknown subcommand 'nope'", err)
        self.assertIn("usage: aet", err)
        for name in ("status", "run", "ship"):
            self.assertIn(name, err)

    def test_no_subcommand_exits_2_with_usage(self):
        """Bare `aet` prints usage and exits 2."""
        with patch.object(sys, "argv", ["aet"]):
            with patch.object(aet.os, "execvp") as mock_exec:
                rc = aet.main()
        self.assertEqual(rc, 2)
        mock_exec.assert_not_called()

    def test_missing_sibling_exits_1_naming_skill(self):
        """A missing target skill exits 1 with an error naming the skill dir."""
        import io

        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(aet, "_skills_root", lambda: Path(tmp)):
                with patch.object(sys, "argv", ["aet", "ship"]):
                    with patch.object(sys, "stderr", stderr):
                        with patch.object(aet.os, "execvp") as mock_exec:
                            with self.assertRaises(SystemExit) as ctx:
                                aet.main()
        self.assertEqual(ctx.exception.code, 1)
        mock_exec.assert_not_called()
        self.assertIn("aet-ship", stderr.getvalue())


class TestAetIntegration(unittest.TestCase):
    """Subprocess integration: the real exec path reaches the target binary."""

    def test_status_via_real_exec(self):
        """`aet status` execs the real status binary against a temp queue."""
        with tempfile.TemporaryDirectory() as tmp:
            queue_file = Path(tmp) / "queue.json"
            history_file = Path(tmp) / "history.jsonl"
            plans_dir = Path(tmp) / "plans"
            plans_dir.mkdir()
            result = subprocess.run(
                [
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
                cwd=tmp,
            )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
