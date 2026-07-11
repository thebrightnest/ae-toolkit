"""Tests for the cross-project telemetry archive."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
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
        logger = telemetry.RunLogger(self.project_dir, run_id="run-001", date="2026-06-20")
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
        (run1 / "qa-report.md").write_text("The agent had to retry once.", encoding="utf-8")
        (run2 / "qa-report.md").write_text("The agent had to retry once.", encoding="utf-8")

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
        (run_dir / "qa-report.md").write_text("The agent had to retry once.", encoding="utf-8")

        patterns = mine_learnings.mine_archive(self.archive_dir)
        proposals = mine_learnings.propose_edits(patterns)

        self.assertIn("aet-setup", proposals)
        self.assertIn("aet-implement", proposals)
        self.assertNotIn(str(self.archive_dir), proposals)


class TestPruneArchive(unittest.TestCase):
    def setUp(self):
        self.archive_dir = Path(tempfile.mkdtemp(prefix="aet-prune-"))
        os.environ["AET_TELEMETRY_ARCHIVE_DIR"] = str(self.archive_dir)

    def tearDown(self):
        shutil.rmtree(self.archive_dir, ignore_errors=True)
        os.environ.pop("AET_TELEMETRY_ARCHIVE_DIR", None)

    def _backdate(self, path: Path, age_days: float) -> None:
        ts = time.time() - age_days * 86400
        for p in [path, *path.rglob("*")]:
            os.utime(p, (ts, ts))

    def _seed_run(self, project: str, date: str, run_id: str, age_days: float) -> Path:
        run_dir = self.archive_dir / project / date / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "t1.jsonl").write_text('{"type":"stage"}\n', encoding="utf-8")
        self._backdate(run_dir, age_days)
        return run_dir

    def test_prune_dry_run_lists_only(self):
        old = self._seed_run("proj", "2026-05-01", "old-run", 60)
        new = self._seed_run("proj", "2026-07-10", "new-run", 1)

        report = telemetry.prune_archive(30)

        self.assertTrue(old.exists())
        self.assertTrue(new.exists())
        self.assertEqual(report["deleted"], [])
        self.assertEqual(report["candidates"], [str(old)])

    def test_prune_force_deletes_old_runs(self):
        old_current = self._seed_run("proj", "2026-05-01", "old-run", 60)
        old_legacy = self.archive_dir / "proj" / "2026-05-02-legacy-run"
        old_legacy.mkdir(parents=True, exist_ok=True)
        (old_legacy / "t1.jsonl").write_text('{"type":"stage"}\n', encoding="utf-8")
        self._backdate(old_legacy, 60)
        new = self._seed_run("proj", "2026-07-10", "new-run", 1)

        report = telemetry.prune_archive(30, force=True)

        self.assertFalse(old_current.exists())
        self.assertFalse(old_legacy.exists())
        self.assertTrue(new.exists())
        self.assertEqual(
            sorted(report["deleted"]),
            sorted([str(old_current), str(old_legacy)]),
        )
        self.assertGreater(report["bytes_reclaimed"], 0)

    def test_prune_root_scope_narrows_to_project(self):
        scoped_current = self._seed_run("proj", "2026-05-01", "old-run", 60)
        scoped_legacy = self.archive_dir / "proj" / "2026-05-02-legacy-run"
        scoped_legacy.mkdir(parents=True, exist_ok=True)
        (scoped_legacy / "t1.jsonl").write_text('{"type":"stage"}\n', encoding="utf-8")
        self._backdate(scoped_legacy, 60)
        other = self._seed_run("other-proj", "2026-05-01", "old-run", 60)

        report = telemetry.prune_archive(30, root=self.archive_dir / "proj", force=True)

        self.assertFalse(scoped_current.exists())
        self.assertFalse(scoped_legacy.exists())
        self.assertTrue(other.exists())
        self.assertEqual(
            sorted(report["deleted"]),
            sorted([str(scoped_current), str(scoped_legacy)]),
        )

    def test_prune_skips_leased_run(self):
        leased = self._seed_run("proj", "2026-05-01", "leased-run", 60)
        doomed = self._seed_run("proj", "2026-05-01", "doomed-run", 60)

        report = telemetry.prune_archive(30, force=True, protected_run_ids=frozenset({"leased-run"}))

        self.assertTrue(leased.exists())
        self.assertFalse(doomed.exists())
        self.assertEqual(report["kept_protected"], [str(leased)])

    def test_prune_skips_fresh_or_summaryless_dirs(self):
        # The wfd-03 shape: an old-dated dir (empty, no last-run.json) whose
        # mtime is fresh because the run is live right now.
        fresh_old = self.archive_dir / "proj" / "2026-05-01" / "live-run"
        fresh_old.mkdir(parents=True, exist_ok=True)
        old = self._seed_run("proj", "2026-05-01", "old-run", 60)

        report = telemetry.prune_archive(30, force=True)

        self.assertTrue(fresh_old.exists())
        self.assertFalse(old.exists())
        self.assertNotIn(str(fresh_old), report["deleted"])

    def test_prune_removes_stale_empty_dirs(self):
        stale_date = self.archive_dir / "proj" / "2026-05-01"
        stale_date.mkdir(parents=True, exist_ok=True)
        self._backdate(stale_date, 60)
        stale_project = self.archive_dir / "proj-stale"
        stale_project.mkdir(parents=True, exist_ok=True)
        self._backdate(stale_project, 60)
        fresh_date = self.archive_dir / "proj" / "2026-07-10"
        fresh_date.mkdir(parents=True, exist_ok=True)

        telemetry.prune_archive(30, force=True)

        self.assertFalse(stale_date.exists())
        self.assertFalse(stale_project.exists())
        self.assertTrue(fresh_date.exists())
        self.assertTrue((self.archive_dir / "proj").exists())

        # Dry run never sweeps, even for stale dirs.
        telemetry.prune_archive(30)
        stale_again = self.archive_dir / "proj2" / "2026-05-01"
        stale_again.mkdir(parents=True, exist_ok=True)
        self._backdate(stale_again, 60)
        telemetry.prune_archive(30)
        self.assertTrue(stale_again.exists())

    def test_prune_root_outside_archive_rejected(self):
        outside = Path(tempfile.mkdtemp(prefix="aet-prune-outside-"))
        try:
            with self.assertRaises(ValueError):
                telemetry.prune_archive(30, root=outside, force=True)
            with self.assertRaises(ValueError):
                telemetry.prune_archive(30, root=self.archive_dir / ".." / "..", force=True)
        finally:
            shutil.rmtree(outside, ignore_errors=True)

    def test_prune_skips_symlinked_run_dirs(self):
        target = Path(tempfile.mkdtemp(prefix="aet-prune-link-target-"))
        try:
            link = self.archive_dir / "proj" / "2026-05-01" / "linked-run"
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(target)
            self._backdate(link.parent, 60)

            report = telemetry.prune_archive(30, force=True)

            self.assertTrue(target.exists())
            self.assertTrue(link.exists())
            self.assertEqual(report["deleted"], [])
        finally:
            shutil.rmtree(target, ignore_errors=True)

    def test_report_prune_cli_dry_run_smoke(self):
        old = self._seed_run("proj", "2026-05-01", "old-run", 60)
        report_bin = Path(__file__).parent.parent / "aet-work" / "bin" / "report"
        result = subprocess.run(
            [sys.executable, str(report_bin), "--prune", "7"],
            capture_output=True,
            text=True,
            cwd=self.archive_dir,
            env={**os.environ, "AET_TELEMETRY_ARCHIVE_DIR": str(self.archive_dir)},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("dry run", result.stdout.lower())
        self.assertTrue(old.exists())


if __name__ == "__main__":
    unittest.main()
