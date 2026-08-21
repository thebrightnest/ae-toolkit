"""Tests for the `aet size` CLI surface (src/aet/cli/size.py)."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

# Load the size CLI script as a module. The loader name must not collide with
# the lib `metrics` module the CLI imports.
_SIZE_BIN = Path(__file__).parents[2] / "src" / "aet" / "cli" / "size.py"
_size_loader = importlib.machinery.SourceFileLoader("size_cli", str(_SIZE_BIN))
_size_spec = importlib.util.spec_from_loader("size_cli", _size_loader)
size_cli = importlib.util.module_from_spec(_size_spec)
_size_spec.loader.exec_module(size_cli)

# Load the multicall dispatcher for the registration test.
_AET_BIN = Path(__file__).parents[2] / "src" / "aet" / "cli" / "main.py"
_aet_loader = importlib.machinery.SourceFileLoader("aet_dispatcher", str(_AET_BIN))
_aet_spec = importlib.util.spec_from_loader("aet_dispatcher", _aet_loader)
aet_dispatcher = importlib.util.module_from_spec(_aet_spec)
_aet_spec.loader.exec_module(aet_dispatcher)


def _write_history(path: Path, tasks: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for task in tasks:
            f.write(json.dumps(task) + "\n")


def _init_repo(repo_root: str) -> None:
    subprocess.run(["git", "init", "-q", repo_root], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "config", "user.name", "Test User"],
        check=True,
    )
    Path(repo_root, "README.md").write_text("# test\n", encoding="utf-8")
    subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "commit", "-q", "-m", "initial"],
        check=True,
    )
    subprocess.run(["git", "-C", repo_root, "branch", "-M", "main"], check=True)


def _commit(repo_root: str, path: str, content: str, message: str) -> None:
    target = Path(repo_root, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", repo_root, "add", path], check=True)
    subprocess.run(
        ["git", "-C", repo_root, "commit", "-q", "-m", message],
        check=True,
    )


def _make_merge_commit(repo_root: str, feature_path: str, content: str) -> str:
    subprocess.run(
        ["git", "-C", repo_root, "checkout", "-b", "feature"],
        check=True,
        capture_output=True,
    )
    _commit(repo_root, feature_path, content, "feature commit")
    subprocess.run(
        ["git", "-C", repo_root, "checkout", "main"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "merge", "--squash", "feature"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", repo_root, "commit", "-q", "-m", "merge feature"],
        check=True,
        capture_output=True,
    )
    result = subprocess.run(
        ["git", "-C", repo_root, "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _make_plan_file(repo_root: str, plan_path: str, size: str) -> None:
    path = Path(repo_root, plan_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nid: test-task\nsize: {size}\n---\n\n# Test plan\n",
        encoding="utf-8",
    )


def _spec(size: str) -> dict:
    """Build a portable spec with the given declared size."""
    return {"frontmatter": {"size": size}, "title": "Test plan", "body": "", "tasks": []}


def _run_size_cli(monkeypatch, argv: list[str]) -> int:
    monkeypatch.setattr(sys, "argv", ["size", *argv])
    return size_cli.main()


class TestSizeReportCli:
    """`aet size report` renders delivered-size aggregates."""

    def test_report_json_matches_aggregate_projection(
        self, tmp_path, capsys, monkeypatch
    ):
        history = tmp_path / "history.jsonl"
        _write_history(
            history,
            [
                {
                    "id": "s1",
                    "settled_at": "2026-07-15T00:00:00Z",
                    "delivered_size": {"headline": 100, "status": "ok", "declared_size": "S"},
                },
                {
                    "id": "m1",
                    "settled_at": "2026-07-15T00:00:00Z",
                    "delivered_size": {"headline": 400, "status": "ok", "declared_size": "M"},
                },
            ],
        )

        rc = _run_size_cli(monkeypatch, ["report", "--json", "--history-file", str(history)])

        assert rc == 0
        projection = json.loads(capsys.readouterr().out)
        assert projection["sample_size"] == 2
        assert projection["labels"]["S"]["n"] == 1
        assert projection["labels"]["M"]["n"] == 1

    def test_report_human_shows_labels_and_sample_size(
        self, tmp_path, capsys, monkeypatch
    ):
        history = tmp_path / "history.jsonl"
        _write_history(
            history,
            [
                {
                    "id": "s1",
                    "settled_at": "2026-07-15T00:00:00Z",
                    "delivered_size": {"headline": 100, "status": "ok", "declared_size": "S"},
                },
            ],
        )

        rc = _run_size_cli(monkeypatch, ["report", "--history-file", str(history)])

        assert rc == 0
        out = capsys.readouterr().out
        assert "S" in out
        assert "sample size" in out.lower()

    def test_report_since_filters_window(self, tmp_path, capsys, monkeypatch):
        history = tmp_path / "history.jsonl"
        _write_history(
            history,
            [
                {
                    "id": "old",
                    "settled_at": "2026-01-01T00:00:00Z",
                    "delivered_size": {"headline": 100, "status": "ok", "declared_size": "S"},
                },
                {
                    "id": "new",
                    "settled_at": "2026-07-15T00:00:00Z",
                    "delivered_size": {"headline": 200, "status": "ok", "declared_size": "S"},
                },
            ],
        )

        rc = _run_size_cli(
            monkeypatch,
            ["report", "--json", "--history-file", str(history), "--since", "2026-07-01"],
        )

        assert rc == 0
        projection = json.loads(capsys.readouterr().out)
        assert projection["since"] == "2026-07-01"
        assert projection["sample_size"] == 1
        assert projection["labels"]["S"]["median"] == 200


class TestSizeBackfillCli:
    """`aet size backfill` measures missing delivered_size records."""

    def test_backfill_human_reports_measured_skipped_unresolvable(
        self, tmp_path, capsys, monkeypatch
    ):
        repo_root = str(tmp_path / "repo")
        history = tmp_path / "history.jsonl"
        _init_repo(repo_root)
        merge_commit = _make_merge_commit(repo_root, "src/feature.py", "a\nb\nc\n")
        _make_plan_file(repo_root, "docs/plans/test-task.md", "S")
        _write_history(
            history,
            [
                {
                    "id": "test-task",
                    "settled_at": "2026-07-15T00:00:00Z",
                    "merge_commit": merge_commit,
                    "plan_file": "docs/plans/test-task.md",
                    "spec": _spec("S"),
                },
            ],
        )

        rc = _run_size_cli(
            monkeypatch,
            ["backfill", "--history-file", str(history), "--repo-root", repo_root],
        )

        assert rc == 0
        out = capsys.readouterr().out
        assert "measured" in out.lower()
        assert "skipped" in out.lower()
        assert "unresolvable" in out.lower()

    def test_backfill_json_reports_counts(self, tmp_path, capsys, monkeypatch):
        repo_root = str(tmp_path / "repo")
        history = tmp_path / "history.jsonl"
        _init_repo(repo_root)
        merge_commit = _make_merge_commit(repo_root, "src/feature.py", "a\nb\n")
        _make_plan_file(repo_root, "docs/plans/test-task.md", "S")
        _write_history(
            history,
            [
                {
                    "id": "test-task",
                    "settled_at": "2026-07-15T00:00:00Z",
                    "merge_commit": merge_commit,
                    "plan_file": "docs/plans/test-task.md",
                    "spec": _spec("S"),
                },
            ],
        )

        rc = _run_size_cli(
            monkeypatch,
            ["backfill", "--json", "--history-file", str(history), "--repo-root", repo_root],
        )

        assert rc == 0
        result = json.loads(capsys.readouterr().out)
        assert result["measured"] == 1
        assert result["skipped"] == 0
        assert result["unresolvable"] == 0

    def test_backfill_min_yield_fails_when_not_met(self, tmp_path, capsys, monkeypatch):
        repo_root = str(tmp_path / "repo")
        history = tmp_path / "history.jsonl"
        _init_repo(repo_root)
        _write_history(history, [])

        rc = _run_size_cli(
            monkeypatch,
            [
                "backfill",
                "--history-file",
                str(history),
                "--repo-root",
                repo_root,
                "--min-yield",
                "1",
            ],
        )

        assert rc == 1
        assert "yield" in capsys.readouterr().err.lower()


class TestSizeCliRegisteredInDispatcher:
    """`aet size` is registered in the consolidated Typer app."""

    def test_size_group_registered(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["aet", "size", "--help"])
        rc = aet_dispatcher.main()
        assert rc == 0
