"""Tests for the metrics aggregation core."""

from __future__ import annotations

import json
from pathlib import Path

import metrics


def _write_history(path: Path, tasks: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for task in tasks:
            f.write(json.dumps(task) + "\n")


def _write_telemetry(
    archive: Path,
    project_slug: str,
    task_id: str,
    records: list[dict],
    date: str = "2026-07-19",
    run_id: str = "run-1",
) -> None:
    run_dir = archive / project_slug / date / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    with open(run_dir / f"{task_id}.jsonl", "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")


def _write_verdicts(reports: Path, project_slug: str, task_id: str) -> None:
    task_dir = reports / project_slug / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    for kind in ("qa", "review", "cso", "sync-docs"):
        (task_dir / f"{kind}.json").write_text(json.dumps({"verdict": "pass"}), encoding="utf-8")


class TestIterSettledTasks:
    """Window filtering over the settled history log."""

    def test_iter_settled_tasks_since_window_filters_on_settled_at(self, tmp_path):
        history = tmp_path / "history.jsonl"
        _write_history(
            history,
            [
                {"id": "old-1", "settled_at": "2026-01-01T00:00:00Z"},
                {"id": "new-1", "settled_at": "2026-07-15T00:00:00Z"},
                {"id": "new-2", "settled_at": "2026-07-20T00:00:00Z"},
            ],
        )

        result = metrics.iter_settled_tasks(str(history), since="2026-07-10")

        assert [t["id"] for t in result] == ["new-1", "new-2"]

    def test_iter_settled_tasks_legacy_fallback_completed_at(self, tmp_path):
        history = tmp_path / "history.jsonl"
        _write_history(
            history,
            [
                {
                    "id": "legacy-completed",
                    "completed_at": "2026-07-12T00:00:00Z",
                },
                {
                    "id": "legacy-merged",
                    "merged_at": "2026-07-18T00:00:00Z",
                },
                {
                    "id": "legacy-settled-wins",
                    "settled_at": "2026-07-14T00:00:00Z",
                    "completed_at": "2026-07-13T00:00:00Z",
                },
            ],
        )

        result = metrics.iter_settled_tasks(str(history), since="2026-07-15")

        assert [t["id"] for t in result] == ["legacy-merged"]

    def test_iter_settled_tasks_no_timestamp_included_only_without_since(self, tmp_path):
        history = tmp_path / "history.jsonl"
        _write_history(
            history,
            [
                {"id": "dated", "settled_at": "2026-07-15T00:00:00Z"},
                {"id": "undated"},
            ],
        )

        assert [t["id"] for t in metrics.iter_settled_tasks(str(history))] == [
            "dated",
            "undated",
        ]
        assert [t["id"] for t in metrics.iter_settled_tasks(str(history), since="2026-01-01")] == ["dated"]


class TestTaskCost:
    """Cross-run, null-honest cost aggregation."""

    def test_task_cost_sums_stage_records_across_runs(self, tmp_path):
        archive = tmp_path / "telemetry"
        project = "test/project"
        task_id = "task-cross-run"
        _write_telemetry(
            archive,
            project,
            task_id,
            [
                {"type": "stage", "stage": "implement", "token_count": 100, "cost_estimate": 0.5},
                {"type": "stage", "stage": "qa", "token_count": 50, "cost_estimate": 0.25},
            ],
            run_id="run-a",
        )
        _write_telemetry(
            archive,
            project,
            task_id,
            [
                {"type": "stage", "stage": "review", "token_count": 75, "cost_estimate": 0.35},
            ],
            run_id="run-b",
        )

        result = metrics.task_cost(
            task_id,
            archive_dir=str(archive),
            project_slug=project,
        )

        assert result == {"tokens": 225, "usd": 1.1}

    def test_task_cost_all_null_usd_returns_none(self, tmp_path):
        archive = tmp_path / "telemetry"
        project = "test/project"
        task_id = "task-null-cost"
        _write_telemetry(
            archive,
            project,
            task_id,
            [
                {"type": "stage", "stage": "implement", "token_count": 100, "cost_estimate": None},
                {"type": "stage", "stage": "qa", "token_count": None, "cost_estimate": None},
            ],
        )

        result = metrics.task_cost(
            task_id,
            archive_dir=str(archive),
            project_slug=project,
        )

        assert result == {"tokens": 100, "usd": None}

    def test_task_cost_no_records_returns_none(self, tmp_path):
        archive = tmp_path / "telemetry"
        project = "test/project"

        result = metrics.task_cost(
            "missing-task",
            archive_dir=str(archive),
            project_slug=project,
        )

        assert result == {"tokens": None, "usd": None}


class TestAggregate:
    """Canonical projection over settled tasks."""

    def test_aggregate_first_pass_rate_per_class_and_overall(self, tmp_path):
        archive = tmp_path / "telemetry"
        reports = tmp_path / "reports"
        project = "test/project"
        history = tmp_path / "history.jsonl"

        _write_verdicts(reports, project, "clean")
        _write_verdicts(reports, project, "rework")
        _write_telemetry(
            archive,
            project,
            "clean",
            [
                {"type": "stage", "stage": "implement", "token_count": 10, "cost_estimate": 0.1},
                {"type": "stage", "stage": "qa", "token_count": 10, "cost_estimate": 0.1},
            ],
        )
        _write_telemetry(
            archive,
            project,
            "rework",
            [
                {"type": "stage", "stage": "implement", "token_count": 10, "cost_estimate": 0.1},
                {"type": "stage", "stage": "implement", "token_count": 10, "cost_estimate": 0.1},
                {"type": "stage", "stage": "qa", "token_count": 10, "cost_estimate": 0.1},
            ],
        )
        _write_history(
            history,
            [
                {"id": "clean", "state": "merged", "work_class": "normal", "settled_at": "2026-07-15T00:00:00Z"},
                {"id": "rework", "state": "merged", "work_class": "normal", "settled_at": "2026-07-15T00:00:00Z"},
                {"id": "open", "state": "ready", "work_class": "normal", "settled_at": "2026-07-15T00:00:00Z"},
            ],
        )

        result = metrics.aggregate(
            str(history),
            archive_dir=str(archive),
            project_slug=project,
            reports_dir=str(reports),
        )

        overall = result["overall"]
        assert overall["settled"] == 3
        assert overall["merged"] == 2
        assert overall["first_pass"] == 1
        assert overall["first_pass_rate"] == 0.5
        assert result["classes"]["normal"]["first_pass_rate"] == 0.5

    def test_aggregate_rework_totals(self, tmp_path):
        archive = tmp_path / "telemetry"
        reports = tmp_path / "reports"
        project = "test/project"
        history = tmp_path / "history.jsonl"

        _write_verdicts(reports, project, "a")
        _write_telemetry(
            archive,
            project,
            "a",
            [
                {"type": "stage", "stage": "implement", "token_count": 10, "cost_estimate": 0.1},
                {"type": "stage", "stage": "implement", "token_count": 10, "cost_estimate": 0.1},
            ],
        )
        _write_history(
            history,
            [
                {
                    "id": "a",
                    "state": "merged",
                    "work_class": "normal",
                    "settled_at": "2026-07-15T00:00:00Z",
                    "history": [{"from": "failed", "to": "ready"}],
                },
            ],
        )

        result = metrics.aggregate(
            str(history),
            archive_dir=str(archive),
            project_slug=project,
            reports_dir=str(reports),
        )

        # Repeated implement stage (1) + failed->ready history entry (1)
        assert result["overall"]["rework"] == 2
        assert result["classes"]["normal"]["rework"] == 2

    def test_aggregate_cost_averages_and_usd_coverage_count(self, tmp_path):
        archive = tmp_path / "telemetry"
        reports = tmp_path / "reports"
        project = "test/project"
        history = tmp_path / "history.jsonl"

        for task_id in ("known", "unknown-usd"):
            _write_verdicts(reports, project, task_id)
        _write_telemetry(
            archive,
            project,
            "known",
            [
                {"type": "stage", "stage": "implement", "token_count": 100, "cost_estimate": 0.5},
            ],
        )
        _write_telemetry(
            archive,
            project,
            "unknown-usd",
            [
                {"type": "stage", "stage": "implement", "token_count": 200, "cost_estimate": None},
            ],
        )
        _write_history(
            history,
            [
                {"id": "known", "state": "merged", "work_class": "normal", "settled_at": "2026-07-15T00:00:00Z"},
                {"id": "unknown-usd", "state": "merged", "work_class": "normal", "settled_at": "2026-07-15T00:00:00Z"},
            ],
        )

        result = metrics.aggregate(
            str(history),
            archive_dir=str(archive),
            project_slug=project,
            reports_dir=str(reports),
        )

        cost = result["overall"]["cost"]
        assert cost["tokens_total"] == 300
        assert cost["tokens_avg_per_merged"] == 150.0
        assert cost["usd_total"] == 0.5
        assert cost["usd_avg_per_merged"] == 0.25
        assert cost["usd_known_tasks"] == 1

    def test_aggregate_empty_history_returns_zeroed_projection(self, tmp_path):
        history = tmp_path / "history.jsonl"
        _write_history(history, [])

        result = metrics.aggregate(str(history))

        assert result["since"] is None
        overall = result["overall"]
        assert overall["settled"] == 0
        assert overall["merged"] == 0
        assert overall["first_pass"] == 0
        assert overall["first_pass_rate"] is None
        assert overall["rework"] == 0
        assert overall["cost"]["tokens_total"] is None
        assert overall["cost"]["tokens_avg_per_merged"] is None
        assert overall["cost"]["usd_total"] is None
        assert overall["cost"]["usd_avg_per_merged"] is None
        assert overall["cost"]["usd_known_tasks"] == 0
        assert result["classes"] == {}

    def test_aggregate_unknown_work_class_gets_own_bucket(self, tmp_path):
        archive = tmp_path / "telemetry"
        reports = tmp_path / "reports"
        project = "test/project"
        history = tmp_path / "history.jsonl"

        for task_id in ("normal-task", "weird-task"):
            _write_verdicts(reports, project, task_id)
        for task_id in ("normal-task", "weird-task"):
            _write_telemetry(
                archive,
                project,
                task_id,
                [{"type": "stage", "stage": "implement", "token_count": 10, "cost_estimate": 0.1}],
            )
        _write_history(
            history,
            [
                {"id": "normal-task", "state": "merged", "work_class": "normal", "settled_at": "2026-07-15T00:00:00Z"},
                {"id": "weird-task", "state": "merged", "work_class": "weird", "settled_at": "2026-07-15T00:00:00Z"},
            ],
        )

        result = metrics.aggregate(
            str(history),
            archive_dir=str(archive),
            project_slug=project,
            reports_dir=str(reports),
        )

        assert set(result["classes"].keys()) == {"normal", "weird"}
        assert result["classes"]["weird"]["merged"] == 1
