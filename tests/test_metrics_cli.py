"""Tests for the `aet metrics` CLI surface (aet-work/bin/metrics)."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "aet-work" / "lib"))

import metrics

# Load the metrics CLI script (no .py extension) as a module. The loader name
# must not collide with the lib `metrics` module the CLI imports.
_METRICS_BIN = Path(__file__).parent.parent / "aet-work" / "bin" / "metrics"
_metrics_loader = importlib.machinery.SourceFileLoader(
    "metrics_cli", str(_METRICS_BIN)
)
_spec = importlib.util.spec_from_loader("metrics_cli", _metrics_loader)
metrics_cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(metrics_cli)

# Load the multicall dispatcher (no .py extension) for the registration test.
_AET_BIN = Path(__file__).parent.parent / "aet-work" / "bin" / "aet"
_aet_loader = importlib.machinery.SourceFileLoader("aet_dispatcher", str(_AET_BIN))
_aet_spec = importlib.util.spec_from_loader("aet_dispatcher", _aet_loader)
aet_dispatcher = importlib.util.module_from_spec(_aet_spec)
_aet_spec.loader.exec_module(aet_dispatcher)


def _write_history(path: Path, tasks: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for task in tasks:
            f.write(json.dumps(task) + "\n")


def _run_cli(monkeypatch, argv: list[str]) -> int:
    monkeypatch.setattr(sys, "argv", ["metrics", *argv])
    return metrics_cli.main()


class TestCliJsonProjection:
    """--json prints the aggregate projection verbatim to stdout."""

    def test_cli_json_projection_matches_aggregate_shape(
        self, tmp_path, capsys, monkeypatch
    ):
        history = tmp_path / "history.jsonl"
        _write_history(
            history,
            [
                {
                    "id": "t1",
                    "state": "merged",
                    "work_class": "normal",
                    "settled_at": "2026-07-15T00:00:00Z",
                },
                {
                    "id": "t2",
                    "state": "abandoned",
                    "work_class": "critical",
                    "settled_at": "2026-07-16T00:00:00Z",
                },
            ],
        )

        rc = _run_cli(monkeypatch, ["--json", "--history-file", str(history)])

        assert rc == 0
        projection = json.loads(capsys.readouterr().out)
        assert projection == metrics.aggregate(str(history))


class TestCliHumanReport:
    """The default output is a sectioned human report."""

    def test_cli_human_report_shows_three_metric_sections_and_classes(
        self, tmp_path, capsys, monkeypatch
    ):
        history = tmp_path / "history.jsonl"
        _write_history(
            history,
            [
                {
                    "id": "t1",
                    "state": "merged",
                    "work_class": "normal",
                    "settled_at": "2026-07-15T00:00:00Z",
                },
                {
                    "id": "t2",
                    "state": "abandoned",
                    "work_class": "critical",
                    "settled_at": "2026-07-16T00:00:00Z",
                },
            ],
        )

        rc = _run_cli(monkeypatch, ["--history-file", str(history)])

        assert rc == 0
        out = capsys.readouterr().out
        assert "First-pass merge rate" in out
        assert "Rework" in out
        assert "Cost per merged task" in out
        assert "overall" in out
        assert "normal" in out
        assert "critical" in out
        # Null metrics (no telemetry in the isolated archive) render as "-"
        assert "-" in out


class TestCliNoSettledTasks:
    """An empty or missing history is a valid state, not an error."""

    def test_cli_no_settled_tasks_prints_no_data_rc0(
        self, tmp_path, capsys, monkeypatch
    ):
        history = tmp_path / "missing.jsonl"

        rc = _run_cli(monkeypatch, ["--history-file", str(history)])

        assert rc == 0
        out = capsys.readouterr().out
        assert "No settled tasks found" in out

    def test_cli_no_settled_tasks_json_is_zeroed_projection_rc0(
        self, tmp_path, capsys, monkeypatch
    ):
        history = tmp_path / "missing.jsonl"

        rc = _run_cli(monkeypatch, ["--json", "--history-file", str(history)])

        assert rc == 0
        projection = json.loads(capsys.readouterr().out)
        assert projection["overall"]["settled"] == 0
        assert projection["classes"] == {}


class TestCliSinceWindow:
    """--since restricts the aggregation window."""

    def test_cli_since_filters_window(self, tmp_path, capsys, monkeypatch):
        history = tmp_path / "history.jsonl"
        _write_history(
            history,
            [
                {
                    "id": "old",
                    "state": "merged",
                    "work_class": "normal",
                    "settled_at": "2026-01-01T00:00:00Z",
                },
                {
                    "id": "new",
                    "state": "merged",
                    "work_class": "normal",
                    "settled_at": "2026-07-15T00:00:00Z",
                },
            ],
        )

        rc = _run_cli(
            monkeypatch,
            ["--json", "--history-file", str(history), "--since", "2026-07-01"],
        )

        assert rc == 0
        projection = json.loads(capsys.readouterr().out)
        assert projection["since"] == "2026-07-01"
        assert projection["overall"]["settled"] == 1
        assert projection["overall"]["merged"] == 1


class TestCliInvalidSince:
    """A malformed --since is the only rc 1 path."""

    def test_cli_invalid_since_exits_1_with_stderr(
        self, tmp_path, capsys, monkeypatch
    ):
        history = tmp_path / "history.jsonl"
        _write_history(history, [])

        rc = _run_cli(
            monkeypatch,
            ["--history-file", str(history), "--since", "July 2026"],
        )

        assert rc == 1
        captured = capsys.readouterr()
        assert "⛔" in captured.err
        assert captured.out == ""


class TestCliRegisteredInDispatcher:
    """`aet metrics` dispatches to aet-work/bin/metrics."""

    def test_cli_registered_in_dispatcher(self, monkeypatch):
        captured = {}

        def mock_execvp(path, exec_argv):
            captured["path"] = path
            captured["argv"] = exec_argv
            raise SystemExit(0)

        monkeypatch.setattr(sys, "argv", ["aet", "metrics", "--json"])
        monkeypatch.setattr(aet_dispatcher.os, "execvp", mock_execvp)
        rc = aet_dispatcher.main()

        repo_root = Path(__file__).parent.parent
        assert rc == 0
        assert Path(captured["path"]) == repo_root / "aet-work" / "bin" / "metrics"
        assert captured["argv"] == ["metrics", "--json"]
