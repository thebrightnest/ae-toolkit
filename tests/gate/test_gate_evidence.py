"""Tests for structured gate evidence contracts."""

from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aet import evidence, telemetry
from aet.cli_adapter import CLIAdapter
from aet.workflow import ExecutionPolicy, Routing, Workflow, WorkflowStage

# Load the orchestrator script (no .py extension) as a module.
_ORCHESTRATOR_BIN = Path(__file__).parents[2] / "src" / "aet" / "cli" / "orchestrator.py"
_orchestrator_loader = importlib.machinery.SourceFileLoader(
    "orchestrator", str(_ORCHESTRATOR_BIN)
)
_spec = importlib.util.spec_from_loader("orchestrator", _orchestrator_loader)
orchestrator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(orchestrator)


class TestReportsDir(unittest.TestCase):
    def test_reports_dir_env_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = os.environ.copy()
            env["AET_REPORTS_DIR"] = str(tmp_path)
            # Module-level default is computed at import time, so call the
            # function with the environment variable set via mocking.
            original = os.environ.get("AET_REPORTS_DIR")
            os.environ["AET_REPORTS_DIR"] = str(tmp_path)
            try:
                self.assertEqual(evidence.reports_dir(), tmp_path)
            finally:
                if original is None:
                    del os.environ["AET_REPORTS_DIR"]
                else:
                    os.environ["AET_REPORTS_DIR"] = original


class TestEvidencePath(unittest.TestCase):
    def test_evidence_path_is_project_namespaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            path_a = evidence.evidence_path(
                task_id="frh-10",
                kind="qa",
                project_slug="owner/repo-a",
                reports_root=base,
            )
            path_b = evidence.evidence_path(
                task_id="frh-10",
                kind="qa",
                project_slug="owner/repo-b",
                reports_root=base,
            )
            self.assertNotEqual(path_a, path_b)
            self.assertIn("repo-a", str(path_a))
            self.assertIn("repo-b", str(path_b))


class TestValidateVerdict(unittest.TestCase):
    def test_valid_qa_verdict_passes_validation(self):
        record = {
            "task_id": "frh-10",
            "stage": "qa-complete",
            "skill": "aet-qa",
            "verdict": "pass",
            "summary": "All checks passed",
            "generated_at": "2026-07-09T20:00:00Z",
            "tree_hash": "abc123",
            "test_command": "pytest tests/test_gate_evidence.py",
            "tests_total": 6,
            "tests_passed": 6,
            "tests_failed": 0,
        }
        evidence.validate_verdict(record, "qa")  # should not raise

    def test_missing_required_key_fails_validation(self):
        record = {
            "task_id": "frh-10",
            "stage": "qa-complete",
            "skill": "aet-qa",
            "verdict": "pass",
            "summary": "Missing generated_at",
        }
        with self.assertRaises(evidence.VerdictValidationError):
            evidence.validate_verdict(record, "qa")

    def test_wrong_type_fails_validation(self):
        record = {
            "task_id": "frh-10",
            "stage": "qa-complete",
            "skill": "aet-qa",
            "verdict": "pass",
            "summary": "Bad counts",
            "generated_at": "2026-07-09T20:00:00Z",
            "tree_hash": "abc123",
            "test_command": "pytest",
            "tests_total": "six",
            "tests_passed": 6,
            "tests_failed": 0,
        }
        with self.assertRaises(evidence.VerdictValidationError):
            evidence.validate_verdict(record, "qa")

    def test_invalid_verdict_value_fails_validation(self):
        record = {
            "task_id": "frh-10",
            "stage": "qa-complete",
            "skill": "aet-qa",
            "verdict": "maybe",
            "summary": "Invalid verdict value",
            "generated_at": "2026-07-09T20:00:00Z",
            "tree_hash": "abc123",
            "test_command": "pytest",
            "tests_total": 1,
            "tests_passed": 1,
            "tests_failed": 0,
        }
        with self.assertRaises(evidence.VerdictValueError):
            evidence.validate_verdict(record, "qa")

    def test_unknown_kind_fails_validation(self):
        with self.assertRaises(evidence.VerdictValidationError):
            evidence.validate_verdict({"task_id": "frh-10"}, "unknown-kind")


