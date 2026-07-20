"""Tests for routing-aware clean-merge definitions and rework counting."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
from aet import (  # noqa: E402
    plan_parser,
    project_id,
    telemetry,
    track_record,
)

REPO_ROOT = Path(__file__).parent.parent
_DESK_PY = REPO_ROOT / "src" / "aet" / "cli" / "desk.py"

_desk_spec = importlib.util.spec_from_loader(
    "desk_bin", importlib.machinery.SourceFileLoader("desk_bin", str(_DESK_PY))
)
desk = importlib.util.module_from_spec(_desk_spec)
_desk_spec.loader.exec_module(desk)


def test_required_verdict_kinds_defaults_to_all_four():
    """A plan with no routing keys requires all four gate verdicts."""
    assert plan_parser.required_verdict_kinds({}) == ["qa", "review", "cso", "sync-docs"]


def test_required_verdict_kinds_excludes_skipped_gates():
    """A plan that skips a gated gate drops the corresponding verdict kind."""
    plan_data = {"security_review": "skipped", "docs_sync": "required"}
    assert plan_parser.required_verdict_kinds(plan_data) == ["qa", "review", "sync-docs"]


def _make_task(tmp_path: Path, task_id: str, plan_text: str) -> dict:
    plan_file = tmp_path / "plans" / f"{task_id}.md"
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text(plan_text, encoding="utf-8")
    return {
        "id": task_id,
        "state": "merged",
        "work_class": "trivial",
        "plan_file": str(plan_file),
        "history": [
            {"from": None, "to": "planned", "at": "2026-07-09T10:00:00Z", "by": "add"},
            {"from": "planned", "to": "in_progress", "at": "2026-07-09T11:00:00Z", "by": "orchestrator"},
            {"from": "in_progress", "to": "awaiting_merge", "at": "2026-07-09T12:00:00Z", "by": "orchestrator"},
            {"from": "awaiting_merge", "to": "merged", "at": "2026-07-09T13:00:00Z", "by": "record-merge"},
        ],
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
            record.update({"test_command": "pytest", "tests_total": 10, "tests_passed": 10, "tests_failed": 0})
        elif kind == "sync-docs":
            record["divergences"] = []
        else:
            record["findings"] = []
        (base / f"{kind}.json").write_text(json.dumps(record), encoding="utf-8")


@pytest.fixture(autouse=True)
def _isolate_reports_dir(monkeypatch, tmp_path):
    """Point evidence and telemetry archives at per-test tmp dirs."""
    monkeypatch.setenv("AET_REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("AET_TELEMETRY_ARCHIVE_DIR", str(tmp_path / "telemetry"))


def test_is_clean_merge_clean_when_routed_away_gate_verdict_absent(tmp_path):
    """A skipped gate's missing verdict does not disqualify a clean merge."""
    task = _make_task(
        tmp_path,
        "t-1",
        "---\nid: t-1\nsecurity_review: skipped\nsecurity_review_reason: low risk\n---\n\n# T-1\n",
    )
    _write_verdicts(tmp_path / "reports", "demo/project", "t-1", ["qa", "review", "sync-docs"])
    assert track_record.is_clean_merge(
        task,
        archive_dir=tmp_path / "telemetry",
        reports_dir=tmp_path / "reports",
        project_slug="demo/project",
    )


def test_is_clean_merge_still_requires_non_skipped_gates(tmp_path):
    """A non-skipped gate's missing verdict still disqualifies the merge."""
    task = _make_task(
        tmp_path,
        "t-1",
        "---\nid: t-1\nsecurity_review: skipped\nsecurity_review_reason: low risk\n---\n\n# T-1\n",
    )
    # sync-docs is required by default, but we only provide qa + review.
    _write_verdicts(tmp_path / "reports", "demo/project", "t-1", ["qa", "review"])
    assert not track_record.is_clean_merge(
        task,
        archive_dir=tmp_path / "telemetry",
        reports_dir=tmp_path / "reports",
        project_slug="demo/project",
    )


