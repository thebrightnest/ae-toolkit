"""Tests for the cross-project telemetry archive scripts."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

BIN_DIR = Path(__file__).parent.parent / "aet-evolve" / "bin"


def _load_module(module_name: str, script_path: Path):
    """Load a hyphenated script as an importable module."""
    from importlib.machinery import SourceFileLoader

    loader = SourceFileLoader(module_name, str(script_path))
    spec = importlib.util.spec_from_loader(module_name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


ingest_telemetry = _load_module(
    "ingest_telemetry", BIN_DIR / "ingest-telemetry"
)
mine_learnings = _load_module(
    "mine_learnings", BIN_DIR / "mine-learnings"
)


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")


class TestIngestTelemetry(unittest.TestCase):
    def setUp(self):
        self.project_dir = Path(tempfile.mkdtemp(prefix="aet-project-"))
        self.archive_dir = Path(tempfile.mkdtemp(prefix="aet-archive-"))
        self.reports_dir = Path(tempfile.mkdtemp(prefix="aet-reports-"))

    def tearDown(self):
        shutil = __import__("shutil")
        shutil.rmtree(self.project_dir, ignore_errors=True)
        shutil.rmtree(self.archive_dir, ignore_errors=True)
        shutil.rmtree(self.reports_dir, ignore_errors=True)

    def test_creates_archive_with_sanitized_paths_and_headers(self):
        repo_path = str(self.project_dir)
        execution_log = self.project_dir / ".agents" / "execution.log.jsonl"
        _write_jsonl(
            execution_log,
            [
                {
                    "type": "stage",
                    "run_id": "r1",
                    "task_id": "t1",
                    "plan_file": str(self.project_dir / "docs" / "plans" / "x.md"),
                    "stage": "implemented",
                    "exit_code": 0,
                }
            ],
        )

        work_history = self.project_dir / ".agents" / "work-history.jsonl"
        _write_jsonl(
            work_history,
            [
                {
                    "id": "t1",
                    "plan_file": str(self.project_dir / "docs" / "plans" / "x.md"),
                }
            ],
        )

        report_file = self.reports_dir / "t1" / "report.md"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(
            f"# Report\n\nRun completed in {self.project_dir / '.agents'}.\n",
            encoding="utf-8",
        )

        archive_path = ingest_telemetry.ingest(
            run_id="run-001",
            project_id="demo-project",
            repo_slug="demo/repo",
            repo_root=self.project_dir,
            archive_dir=self.archive_dir,
            reports_dir=self.reports_dir,
            date="2026-06-20",
        )

        self.assertTrue(archive_path.exists())
        manifest_path = archive_path / "manifest.json"
        self.assertTrue(manifest_path.exists())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["project_id"], "demo-project")
        self.assertEqual(manifest["repo_slug"], "demo/repo")
        self.assertEqual(manifest["run_id"], "run-001")

        dests = {entry["dest"] for entry in manifest["files"]}
        self.assertIn("execution.log.jsonl", dests)
        self.assertIn("t1/report.md", dests)

        archived_execution = archive_path / "execution.log.jsonl"
        self.assertTrue(archived_execution.exists())
        archived_text = archived_execution.read_text(encoding="utf-8")
        self.assertNotIn(repo_path, archived_text)
        self.assertIn("{REPO_ROOT}", archived_text)

        archived_report = archive_path / "t1" / "report.md"
        self.assertTrue(archived_report.exists())
        report_text = archived_report.read_text(encoding="utf-8")
        self.assertIn("project_id: demo-project", report_text)
        self.assertIn("repo_slug: demo/repo", report_text)
        self.assertNotIn(repo_path, report_text)

    def test_handles_missing_source_files_gracefully(self):
        archive_path = ingest_telemetry.ingest(
            run_id="run-empty",
            project_id="empty-project",
            repo_slug="empty/repo",
            repo_root=self.project_dir,
            archive_dir=self.archive_dir,
            reports_dir=self.reports_dir,
            date="2026-06-20",
        )

        self.assertTrue(archive_path.exists())
        manifest = json.loads((archive_path / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["files"], [])


class TestMineLearnings(unittest.TestCase):
    def setUp(self):
        self.archive_dir = Path(tempfile.mkdtemp(prefix="aet-mine-"))

    def tearDown(self):
        shutil = __import__("shutil")
        shutil.rmtree(self.archive_dir, ignore_errors=True)

    def _seed_run(self, project_id: str, run_name: str, records: list[dict]) -> Path:
        run_dir = self.archive_dir / project_id / run_name
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "project_id": project_id,
            "repo_slug": f"{project_id}/repo",
            "run_id": run_name,
            "archived_at": "2026-06-20T00:00:00Z",
            "files": [],
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        _write_jsonl(run_dir / "execution.log.jsonl", records)
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
                "type": "loop",
                "run_id": "r1",
                "loop_type": "format_fix",
                "iteration": 2,
                "exit_code": 0,
            },
            {
                "type": "stage",
                "run_id": "r1",
                "stage": "review",
                "exit_code": 1,
            },
        ]
        self._seed_run("p1", "2026-06-20-r1", records)
        self._seed_run("p2", "2026-06-20-r2", records)

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
            {
                "type": "loop",
                "run_id": "r1",
                "loop_type": "format_fix",
                "iteration": 2,
                "exit_code": 0,
            },
        ]
        self._seed_run("p1", "2026-06-20-r1", records)

        patterns = mine_learnings.mine_archive(self.archive_dir)
        proposals = mine_learnings.propose_edits(patterns)

        self.assertIn("aet-setup", proposals)
        self.assertIn("aet-implement", proposals)
        self.assertNotIn(str(self.archive_dir), proposals)


if __name__ == "__main__":
    unittest.main()