class TestWriteThenReadVerdict(unittest.TestCase):
    def test_write_then_read_verdict_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            record = {
                "task_id": "frh-10",
                "stage": "qa-complete",
                "skill": "aet-qa",
                "verdict": "pass",
                "summary": "Roundtrip",
                "generated_at": "2026-07-09T20:00:00Z",
                "tree_hash": "t0",
                "test_command": "pytest",
                "tests_total": 1,
                "tests_passed": 1,
                "tests_failed": 0,
            }
            path = evidence.write_verdict(
                task_id="frh-10",
                kind="qa",
                record=record,
                project_slug="owner/repo",
                reports_root=base,
            )
            self.assertTrue(path.exists())
            loaded = evidence.read_verdict(path)
            self.assertEqual(loaded["task_id"], "frh-10")
            self.assertEqual(loaded["verdict"], "pass")

    def test_write_verdict_stamps_tree_hash_when_absent(self):
        # The code stamps provenance; the caller need not supply it. A non-git
        # worktree yields an empty hash, but the field is present regardless.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            record = {
                "task_id": "frh-10",
                "stage": "qa-complete",
                "skill": "aet-qa",
                "verdict": "pass",
                "summary": "No hash supplied",
                "generated_at": "2026-07-09T20:00:00Z",
                "test_command": "pytest",
                "tests_total": 1,
                "tests_passed": 1,
                "tests_failed": 0,
            }
            path = evidence.write_verdict(
                task_id="frh-10",
                kind="qa",
                record=record,
                project_slug="owner/repo",
                reports_root=base,
                worktree_dir=base,  # not a git repo → empty hash, still stamped
            )
            loaded = evidence.read_verdict(path)
            self.assertIn("tree_hash", loaded)
            self.assertEqual(loaded["tree_hash"], "")
            # The caller's record must not be mutated in place.
            self.assertNotIn("tree_hash", record)


