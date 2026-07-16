"""Tests for the zero-review mechanism (twe-06)."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "aet-work" / "lib"))
import telemetry  # noqa: E402
import track_record  # noqa: E402

_AET_STATE_PY = REPO_ROOT / "aet-work" / "bin" / "aet-state"
_spec = importlib.util.spec_from_loader(
    "aet_state", importlib.machinery.SourceFileLoader("aet_state", str(_AET_STATE_PY))
)
aet_state = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aet_state)


def _write_history(path: Path, tasks: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for task in tasks:
            f.write(json.dumps(task) + "\n")


def _write_verdicts(
    reports_dir: Path, project_slug: str, task_id: str, verdict: str = "pass"
) -> None:
    base = reports_dir / project_slug / task_id
    base.mkdir(parents=True, exist_ok=True)
    for kind in track_record.REQUIRED_VERDICT_KINDS:
        record = {
            "task_id": task_id,
            "stage": f"{kind}-stage",
            "skill": f"aet-{kind}",
            "verdict": verdict,
            "summary": "ok",
            "generated_at": "2026-07-09T20:00:00Z",
            "tree_hash": "t0",
        }
        if kind == "qa":
            record.update(
                {
                    "test_command": "pytest tests/",
                    "tests_total": 10,
                    "tests_passed": 10,
                    "tests_failed": 0,
                }
            )
        if kind in ("review", "cso"):
            record["findings"] = []
        if kind == "sync-docs":
            record["divergences"] = []
        (base / f"{kind}.json").write_text(json.dumps(record), encoding="utf-8")


def _make_clean_task(task_id: str, work_class: str = "trivial") -> dict:
    return {
        "id": task_id,
        "work_class": work_class,
        "state": "merged",
        "history": [
            {"from": None, "to": "planned", "at": "2026-07-09T10:00:00Z", "by": "add"},
            {
                "from": "planned",
                "to": "in_progress",
                "at": "2026-07-09T11:00:00Z",
                "by": "orchestrator",
            },
            {
                "from": "in_progress",
                "to": "awaiting_merge",
                "at": "2026-07-09T12:00:00Z",
                "by": "orchestrator",
            },
            {
                "from": "awaiting_merge",
                "to": "merged",
                "at": "2026-07-09T13:00:00Z",
                "by": "record-merge",
            },
        ],
    }


def _stage_record(task_id: str, stage: str, exit_code: int) -> dict:
    return telemetry.stage_record(
        run_id="run-1",
        task_id=task_id,
        plan_file=f"docs/plans/{task_id}.md",
        stage=stage,
        agent_cli="test",
        isolation_level="standard",
        start_time="2026-07-09T10:00:00Z",
        end_time="2026-07-09T10:05:00Z",
        exit_code=exit_code,
    )


class TestCleanMergeCounting(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.history_file = self.root / ".agents" / "work-history.jsonl"
        self.reports_dir = self.root / "reports"
        self.archive_dir = self.root / "telemetry"
        self.project_slug = "demo/project"

    def tearDown(self):
        self.tmp.cleanup()

    def test_clean_merge_counts_all_pass_no_rework(self):
        """A merged task with all verdicts pass and no rework counts as clean."""
        _write_history(self.history_file, [_make_clean_task("t-1", "trivial")])
        _write_verdicts(self.reports_dir, self.project_slug, "t-1", "pass")
        count = track_record.count_clean_merges(
            "trivial",
            history_file=self.history_file,
            reports_dir=self.reports_dir,
            archive_dir=self.archive_dir,
            project_slug=self.project_slug,
        )
        self.assertEqual(count, 1)

    def test_reworked_or_failed_merge_not_counted_clean(self):
        """Failed stage, failed verdict, re-entry from failed, or repeated stage run disqualify."""
        # Failed stage record in telemetry.
        task = _make_clean_task("t-1", "trivial")
        _write_history(self.history_file, [task])
        _write_verdicts(self.reports_dir, self.project_slug, "t-1", "pass")
        run_dir = self.archive_dir / self.project_slug / "2026-07-09" / "run-1"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "t-1.jsonl").write_text(
            json.dumps(_stage_record("t-1", "qa", 1)) + "\n", encoding="utf-8"
        )
        count = track_record.count_clean_merges(
            "trivial",
            history_file=self.history_file,
            reports_dir=self.reports_dir,
            archive_dir=self.archive_dir,
            project_slug=self.project_slug,
        )
        self.assertEqual(count, 0)

    def test_failing_verdict_disqualifies_clean_merge(self):
        """A required verdict that is not 'pass' disqualifies the merge."""
        _write_history(self.history_file, [_make_clean_task("t-1", "trivial")])
        _write_verdicts(self.reports_dir, self.project_slug, "t-1", "fail")
        count = track_record.count_clean_merges(
            "trivial",
            history_file=self.history_file,
            reports_dir=self.reports_dir,
            archive_dir=self.archive_dir,
            project_slug=self.project_slug,
        )
        self.assertEqual(count, 0)

    def test_reentry_from_failed_disqualifies_clean_merge(self):
        """A history transition from 'failed' back to a non-terminal state is rework."""
        task = _make_clean_task("t-1", "trivial")
        task["history"].insert(
            1,
            {
                "from": "failed",
                "to": "in_progress",
                "at": "2026-07-09T10:30:00Z",
                "by": "retry",
            },
        )
        _write_history(self.history_file, [task])
        _write_verdicts(self.reports_dir, self.project_slug, "t-1", "pass")
        count = track_record.count_clean_merges(
            "trivial",
            history_file=self.history_file,
            reports_dir=self.reports_dir,
            archive_dir=self.archive_dir,
            project_slug=self.project_slug,
        )
        self.assertEqual(count, 0)

    def test_repeated_stage_run_disqualifies_clean_merge(self):
        """Two telemetry stage records for the same stage name is rework."""
        _write_history(self.history_file, [_make_clean_task("t-1", "trivial")])
        _write_verdicts(self.reports_dir, self.project_slug, "t-1", "pass")
        run_dir = self.archive_dir / self.project_slug / "2026-07-09" / "run-1"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "t-1.jsonl").write_text(
            json.dumps(_stage_record("t-1", "implement", 0)) + "\n" +
            json.dumps(_stage_record("t-1", "implement", 0)) + "\n",
            encoding="utf-8",
        )
        count = track_record.count_clean_merges(
            "trivial",
            history_file=self.history_file,
            reports_dir=self.reports_dir,
            archive_dir=self.archive_dir,
            project_slug=self.project_slug,
        )
        self.assertEqual(count, 0)


class TestEligibilityReporting(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.history_file = self.root / ".agents" / "work-history.jsonl"
        self.reports_dir = self.root / "reports"
        self.archive_dir = self.root / "telemetry"
        self.project_slug = "demo/project"

    def tearDown(self):
        self.tmp.cleanup()

    def test_eligibility_reports_count_and_disabled_status(self):
        """Eligibility reports per-class clean-merge count and enabled/disabled status."""
        _write_history(
            self.history_file,
            [
                _make_clean_task("t-1", "trivial"),
                _make_clean_task("t-2", "trivial"),
                _make_clean_task("n-1", "normal"),
            ],
        )
        for tid in ("t-1", "t-2", "n-1"):
            _write_verdicts(self.reports_dir, self.project_slug, tid, "pass")

        trivial = track_record.class_eligibility(
            "trivial",
            policy=track_record.load_policy(str(self.root / "no-policy.json")),
            history_file=self.history_file,
            reports_dir=self.reports_dir,
            archive_dir=self.archive_dir,
            project_slug=self.project_slug,
        )
        self.assertEqual(trivial["count"], 2)
        self.assertFalse(trivial["enabled"])
        self.assertFalse(trivial["threshold_met"])

        enabled_policy = {"enabled_classes": {"trivial": True}, "thresholds": {"trivial": 2}}
        trivial_enabled = track_record.class_eligibility(
            "trivial",
            policy=enabled_policy,
            history_file=self.history_file,
            reports_dir=self.reports_dir,
            archive_dir=self.archive_dir,
            project_slug=self.project_slug,
        )
        self.assertTrue(trivial_enabled["enabled"])
        self.assertTrue(trivial_enabled["threshold_met"])

    def test_unclassified_never_eligible(self):
        """unclassified is never zero-review-eligible, even if policy enables it."""
        _write_history(self.history_file, [_make_clean_task("u-1", "unclassified")])
        _write_verdicts(self.reports_dir, self.project_slug, "u-1", "pass")
        task = {"id": "u-1", "work_class": "unclassified"}
        policy = {"enabled_classes": {"unclassified": True}, "thresholds": {"unclassified": 1}}
        self.assertFalse(
            track_record.is_eligible_for_auto_merge(
                task,
                policy=policy,
                history_file=self.history_file,
                reports_dir=self.reports_dir,
                archive_dir=self.archive_dir,
                project_slug=self.project_slug,
            )
        )

    def test_default_policy_empty_nothing_auto_merges(self):
        """With the default empty policy, no task is eligible for auto-merge."""
        _write_history(self.history_file, [_make_clean_task("t-1", "trivial")])
        _write_verdicts(self.reports_dir, self.project_slug, "t-1", "pass")
        task = {"id": "t-1", "work_class": "trivial"}
        self.assertFalse(
            track_record.is_eligible_for_auto_merge(
                task,
                policy=track_record.load_policy(str(self.root / "no-policy.json")),
                history_file=self.history_file,
                reports_dir=self.reports_dir,
                archive_dir=self.archive_dir,
                project_slug=self.project_slug,
            )
        )

    def test_enabled_class_below_threshold_left_for_human(self):
        """A class enabled but below its threshold is not eligible."""
        _write_history(self.history_file, [_make_clean_task("t-1", "trivial")])
        _write_verdicts(self.reports_dir, self.project_slug, "t-1", "pass")
        task = {"id": "t-1", "work_class": "trivial"}
        policy = {"enabled_classes": {"trivial": True}, "thresholds": {"trivial": 5}}
        self.assertFalse(
            track_record.is_eligible_for_auto_merge(
                task,
                policy=policy,
                history_file=self.history_file,
                reports_dir=self.reports_dir,
                archive_dir=self.archive_dir,
                project_slug=self.project_slug,
            )
        )


class TestAutoMergeAction(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.queue_file = self.root / ".agents" / "work-queue.json"
        self.history_file = self.queue_file.with_name("work-history.jsonl")
        self.plan_file = self.root / "docs" / "plans" / "t-1.md"
        self.plan_file.parent.mkdir(parents=True, exist_ok=True)
        self.plan_file.write_text("---\nid: t-1\n---\n\n# T-1\n", encoding="utf-8")
        queue = {
            "tasks": [
                {
                    "id": "t-1",
                    "state": "awaiting_merge",
                    "branch": "feat-t-1",
                    "plan_file": str(self.plan_file),
                    "work_class": "trivial",
                }
            ]
        }
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        self.queue_file.write_text(json.dumps(queue), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_enabled_class_at_threshold_auto_merges_via_closure_path(self):
        """An enabled class at threshold triggers record-merge, not awaiting_merge."""
        responses = {
            ("git", "fetch", "origin"): (0, "", ""),
            ("git", "checkout", "main"): (0, "", ""),
            ("git", "merge", "--no-ff", "-m", "auto-merge(t-1)", "feat-t-1"): (0, "", ""),
            ("git", "push", "origin", "main"): (0, "", ""),
            ("git", "rev-parse", "HEAD"): (0, "merge_sha\n", ""),
        }

        def mock_run(cmd, **kwargs):
            key = tuple(cmd)
            if key[0] == sys.executable and "record-merge" in key:
                # Simulate record-merge success by transitioning the task.
                with open(self.queue_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["tasks"] = []
                with open(self.queue_file, "w", encoding="utf-8") as f:
                    json.dump(data, f)
                return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            rc, out, err = responses.get(key, (1, "", ""))
            return type("R", (), {"returncode": rc, "stdout": out, "stderr": err})()

        with patch.object(track_record.subprocess, "run", side_effect=mock_run):
            merged = track_record.perform_auto_merge(
                {"id": "t-1", "branch": "feat-t-1"},
                str(self.queue_file),
                str(self.root),
            )

        self.assertTrue(merged)
        with open(self.queue_file, "r", encoding="utf-8") as f:
            live = json.load(f)
        self.assertEqual(live["tasks"], [])

    def test_git_failure_aborts_auto_merge(self):
        """If any git step fails, perform_auto_merge returns False and does not record-merge."""
        responses = {
            ("git", "fetch", "origin"): (0, "", ""),
            ("git", "checkout", "main"): (0, "", ""),
            ("git", "merge", "--no-ff", "-m", "auto-merge(t-1)", "feat-t-1"): (1, "", "merge failed"),
        }

        calls = []

        def mock_run(cmd, **kwargs):
            calls.append(tuple(cmd))
            key = tuple(cmd)
            rc, out, err = responses.get(key, (1, "", ""))
            return type("R", (), {"returncode": rc, "stdout": out, "stderr": err})()

        with patch.object(track_record.subprocess, "run", side_effect=mock_run):
            merged = track_record.perform_auto_merge(
                {"id": "t-1", "branch": "feat-t-1"},
                str(self.queue_file),
                str(self.root),
            )

        self.assertFalse(merged)
        self.assertNotIn((sys.executable, "record-merge"), calls)


class TestLoadPolicy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_policy_returns_empty_default(self):
        """A missing policy file yields the empty default (nothing enabled)."""
        policy = track_record.load_policy(str(self.root / "nonexistent.json"))
        self.assertEqual(policy, {"enabled_classes": {}, "thresholds": {}})

    def test_existing_policy_loaded(self):
        """An existing policy file is loaded and normalized."""
        path = self.root / "policy.json"
        path.write_text(
            json.dumps({"enabled_classes": {"trivial": True}, "thresholds": {"trivial": 3}}),
            encoding="utf-8",
        )
        policy = track_record.load_policy(str(path))
        self.assertTrue(policy["enabled_classes"]["trivial"])
        self.assertEqual(policy["thresholds"]["trivial"], 3)

    def test_malformed_policy_returns_empty_default(self):
        """A malformed policy file yields the empty default."""
        path = self.root / "policy.json"
        path.write_text("not json", encoding="utf-8")
        policy = track_record.load_policy(str(path))
        self.assertEqual(policy, {"enabled_classes": {}, "thresholds": {}})


if __name__ == "__main__":
    unittest.main()
