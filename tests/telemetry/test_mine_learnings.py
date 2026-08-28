"""Tests for mine-learnings archive walking against the telemetry writer layout."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).parents[2]
_MINE_LEARNINGS_PY = _REPO_ROOT / "src" / "aet" / "cli" / "mine_learnings.py"

_spec = importlib.util.spec_from_loader(
    "mine_learnings_walk",
    importlib.machinery.SourceFileLoader("mine_learnings_walk", str(_MINE_LEARNINGS_PY)),
)
mine_learnings = importlib.util.module_from_spec(_spec)
sys.modules["mine_learnings_walk"] = mine_learnings
_spec.loader.exec_module(mine_learnings)


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _write_run(archive: Path, slug: str, date: str, run_id: str, records: list[dict]) -> Path:
    """Write a task JSONL log in the writer layout: {archive}/{slug}/{date}/{run-id}/."""
    run_dir = archive / slug / date / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "task-1.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
    )
    return run_dir


class TestMineArchiveWriterLayout(unittest.TestCase):
    """mine_archive walks {project-dir}/{worktree-label}/{date}/{run-id}/*.jsonl."""

    def test_scans_runs_and_files_in_writer_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp)
            _write_run(archive, "myrepo/main", _today(), "run-1", [{"type": "stage", "exit_code": 0}])
            _write_run(archive, "myrepo/main", _today(), "run-2", [{"type": "stage", "exit_code": 0}])
            patterns = mine_learnings.mine_archive(archive)
        self.assertEqual(patterns["runs_scanned"], 2)
        self.assertEqual(patterns["files_scanned"], 2)

    def test_non_date_directories_are_skipped_not_treated_as_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp)
            _write_run(archive, "myrepo/main", _today(), "run-1", [{"type": "stage", "exit_code": 0}])
            stray = archive / "myrepo" / "main" / "not-a-date" / "run-x"
            stray.mkdir(parents=True)
            (stray / "task-1.jsonl").write_text(
                json.dumps({"type": "stage", "exit_code": 1}) + "\n", encoding="utf-8"
            )
            patterns = mine_learnings.mine_archive(archive)
        self.assertEqual(patterns["runs_scanned"], 1)
        self.assertEqual(patterns["files_scanned"], 1)
        self.assertEqual(patterns["stage_failures"], 0)

    def test_record_counts_come_from_writer_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp)
            _write_run(
                archive,
                "myrepo/main",
                _today(),
                "run-1",
                [
                    {"type": "learning_candidate", "description": "format-fix loop in aet-implement"},
                    {"type": "environment_issue", "dependency": "node_modules"},
                    {"type": "stage", "stage": "qa", "exit_code": 1},
                ],
            )
            patterns = mine_learnings.mine_archive(archive)
        self.assertEqual(patterns["learning_candidates"], 1)
        self.assertIn(
            "format-fix loop in aet-implement",
            patterns["examples"]["learning_candidates"],
        )
        self.assertEqual(patterns["dependency_issues"], 1)
        self.assertEqual(patterns["stage_failures"], 1)

    def test_multiple_projects_each_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp)
            _write_run(archive, "myrepo/main", _today(), "run-1", [{"type": "stage", "exit_code": 0}])
            _write_run(archive, "other/feature-x", _today(), "run-9", [{"type": "stage", "exit_code": 0}])
            patterns = mine_learnings.mine_archive(archive)
        self.assertEqual(patterns["runs_scanned"], 2)
        self.assertEqual(patterns["files_scanned"], 2)


class TestStructuralScopeCounting(unittest.TestCase):
    """test_run records are counted by scope, not narrative keyword scans."""

    def test_full_suite_and_impact_runs_counted_structurally(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp)
            records = [
                {"type": "test_run", "task_id": "t1", "scope": "full-suite", "source": "wire"},
                {"type": "test_run", "task_id": "t1", "scope": "full-suite", "source": "wire"},
                {"type": "test_run", "task_id": "t2", "scope": "impact", "source": "wire"},
                {"type": "test_run", "task_id": "t3", "scope": "unknown", "source": "wire"},
            ]
            _write_run(archive, "myrepo/main", _today(), "run-1", records)
            patterns = mine_learnings.mine_archive(archive)
        self.assertEqual(patterns["full_suite_runs"], 2)
        self.assertEqual(patterns["impact_runs"], 1)
        # Unknown scope is left uncounted in both categories.
        self.assertEqual(patterns["repeated_test_invocations"], 1)

    def test_repeated_invocations_tallied_per_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp)
            records = [
                # t1 ran full suite three times → 2 redundant.
                {"type": "test_run", "task_id": "t1", "scope": "full-suite", "source": "wire"},
                {"type": "test_run", "task_id": "t1", "scope": "full-suite", "source": "wire"},
                {"type": "test_run", "task_id": "t1", "scope": "full-suite", "source": "wire"},
                # t2 ran full suite once → 0 redundant.
                {"type": "test_run", "task_id": "t2", "scope": "full-suite", "source": "wire"},
                # t3 ran impact only → ignored for repetition tally.
                {"type": "test_run", "task_id": "t3", "scope": "impact", "source": "wire"},
                {"type": "test_run", "task_id": "t3", "scope": "impact", "source": "wire"},
            ]
            _write_run(archive, "myrepo/main", _today(), "run-1", records)
            patterns = mine_learnings.mine_archive(archive)
        self.assertEqual(patterns["full_suite_runs"], 4)
        self.assertEqual(patterns["repeated_test_invocations"], 2)

    def test_mine_learnings_scope_counts_observed_only(self):
        """Scope counts are about runs AET saw, so only observed records count."""
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp)
            records = [
                {"type": "test_run", "task_id": "t1", "scope": "full-suite", "source": "wire"},
                # Claimed by a QA verdict — AET never saw this invocation.
                {"type": "test_run", "task_id": "t1", "scope": "full-suite", "source": "verdict"},
                {"type": "test_run", "task_id": "t2", "scope": "impact", "source": "verdict"},
                # Pre-ADR-051: provenance unknown, not inferred.
                {"type": "test_run", "task_id": "t2", "scope": "impact"},
            ]
            _write_run(archive, "myrepo/main", _today(), "run-1", records)
            patterns = mine_learnings.mine_archive(archive)
        self.assertEqual(patterns["full_suite_runs"], 1)
        self.assertEqual(patterns["impact_runs"], 0)
        # The claimed full-suite record must not read as a redundant repeat.
        self.assertEqual(patterns["repeated_test_invocations"], 0)

    def test_report_labels_scope_counts_as_observed(self):
        """The report states the provenance the figures are computed over."""
        report = mine_learnings.format_report(
            mine_learnings.mine_archive(Path(tempfile.mkdtemp()))
        )
        self.assertIn("Full-suite runs (observed)", report)
        self.assertIn("Impact-scoped runs (observed)", report)


class TestStageAnomalyDetection(unittest.TestCase):
    """Slow and token-burn stages are flagged from stage record fields."""

    def test_slow_stage_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp)
            records = [
                {"type": "stage", "stage": "qa", "duration_seconds": 1800, "token_count": 0},
                {"type": "stage", "stage": "qa", "duration_seconds": 1801, "token_count": 0},
            ]
            _write_run(archive, "myrepo/main", _today(), "run-1", records)
            patterns = mine_learnings.mine_archive(archive)
        self.assertEqual(patterns["slow_stage"], 1)

    def test_token_burn_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp)
            records = [
                {"type": "stage", "stage": "implement", "duration_seconds": 0, "token_count": 5_000_000},
                {"type": "stage", "stage": "implement", "duration_seconds": 0, "token_count": 5_000_001},
            ]
            _write_run(archive, "myrepo/main", _today(), "run-1", records)
            patterns = mine_learnings.mine_archive(archive)
        self.assertEqual(patterns["token_burn"], 1)

    def test_missing_stage_fields_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp)
            records = [
                {"type": "stage", "stage": "qa"},
                {"type": "stage", "stage": "qa", "duration_seconds": None, "token_count": None},
            ]
            _write_run(archive, "myrepo/main", _today(), "run-1", records)
            patterns = mine_learnings.mine_archive(archive)
        self.assertEqual(patterns["slow_stage"], 0)
        self.assertEqual(patterns["token_burn"], 0)


class TestRepeatedLoops(unittest.TestCase):
    """A requeue loop is counted from stage records, not from prose."""

    def test_repeated_failures_of_one_stage_count_as_a_loop(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp)
            _write_run(
                archive,
                "myrepo/main",
                _today(),
                "run-1",
                [
                    {"type": "stage", "task_id": "t1", "stage": "qa", "exit_code": 1},
                    {"type": "stage", "task_id": "t1", "stage": "qa", "exit_code": 1},
                    {"type": "stage", "task_id": "t1", "stage": "qa", "exit_code": 1},
                ],
            )
            patterns = mine_learnings.mine_archive(archive)

        # Three failures of one stage are two repeats, the same derivation the
        # repeated-test-invocation count uses. No report was written, which is
        # the condition under which this signal used to read zero.
        self.assertEqual(patterns["repeated_loops"], 2)
        self.assertEqual(patterns["reports_scanned"], 0)

    def test_distinct_stages_and_tasks_are_not_a_loop(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp)
            _write_run(
                archive,
                "myrepo/main",
                _today(),
                "run-1",
                [
                    {"type": "stage", "task_id": "t1", "stage": "qa", "exit_code": 1},
                    {"type": "stage", "task_id": "t1", "stage": "review", "exit_code": 1},
                    {"type": "stage", "task_id": "t2", "stage": "qa", "exit_code": 1},
                ],
            )
            patterns = mine_learnings.mine_archive(archive)

        self.assertEqual(patterns["repeated_loops"], 0)
        self.assertEqual(patterns["stage_failures"], 3)

    def test_one_stage_failing_in_two_runs_is_not_one_loop(self):
        """Each run is its own attempt sequence; a retry next run is not a loop."""
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp)
            for run_id in ("run-1", "run-2"):
                _write_run(
                    archive,
                    "myrepo/main",
                    _today(),
                    run_id,
                    [{"type": "stage", "task_id": "t1", "stage": "qa", "exit_code": 1}],
                )
            patterns = mine_learnings.mine_archive(archive)

        self.assertEqual(patterns["repeated_loops"], 0)


class TestRetiredNarrativeKeyword(unittest.TestCase):
    """The stale 'full_suite_runs' keyword list is no longer used."""

    def test_488_test_keyword_no_longer_counts_as_full_suite(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp)
            _write_run(archive, "myrepo/main", _today(), "run-1", [])
            run_dir = archive / "myrepo" / "main" / _today() / "run-1"
            (run_dir / "report.md").write_text(
                "The agent ran the 488-test suite five times.\n", encoding="utf-8"
            )
            patterns = mine_learnings.mine_archive(archive)
        self.assertEqual(patterns["full_suite_runs"], 0)
        self.assertEqual(patterns["reports_scanned"], 1)


if __name__ == "__main__":
    unittest.main()