def test_is_clean_merge_missing_plan_file_fails_safe_to_all_four(tmp_path):
    """A legacy task with no readable plan file falls back to requiring all four verdicts."""
    plan_file = tmp_path / "plans" / "legacy.md"
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    # Do not create the file.
    task = {
        "id": "legacy",
        "state": "merged",
        "work_class": "trivial",
        "plan_file": str(plan_file),
        "history": [],
    }
    _write_verdicts(tmp_path / "reports", "demo/project", "legacy", ["qa", "review", "cso", "sync-docs"])
    assert track_record.is_clean_merge(
        task,
        archive_dir=tmp_path / "telemetry",
        reports_dir=tmp_path / "reports",
        project_slug="demo/project",
    )


def _stage_record(task_id: str, stage: str, exit_code: int = 0) -> dict:
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


def test_rework_count_zero_for_single_pass_task(tmp_path):
    """A single clean pass has no rework."""
    task = _make_task(tmp_path, "t-1", "---\nid: t-1\n---\n\n# T-1\n")
    assert track_record.rework_count(task) == 0


def test_rework_count_repeated_stage_records(tmp_path):
    """Repeated stage/test_run records beyond the first per stage count as rework."""
    task = _make_task(tmp_path, "t-1", "---\nid: t-1\n---\n\n# T-1\n")
    run_dir = tmp_path / "telemetry" / "demo" / "project" / "2026-07-09" / "run-1"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "t-1.jsonl").write_text(
        json.dumps(_stage_record("t-1", "implement")) + "\n" +
        json.dumps(_stage_record("t-1", "implement")) + "\n" +
        json.dumps(_stage_record("t-1", "qa")) + "\n",
        encoding="utf-8",
    )
    assert track_record.rework_count(
        task,
        archive_dir=tmp_path / "telemetry",
        project_slug="demo/project",
    ) == 1


def test_rework_count_failed_reentry_transitions(tmp_path):
    """History transitions from 'failed' count as rework."""
    task = _make_task(tmp_path, "t-1", "---\nid: t-1\n---\n\n# T-1\n")
    task["history"].insert(
        1,
        {"from": "failed", "to": "in_progress", "at": "2026-07-09T10:30:00Z", "by": "retry"},
    )
    assert track_record.rework_count(task) == 1


def _write_history(tmp_path: Path, tasks: list[dict]) -> str:
    path = tmp_path / "work-history.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for task in tasks:
            f.write(json.dumps(task) + "\n")
    return str(path)


def test_desk_eligibility_matches_shared_definition(tmp_path, monkeypatch):
    """Desk --eligibility uses the same routing-aware clean-merge predicate."""
    monkeypatch.setenv("AET_PROJECT_ID", "demo/project")
    project_slug = project_id.derive_project_slug()

    plan_text = (
        "---\n"
        "id: t-1\n"
        "security_review: skipped\n"
        "security_review_reason: low risk\n"
        "---\n\n# T-1\n"
    )
    task = _make_task(tmp_path, "t-1", plan_text)
    history_file = _write_history(tmp_path, [task])
    _write_verdicts(tmp_path / "reports", project_slug, "t-1", ["qa", "review", "sync-docs"])

    policy = {"enabled_classes": {"trivial": True}, "thresholds": {"trivial": 1}}
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")

    shared = track_record.class_eligibility(
        "trivial",
        policy=policy,
        history_file=history_file,
        reports_dir=tmp_path / "reports",
        archive_dir=tmp_path / "telemetry",
        project_slug=project_slug,
    )

    argv = [
        "desk",
        "--eligibility",
        "--json",
        "--history-file", history_file,
        "--policy", str(policy_path),
    ]
    stdout = io.StringIO()
    with patch_argv(argv), redirect_stdout(stdout):
        assert desk.main() == 0
    projection = json.loads(stdout.getvalue())

    assert projection["trivial"]["count"] == shared["count"] == 1


class patch_argv:
    """Simple context manager to patch sys.argv for the desk binary."""

    def __init__(self, argv: list[str]):
        self.argv = argv

    def __enter__(self):
        self._orig = sys.argv
        sys.argv = self.argv
        return self

    def __exit__(self, *exc):
        sys.argv = self._orig
        return False
