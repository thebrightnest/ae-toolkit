"""Tests for the cross-project telemetry archive."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

EVOLVE_BIN_DIR = Path(__file__).parent.parent / "aet-evolve" / "bin"
WORK_LIB_DIR = Path(__file__).parent.parent / "aet-work" / "lib"
sys.path.insert(0, str(WORK_LIB_DIR))

import telemetry  # noqa: E402


def _load_module(module_name: str, script_path: Path):
    """Load a hyphenated script as an importable module."""
    from importlib.machinery import SourceFileLoader

    loader = SourceFileLoader(module_name, str(script_path))
    spec = importlib.util.spec_from_loader(module_name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


mine_learnings = _load_module("mine_learnings", EVOLVE_BIN_DIR / "mine-learnings")


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")


class TestDirectArchive(unittest.TestCase):
    def setUp(self):
        self.project_dir = Path(tempfile.mkdtemp(prefix="aet-project-"))
        self.archive_dir = Path(tempfile.mkdtemp(prefix="aet-archive-"))
        os.environ["AET_TELEMETRY_ARCHIVE_DIR"] = str(self.archive_dir)

    def tearDown(self):
        shutil = __import__("shutil")
        shutil.rmtree(self.project_dir, ignore_errors=True)
        shutil.rmtree(self.archive_dir, ignore_errors=True)
        os.environ.pop("AET_TELEMETRY_ARCHIVE_DIR", None)

    def test_run_logger_creates_dated_run_directory(self):
        logger = telemetry.RunLogger(
            self.project_dir, run_id="run-001", date="2026-06-20"
        )
        self.assertTrue(logger.run_dir.exists())
        self.assertIn("run-001", str(logger.run_dir))
        self.assertIn("2026-06-20", str(logger.run_dir))

    def test_run_logger_sanitizes_paths_at_write_time(self):
        resolved = self.project_dir.resolve()
        logger = telemetry.RunLogger(resolved, run_id="run-001")
        logger.append_record(
            {
                "type": "stage",
                "plan_file": str(resolved / "docs" / "plans" / "x.md"),
            },
            task_id="t1",
        )

        task_log = logger.task_log_path("t1")
        self.assertTrue(task_log.exists())
        archived_text = task_log.read_text(encoding="utf-8")
        self.assertNotIn(str(resolved), archived_text)
        self.assertIn("{REPO_ROOT}", archived_text)

    def test_run_logger_writes_last_run_summary(self):
        logger = telemetry.RunLogger(self.project_dir, run_id="run-001")
        summary = telemetry.run_summary_record(
            run_id="run-001",
            start_time="2026-06-20T00:00:00Z",
            end_time="2026-06-20T00:01:00Z",
            tasks_spawned=1,
            tasks_succeeded=1,
            tasks_failed=0,
            outcome="success",
            exit_code=0,
            task_ids=["t1"],
        )
        logger.write_last_run(summary)

        last_run = logger.run_dir / "last-run.json"
        self.assertTrue(last_run.exists())
        self.assertEqual(json.loads(last_run.read_text())["outcome"], "success")


class TestMineLearnings(unittest.TestCase):
    def setUp(self):
        self.archive_dir = Path(tempfile.mkdtemp(prefix="aet-mine-"))

    def tearDown(self):
        shutil = __import__("shutil")
        shutil.rmtree(self.archive_dir, ignore_errors=True)

    def _seed_run(self, project_id: str, date: str, run_name: str, task_records: dict[str, list[dict]]) -> Path:
        run_dir = self.archive_dir / project_id / date / run_name
        run_dir.mkdir(parents=True, exist_ok=True)
        for task_id, records in task_records.items():
            _write_jsonl(run_dir / f"{task_id}.jsonl", records)
        return run_dir

    def test_report_lists_recurring_patterns(self):
        records = [
            {
                "type": "environment_issue",
                "run_id": "r1",
                "issue_type": "missing_dependency",
                "dependency": "prettier",
            },
            {
                "type": "stage",
                "run_id": "r1",
                "stage": "review",
                "exit_code": 1,
            },
        ]
        run1 = self._seed_run("p1", "2026-06-20", "r1", {"t1": records})
        run2 = self._seed_run("p2", "2026-06-20", "r2", {"t1": records})
        # Loop records were removed (frh-09); the repeated-loops signal is now
        # mined from narrative report text rather than JSONL loop records.
        (run1 / "qa-report.md").write_text(
            "The agent had to retry once.", encoding="utf-8"
        )
        (run2 / "qa-report.md").write_text(
            "The agent had to retry once.", encoding="utf-8"
        )

        patterns = mine_learnings.mine_archive(self.archive_dir)
        report = mine_learnings.format_report(patterns)

        self.assertIn("Dependency issues: 2", report)
        self.assertIn("Repeated loops: 2", report)
        self.assertIn("Stage failures: 2", report)
        self.assertIn("Review noise: 2", report)

    def test_propose_prints_suggestions_without_writing(self):
        records = [
            {
                "type": "environment_issue",
                "run_id": "r1",
                "issue_type": "missing_dependency",
                "dependency": "prettier",
            },
        ]
        run_dir = self._seed_run("p1", "2026-06-20", "r1", {"t1": records})
        # Surface a repeated-loop signal via narrative mining; loop JSONL records
        # are no longer emitted, so they cannot drive the aet-implement proposal.
        (run_dir / "qa-report.md").write_text(
            "The agent had to retry once.", encoding="utf-8"
        )

        patterns = mine_learnings.mine_archive(self.archive_dir)
        proposals = mine_learnings.propose_edits(patterns)

        self.assertIn("aet-setup", proposals)
        self.assertIn("aet-implement", proposals)
        self.assertNotIn(str(self.archive_dir), proposals)


if __name__ == "__main__":
    unittest.main()
