"""Tests for factory metrics counting core."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aet import telemetry, track_record


def _make_task(tmp_path: Path, task_id: str) -> dict[str, object]:
    plan_file = tmp_path / "plans" / f"{task_id}.md"
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text(
        f"---\nid: {task_id}\n---\n\n# {task_id}\n",
        encoding="utf-8",
    )
    return {
        "id": task_id,
        "state": "merged",
        "work_class": "normal",
        "plan_file": str(plan_file),
        "history": [],
    }


def _write_verdicts(reports_dir: Path, project_slug: str, task_id: str, kinds: list[str]) -> None:
    base = reports_dir / project_slug / task_id
    base.mkdir(parents=True, exist_ok=True)
    for kind in kinds:
        record: dict[str, object] = {
            "task_id": task_id,
            "stage": kind,
            "skill": f"aet-{kind}",
            "verdict": "pass",
            "summary": "ok",
            "generated_at": "2026-07-09T20:00:00Z",
            "tree_hash": "t0",
        }
        if kind == "qa":
            record.update(
                {
                    "test_command": "pytest",
                    "tests_total": 10,
                    "tests_passed": 10,
                    "tests_failed": 0,
                }
            )
        elif kind == "sync-docs":
            record["divergences"] = []
        else:
            record["findings"] = []
        (base / f"{kind}.json").write_text(json.dumps(record), encoding="utf-8")


def _stage_record(task_id: str, stage: str, exit_code: int = 0) -> dict[str, object]:
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


def _test_run_record(
    task_id: str,
    stage: str,
    exit_code: int = 0,
    source: str = "wire",
) -> dict[str, object]:
    record = telemetry.test_run_record(
        run_id="run-1",
        task_id=task_id,
        plan_file=f"docs/plans/{task_id}.md",
        stage=stage,
        scope="impact",
        test_command="pytest tests/foo.py",
        start_time="2026-07-09T10:00:00Z",
        end_time="2026-07-09T10:01:00Z",
        exit_code=exit_code,
    )
    record["source"] = source
    return record


def _write_records(tmp_path: Path, task_id: str, records: list[dict[str, object]]) -> None:
    run_dir = tmp_path / "telemetry" / "demo" / "project" / "2026-07-09" / "run-1"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / f"{task_id}.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in records),
        encoding="utf-8",
    )


@pytest.fixture(autouse=True)
def _isolate_reports_dir(monkeypatch, tmp_path):
    """Point evidence and telemetry archives at per-test tmp dirs."""
    monkeypatch.setenv("AET_REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("AET_TELEMETRY_ARCHIVE_DIR", str(tmp_path / "telemetry"))


def test_rework_count_ignores_test_run_records_in_same_stage(tmp_path):
    """One stage record plus three test_run records in one stage yields 0 rework."""
    task = _make_task(tmp_path, "t-1")
    _write_records(
        tmp_path,
        "t-1",
        [
            _stage_record("t-1", "implement"),
            _test_run_record("t-1", "implement"),
            _test_run_record("t-1", "implement"),
            _test_run_record("t-1", "implement"),
        ],
    )
    assert (
        track_record.rework_count(
            task,
            archive_dir=tmp_path / "telemetry",
            project_slug="demo/project",
        )
        == 0
    )


def test_rework_count_still_counts_repeated_stage_records(tmp_path):
    """Repeated stage records beyond the first per stage name still count."""
    task = _make_task(tmp_path, "t-1")
    _write_records(
        tmp_path,
        "t-1",
        [
            _stage_record("t-1", "implement"),
            _stage_record("t-1", "implement"),
        ],
    )
    assert (
        track_record.rework_count(
            task,
            archive_dir=tmp_path / "telemetry",
            project_slug="demo/project",
        )
        == 1
    )


def test_rework_count_still_counts_failed_reentry_transitions(tmp_path):
    """History transitions from 'failed' still count as rework."""
    task = _make_task(tmp_path, "t-1")
    task["history"].append(
        {
            "from": "failed",
            "to": "in_progress",
            "at": "2026-07-09T10:30:00Z",
            "by": "retry",
        }
    )
    assert track_record.rework_count(task) == 1


def test_clean_merge_ignores_failed_test_run_record(tmp_path):
    """A failed test_run record does not disqualify an otherwise clean merge."""
    task = _make_task(tmp_path, "t-1")
    _write_verdicts(tmp_path / "reports", "demo/project", "t-1", ["qa", "review", "cso", "sync-docs"])
    _write_records(
        tmp_path,
        "t-1",
        [_test_run_record("t-1", "implement", exit_code=1)],
    )
    assert track_record.is_clean_merge(
        task,
        archive_dir=tmp_path / "telemetry",
        reports_dir=tmp_path / "reports",
        project_slug="demo/project",
    )


def test_clean_merge_still_fails_on_failed_stage_record(tmp_path):
    """A failed stage record still disqualifies a clean merge."""
    task = _make_task(tmp_path, "t-1")
    _write_verdicts(tmp_path / "reports", "demo/project", "t-1", ["qa", "review", "cso", "sync-docs"])
    _write_records(
        tmp_path,
        "t-1",
        [_stage_record("t-1", "implement", exit_code=1)],
    )
    assert not track_record.is_clean_merge(
        task,
        archive_dir=tmp_path / "telemetry",
        reports_dir=tmp_path / "reports",
        project_slug="demo/project",
    )


def test_clean_merge_ignores_failed_test_run_of_either_provenance(tmp_path):
    """Failed observed and claimed test_run records are both ignored."""
    task = _make_task(tmp_path, "t-1")
    _write_verdicts(tmp_path / "reports", "demo/project", "t-1", ["qa", "review", "cso", "sync-docs"])
    _write_records(
        tmp_path,
        "t-1",
        [
            _test_run_record("t-1", "implement", exit_code=1, source="wire"),
            _test_run_record("t-1", "implement", exit_code=0, source="verdict"),
        ],
    )
    assert track_record.is_clean_merge(
        task,
        archive_dir=tmp_path / "telemetry",
        reports_dir=tmp_path / "reports",
        project_slug="demo/project",
    )
