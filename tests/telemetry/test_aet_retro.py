"""Reader-contract tests for aet-retro against the telemetry writer layout (tele-07)."""

from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).parents[2]
_RETRO_PY = _REPO_ROOT / "src" / "aet" / "cli" / "retro.py"

_spec = importlib.util.spec_from_loader(
    "aet_retro_reader", importlib.machinery.SourceFileLoader("aet_retro_reader", str(_RETRO_PY))
)
aet_retro = importlib.util.module_from_spec(_spec)
sys.modules["aet_retro_reader"] = aet_retro
_spec.loader.exec_module(aet_retro)


def _make_writer_archive() -> Path:
    """Temp archive in the writer layout ({dir}/{label}/{date}/{run}/) mixing
    typed findings with noise records that must never render."""
    tmp = Path(tempfile.mkdtemp())
    run_dir = tmp / "myrepo" / "main" / datetime.now(timezone.utc).strftime("%Y-%m-%d") / "run-1"
    run_dir.mkdir(parents=True)
    records = [
        {
            "type": "learning_candidate",
            "run_id": "run-1",
            "task_id": "task-1",
            "stage": "retro",
            "pattern_type": "project_finding",
            "description": "API contract drift between frontend cart and backend checkout",
        },
        {
            "type": "stage",
            "run_id": "run-1",
            "task_id": "task-1",
            "stage": "reviewed",
            "message": "aet-review flagged mock-boundary violation in aet-work lib",
        },
        # Noise: a bare stage record carries no human-readable text...
        {"type": "stage", "run_id": "run-1", "task_id": "task-1", "stage": "qa-complete", "exit_code": 0},
        # ...and a queue snapshot must never render as a dict repr.
        {"type": "queue_snapshot", "tasks": [{"id": "abc-123", "status": "ready"}]},
    ]
    (run_dir / "task-1.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return tmp


class TestRetroFindingsAreTypedNotGuessed(unittest.TestCase):
    def test_retro_renders_real_findings_and_skips_untyped_records(self):
        archive = _make_writer_archive()
        output = archive / "retro.md"
        with patch.dict(os.environ, {"AET_PROJECT_ID": "myrepo/main"}, clear=False):
            rc = aet_retro.main(
                [
                    "--archive-dir",
                    str(archive),
                    "--no-mine",
                    "--output",
                    str(output),
                ]
            )
        self.assertEqual(rc, 0)
        text = output.read_text(encoding="utf-8")

        # Real findings render, split by where the fix should land.
        self.assertIn("### Project-level findings", text)
        self.assertIn("### AET-level findings", text)
        project_section = text.split("### Project-level findings", 1)[1].split("### AET-level findings", 1)[0]
        aet_section = text.split("### AET-level findings", 1)[1]
        self.assertIn("API contract drift between frontend cart and backend checkout", project_section)
        self.assertIn("aet-review flagged mock-boundary violation in aet-work lib", aet_section)

        # Bare stage names and dict reprs never render as findings.
        self.assertNotIn("qa-complete", text)
        self.assertNotIn("'type':", text)
        self.assertNotIn('"type":', text)


class TestExtractMessage(unittest.TestCase):
    def test_learning_candidate_uses_description(self):
        msg = aet_retro.extract_message({"type": "learning_candidate", "description": "real finding"})
        self.assertEqual(msg, "real finding")

    def test_explicit_text_fields_are_findings(self):
        self.assertEqual(aet_retro.extract_message({"type": "stage", "message": "boom"}), "boom")
        self.assertEqual(aet_retro.extract_message({"error": "nope"}), "nope")
        self.assertEqual(aet_retro.extract_message({"summary": "sum"}), "sum")

    def test_untyped_records_have_no_message(self):
        self.assertIsNone(aet_retro.extract_message({"type": "stage", "stage": "qa-complete"}))
        self.assertIsNone(aet_retro.extract_message({"type": "queue_snapshot", "tasks": []}))
        self.assertIsNone(aet_retro.extract_message({}))
        self.assertIsNone(aet_retro.extract_message("not a dict"))

    def test_records_without_text_are_not_findings(self):
        aet, project, dropped = aet_retro.categorize_records(
            [
                {"type": "stage", "stage": "secure"},
                {"type": "queue_snapshot", "tasks": [{"id": "x"}]},
            ]
        )
        self.assertEqual(aet, [])
        self.assertEqual(project, [])
        self.assertEqual(dropped, 2)


class TestDistinguishAbsentFromDroppedRecords(unittest.TestCase):
    """Absent records and dropped records render differently in aet-retro (ADR-072 / eop-07)."""

    def test_empty_archive_renders_no_telemetry_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp)
            output = archive / "retro.md"
            with patch.dict(os.environ, {"AET_PROJECT_ID": "myrepo/main"}, clear=False):
                rc = aet_retro.main(["--archive-dir", str(archive), "--no-mine", "--output", str(output)])
            self.assertEqual(rc, 0)
            text = output.read_text(encoding="utf-8")

        self.assertIn("- No telemetry records.", text)

    def test_archive_with_dropped_records_reports_drop_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp)
            run_dir = archive / "myrepo" / "main" / datetime.now(timezone.utc).strftime("%Y-%m-%d") / "run-1"
            run_dir.mkdir(parents=True)
            records = [
                {"type": "stage", "stage": "qa-complete", "exit_code": 0},
                {"type": "queue_snapshot", "tasks": []},
            ]
            (run_dir / "task-1.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
            output = archive / "retro.md"
            with patch.dict(os.environ, {"AET_PROJECT_ID": "myrepo/main"}, clear=False):
                rc = aet_retro.main(["--archive-dir", str(archive), "--no-mine", "--output", str(output)])
            self.assertEqual(rc, 0)
            text = output.read_text(encoding="utf-8")

        self.assertIn("- No findings (2 records dropped lacking usable finding text).", text)

    def test_absent_and_dropped_outputs_differ(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty_archive = Path(tmp) / "empty"
            empty_archive.mkdir()
            empty_output = empty_archive / "retro.md"

            dropped_archive = Path(tmp) / "dropped"
            run_dir = dropped_archive / "myrepo" / "main" / datetime.now(timezone.utc).strftime("%Y-%m-%d") / "run-1"
            run_dir.mkdir(parents=True)
            (run_dir / "task-1.jsonl").write_text(
                json.dumps({"type": "stage", "stage": "qa-complete", "exit_code": 0}) + "\n",
                encoding="utf-8",
            )
            dropped_output = dropped_archive / "retro.md"

            with patch.dict(os.environ, {"AET_PROJECT_ID": "myrepo/main"}, clear=False):
                aet_retro.main(["--archive-dir", str(empty_archive), "--no-mine", "--output", str(empty_output)])
                aet_retro.main(["--archive-dir", str(dropped_archive), "--no-mine", "--output", str(dropped_output)])

            empty_text = empty_output.read_text(encoding="utf-8")
            dropped_text = dropped_output.read_text(encoding="utf-8")

        self.assertNotEqual(empty_text, dropped_text)


class TestProjectSlugContract(unittest.TestCase):
    """The reader's slug derivation is literally the writer's — no second implementation."""

    def test_reader_imports_writers_derive_project_slug(self):
        from aet import telemetry

        self.assertIsNotNone(aet_retro.derive_project_slug)
        self.assertIs(aet_retro.derive_project_slug, telemetry.derive_project_slug)

    def test_reader_and_writer_slug_match_for_temp_repo(self):
        from aet import telemetry

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "myrepo"
            repo.mkdir()
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            with patch.dict(os.environ, {"AET_REPO_ROOT": str(repo)}, clear=False):
                os.environ.pop("AET_PROJECT_ID", None)
                os.environ.pop("AET_REPO_SLUG", None)
                reader_slug = aet_retro.derive_project_slug()
                writer_slug = telemetry.derive_project_slug()
        self.assertEqual(reader_slug, "myrepo/main")
        self.assertEqual(reader_slug, writer_slug)

    def test_missing_writer_lib_exits_with_named_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "retro.md"
            stderr = io.StringIO()
            with patch.object(aet_retro, "derive_project_slug", None):
                with contextlib.redirect_stderr(stderr):
                    rc = aet_retro.main(["--archive-dir", tmp, "--no-mine", "--output", str(output)])
        self.assertEqual(rc, 1)
        self.assertIn("aet", stderr.getvalue())
        self.assertFalse(output.exists())


class TestTelemetrySummaryEmbedsMineLearnings(unittest.TestCase):
    """The retro embeds mine-learnings --propose output verbatim."""

    def _write_run(self, archive: Path, slug: str, records: list[dict]) -> Path:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        run_dir = archive / slug / date / "run-1"
        run_dir.mkdir(parents=True)
        (run_dir / "task-1.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
        return run_dir

    def test_telemetry_summary_renders_new_counts_and_propose(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "archive"
            output = Path(tmp) / "retro.md"
            records = [
                {"type": "test_run", "task_id": "t1", "scope": "full-suite", "source": "wire"},
                {"type": "test_run", "task_id": "t1", "scope": "full-suite", "source": "wire"},
                {"type": "test_run", "task_id": "t2", "scope": "impact", "source": "wire"},
                {"type": "stage", "stage": "qa", "duration_seconds": 1900, "token_count": 0},
                {"type": "stage", "stage": "implement", "duration_seconds": 0, "token_count": 6_000_000},
            ]
            self._write_run(archive, "myrepo/main", records)
            with patch.dict(os.environ, {"AET_PROJECT_ID": "myrepo/main"}, clear=False):
                rc = aet_retro.main(["--archive-dir", str(archive), "--output", str(output)])
            self.assertEqual(rc, 0)
            text = output.read_text(encoding="utf-8")

            # Telemetry Summary block contains the new structural counts.
            summary = text.split("## Telemetry Summary", 1)[1].split("## Findings", 1)[0]
            self.assertIn("Full-suite runs (observed): 2", summary)
            self.assertIn("Impact-scoped runs (observed): 1", summary)
            self.assertIn("Repeated test invocations (observed): 1", summary)
            self.assertIn("Slow stages", summary)
            self.assertIn("Token-burn stages", summary)

            # Proposed skill edits reference the new patterns.
            self.assertIn("prefer impact-scoped tests", text)
            self.assertIn("stage-time triage", text)
            self.assertIn("trim prompt context", text)


if __name__ == "__main__":
    unittest.main()