class TestCheckingVerdictShapes(unittest.TestCase):
    """Round-trip shapes consumed by the orchestrator's evidence gates."""

    def test_review_verdict_with_findings_roundtrips(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            record = {
                "task_id": "frh-11",
                "stage": "reviewed",
                "skill": "aet-review",
                "verdict": "fail",
                "summary": "Findings present",
                "generated_at": "2026-07-09T20:00:00Z",
                "tree_hash": "t0",
                "findings": [{"file": "x.py", "note": "issue"}],
            }
            path = evidence.write_verdict(
                task_id="frh-11",
                kind="review",
                record=record,
                project_slug="owner/repo",
                reports_root=base,
            )
            loaded = evidence.read_verdict(path)
            self.assertEqual(len(loaded["findings"]), 1)

    def test_sync_docs_verdict_with_divergences_roundtrips(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            record = {
                "task_id": "frh-11",
                "stage": "synced",
                "skill": "aet-sync-docs",
                "verdict": "fail",
                "summary": "Divergences present",
                "generated_at": "2026-07-09T20:00:00Z",
                "tree_hash": "t0",
                "divergences": [{"plan": "t1", "note": "drift"}],
            }
            path = evidence.write_verdict(
                task_id="frh-11",
                kind="sync-docs",
                record=record,
                project_slug="owner/repo",
                reports_root=base,
            )
            loaded = evidence.read_verdict(path)
            self.assertEqual(len(loaded["divergences"]), 1)


class TestResolveVerdictPath(unittest.TestCase):
    """resolve_verdict_path implements the three-step verdict path precedence."""

    def test_single_env_var_wins_over_per_kind_and_default(self):
        env = {
            "AET_EVIDENCE_PATH": "/tmp/single/qa.json",
            "AET_EVIDENCE_PATH_QA": "/tmp/per-kind/qa.json",
        }
        with patch.dict(os.environ, env, clear=True):
            path = evidence.resolve_verdict_path(
                task_id="demo",
                kind="qa",
                project_slug="demo/project",
                reports_root="/tmp/reports",
            )
        self.assertEqual(path, Path("/tmp/single/qa.json"))

    def test_per_kind_env_var_used_when_single_unset(self):
        env = {"AET_EVIDENCE_PATH_SYNC_DOCS": "/tmp/per-kind/sync-docs.json"}
        with patch.dict(os.environ, env, clear=True):
            path = evidence.resolve_verdict_path(
                task_id="demo",
                kind="sync-docs",
                project_slug="demo/project",
                reports_root="/tmp/reports",
            )
        self.assertEqual(path, Path("/tmp/per-kind/sync-docs.json"))

    def test_per_kind_env_var_does_not_leak_across_kinds(self):
        env = {"AET_EVIDENCE_PATH_QA": "/tmp/per-kind/qa.json"}
        with patch.dict(os.environ, env, clear=True):
            path = evidence.resolve_verdict_path(
                task_id="demo",
                kind="cso",
                project_slug="demo/project",
                reports_root="/tmp/reports",
            )
        self.assertEqual(
            path, Path("/tmp/reports/demo/project/demo/cso.json")
        )

    def test_default_falls_back_to_evidence_path(self):
        with patch.dict(os.environ, {}, clear=True):
            resolved = evidence.resolve_verdict_path(
                task_id="demo",
                kind="qa",
                project_slug="demo/project",
                reports_root="/tmp/reports",
            )
            expected = evidence.evidence_path(
                task_id="demo",
                kind="qa",
                project_slug="demo/project",
                reports_root="/tmp/reports",
            )
        self.assertEqual(resolved, expected)

    def test_unknown_kind_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(evidence.VerdictValidationError):
                evidence.resolve_verdict_path(task_id="demo", kind="nope")


class TestGroupSessionEnvVars(unittest.TestCase):
    """run_stage_group publishes AET_EVIDENCE_PATH_<KIND> per evidence stage."""

    def _workflow(self) -> Workflow:
        stages = [
            WorkflowStage(
                name="plan-approved",
                skills=["aet-tdd", "aet-implement"],
                evidence=None,
                gate_key=None,
            ),
            WorkflowStage(
                name="implemented", skills=["aet-qa"], evidence="qa", gate_key=None
            ),
            WorkflowStage(
                name="qa-complete",
                skills=["aet-sync-docs"],
                evidence="sync-docs",
                gate_key=None,
            ),
        ]
        return Workflow(
            version=1,
            name="test",
            done_state="done",
            stages=stages,
            stage_map={s.name: s for s in stages},
            execution_policy=ExecutionPolicy(
                session_groups=[["plan-approved", "implemented", "qa-complete"]]
            ),
            routing=Routing(default={"harness": "test", "model": None}, by_stage={}),
        )

    def test_group_env_contains_per_kind_paths_equal_to_gate_path(self):
        workflow = self._workflow()
        adapter = CLIAdapter(
            name="test",
            bin="echo",
            prompt_flag="-p",
            workdir_flag=None,
            headless_flag=None,
        )
        captured = {}

        class _StubPopen:
            stdout = io.StringIO("")

            def wait(self):
                return 0

        def fake_popen(cmd, env=None, **_kwargs):
            captured["env"] = env
            return _StubPopen()

        env_overlay = {"AET_PROJECT_ID": "demo/project"}
        with patch.dict(os.environ, env_overlay, clear=False):
            os.environ.pop("AET_EVIDENCE_PATH", None)
            with patch.object(
                orchestrator.subprocess, "Popen", side_effect=fake_popen
            ):
                orchestrator.run_stage_group(
                    adapter,
                    "/repo",
                    "/work/plan.md",
                    "/work",
                    workflow.stages,
                    task_id="demo",
                    workflow=workflow,
                )

        env = captured["env"]
        # Writers and the gate share one derivation: the env path must equal
        # what _load_checking_verdict reads for the same (task, kind).
        self.assertEqual(
            env["AET_EVIDENCE_PATH_QA"],
            str(
                evidence.evidence_path(
                    task_id="demo", kind="qa", project_slug="demo/project"
                )
            ),
        )
        self.assertEqual(
            env["AET_EVIDENCE_PATH_SYNC_DOCS"],
            str(
                evidence.evidence_path(
                    task_id="demo", kind="sync-docs", project_slug="demo/project"
                )
            ),
        )
        # Group sessions must not set the single-stage var (multiple kinds).
        self.assertNotIn("AET_EVIDENCE_PATH", env)


class TestBuilderInvocation(unittest.TestCase):
    """`aet gate submit` builder mode is single-sourced, not restated per caller."""

    def test_every_schema_kind_has_builder_flags(self):
        self.assertEqual(set(evidence.BUILDER_FLAGS), set(evidence.SCHEMAS))

    def test_submit_command_names_the_stage_and_builder_flags(self):
        command = evidence.submit_command("qa", "pass")
        self.assertIn("aet gate submit --stage qa --verdict pass", command)
        self.assertIn("--from-pytest", command)
        self.assertNotIn("--evidence", command)

    def test_submit_command_rejects_unknown_kinds(self):
        with self.assertRaises(evidence.VerdictValidationError):
            evidence.submit_command("not-a-kind")


class TestGateMessageIncludesPath(unittest.TestCase):
    """The missing-verdict gate message names the path it read."""

    def test_missing_verdict_message_includes_resolved_path(self):
        with tempfile.TemporaryDirectory() as repo_root:
            with tempfile.TemporaryDirectory() as reports_dir:
                env = {
                    "AET_REPORTS_DIR": reports_dir,
                    "AET_PROJECT_ID": "demo/project",
                }
                with patch.dict(os.environ, env, clear=False):
                    logger = telemetry.RunLogger(repo_root, run_id="r1")
                    buf = io.StringIO()
                    with contextlib.redirect_stdout(buf):
                        result = orchestrator._require_passing_verdict(
                            "demo", "qa", repo_root, "plan.md", "qa-complete", logger
                        )
        self.assertFalse(result)
        expected_path = evidence.evidence_path(
            task_id="demo",
            kind="qa",
            project_slug="demo/project",
            reports_root=reports_dir,
        )
        self.assertIn(str(expected_path), buf.getvalue())


if __name__ == "__main__":
    unittest.main()
