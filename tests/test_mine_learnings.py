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

_REPO_ROOT = Path(__file__).parent.parent
_MINE_LEARNINGS_PY = _REPO_ROOT / "aet-evolve" / "bin" / "mine-learnings"

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


if __name__ == "__main__":
    unittest.main()
