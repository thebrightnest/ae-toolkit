"""Tests for aet-retro learning-candidate telemetry emission."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).parents[2]
_RETRO_PY = _REPO_ROOT / "src" / "aet" / "cli" / "retro.py"
_MINE_LEARNINGS_PY = _REPO_ROOT / "src" / "aet" / "cli" / "mine-learnings.py"

_retro_spec = importlib.util.spec_from_loader(
    "aet_retro", importlib.machinery.SourceFileLoader("aet_retro", str(_RETRO_PY))
)
aet_retro = importlib.util.module_from_spec(_retro_spec)
_retro_spec.loader.exec_module(aet_retro)

_mine_spec = importlib.util.spec_from_loader(
    "mine_learnings",
    importlib.machinery.SourceFileLoader("mine_learnings", str(_MINE_LEARNINGS_PY)),
)
mine_learnings = importlib.util.module_from_spec(_mine_spec)
sys.modules["mine_learnings"] = mine_learnings
_mine_spec.loader.exec_module(mine_learnings)


def _make_telemetry_archive(project_slug: str = "owner/repo") -> Path:
    """Create a temp archive with a few recent project telemetry records."""
    tmp = Path(tempfile.mkdtemp())
    date_dir = tmp / project_slug / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    date_dir.mkdir(parents=True)
    run_dir = date_dir / "run-123"
    run_dir.mkdir()
    log = run_dir / "task-456.jsonl"
    records = [
        {
            "type": "stage",
            "run_id": "run-123",
            "task_id": "task-456",
            "plan_file": "docs/plans/frh-12-retro-learning-candidates.md",
            "stage": "implemented",
            "message": "API contract drift between frontend cart and backend checkout",
        },
        {
            "type": "stage",
            "run_id": "run-123",
            "task_id": "task-456",
            "plan_file": "docs/plans/frh-12-retro-learning-candidates.md",
            "stage": "qa-complete",
            "message": "aet-review flagged mock-boundary violation in aet-work lib",
        },
    ]
    log.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return tmp


class TestAetRetroEmitsLearningCandidates(unittest.TestCase):
    def test_retro_emits_learning_candidate_records(self):
        """aet-retro appends one learning_candidate record per finding."""
        archive_dir = _make_telemetry_archive()
        output = archive_dir / "retro.md"

        env = {
            "AET_TELEMETRY_ARCHIVE_DIR": str(archive_dir),
            "AET_PROJECT_ID": "owner/repo",
            "AET_RUN_ID": "run-789",
            "AET_TASK_ID": "task-abc",
            "AET_PLAN_FILE": "docs/plans/frh-12-retro-learning-candidates.md",
        }

        with patch.dict(os.environ, env, clear=False):
            rc = aet_retro.main([
                "--archive-dir", str(archive_dir),
                "--no-mine",
                "--output", str(output),
                "--lookback-days", "7",
            ])

        self.assertEqual(rc, 0)
        self.assertTrue(output.exists())

        # Find the new task log written by aet-retro.
        run_dirs = list((archive_dir / "owner/repo").rglob("run-789"))
        self.assertEqual(len(run_dirs), 1, "Expected one run dir for run-789")
        task_logs = list(run_dirs[0].glob("task-abc.jsonl"))
        self.assertEqual(len(task_logs), 1, "Expected one task log for task-abc")

        records = aet_retro.read_jsonl(task_logs[0])
        candidates = [r for r in records if r.get("type") == "learning_candidate"]
        self.assertGreaterEqual(len(candidates), 2, "Expected at least project + AET candidates")

        for candidate in candidates:
            self.assertEqual(candidate["run_id"], "run-789")
            self.assertEqual(candidate["task_id"], "task-abc")
            self.assertEqual(
                candidate["plan_file"],
                "docs/plans/frh-12-retro-learning-candidates.md",
            )
            self.assertEqual(candidate["stage"], "retro")
            self.assertIn(candidate["pattern_type"], ("project_finding", "aet_finding"))
            self.assertIsInstance(candidate["description"], str)
            self.assertIn(candidate["evidence"].get("source"), ("project_finding", "aet_finding"))


class TestMineLearningsParsesLearningCandidates(unittest.TestCase):
    def test_learning_candidate_records_parse_with_mine_learnings(self):
        """mine-learnings reads learning_candidate records without crashing."""
        tmp = Path(tempfile.mkdtemp())
        date_dir = tmp / "myproject" / "main" / datetime.now(timezone.utc).strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True)
        run_dir = date_dir / "run-123"
        run_dir.mkdir()
        log = run_dir / "task-456.jsonl"
        records = [
            {
                "type": "learning_candidate",
                "run_id": "run-123",
                "task_id": "task-456",
                "plan_file": "docs/plans/frh-12-retro-learning-candidates.md",
                "stage": "retro",
                "pattern_type": "project_finding",
                "description": "API contract drift between frontend and backend",
                "evidence": {"source": "project_finding"},
                "confidence": 0.8,
            },
            {
                "type": "learning_candidate",
                "run_id": "run-123",
                "task_id": "task-456",
                "plan_file": "docs/plans/frh-12-retro-learning-candidates.md",
                "stage": "retro",
                "pattern_type": "aet_finding",
                "description": "mock-boundary violation in aet-work lib",
                "evidence": {"source": "aet_finding"},
                "confidence": 0.7,
            },
        ]
        log.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")

        patterns = mine_learnings.mine_archive(tmp)
        self.assertEqual(patterns.get("learning_candidates", 0), 2)
        self.assertIn("API contract drift", str(patterns.get("examples", {}).get("learning_candidates", [])))
        self.assertIn("mock-boundary violation", str(patterns.get("examples", {}).get("learning_candidates", [])))


class TestRunMineLearningsInvocation(unittest.TestCase):
    """aet-retro must not rely on the pruned `mine-learnings` PATH name (R-5)."""

    def test_invokes_sibling_binary_not_path_lookup(self):
        """The legacy PATH symlink is pruned on install; call the sibling bin."""
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            captured["env"] = kwargs.get("env", {})

            class Result:
                returncode = 0
                stdout = "patterns"
                stderr = ""

            return Result()

        with patch.object(aet_retro.subprocess, "run", fake_run):
            out = aet_retro.run_mine_learnings(Path("/tmp/archive"))

        self.assertEqual(out, "patterns")
        self.assertEqual(
            captured["cmd"],
            [str(_MINE_LEARNINGS_PY), "--propose"],
        )
        self.assertEqual(captured["env"].get("AET_TELEMETRY_ARCHIVE_DIR"), "/tmp/archive")
