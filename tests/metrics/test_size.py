"""Tests for delivered-size aggregation and backfill."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from aet import metrics

_SIZE_BANDS = {"S": 150, "M": 600, "L": None}


def _ds(headline: int | None, status: str, declared_size: str | None) -> dict:
    return {"headline": headline, "status": status, "declared_size": declared_size}


def _write_history(path: Path, tasks: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for task in tasks:
            f.write(json.dumps(task) + "\n")


def _read_history(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _init_repo(repo_root: str) -> None:
    """Initialize a git repo with a clean main branch."""
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
    """Create a feature branch with one code commit and squash-merge it to main."""
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


class TestAggregateDeliveredSize:
    """Delivered-size distribution grouped by declared label."""

    def test_aggregate_computes_median_p90_and_share_exceeding_band(self, tmp_path):
        history = tmp_path / "history.jsonl"
        _write_history(
            history,
            [
                {"id": "s1", "settled_at": "2026-07-15T00:00:00Z", "delivered_size": _ds(50, "ok", "S")},
                {"id": "s2", "settled_at": "2026-07-15T00:00:00Z", "delivered_size": _ds(100, "ok", "S")},
                {"id": "s3", "settled_at": "2026-07-15T00:00:00Z", "delivered_size": _ds(200, "ok", "S")},
                {"id": "s4", "settled_at": "2026-07-15T00:00:00Z", "delivered_size": _ds(300, "ok", "S")},
            ],
        )

        result = metrics.aggregate_delivered_size(str(history))

        s = result["labels"]["S"]
        assert s["n"] == 4
        assert s["median"] == 150
        assert s["p90"] == 300
        assert s["exceeds_band"] == 0.5

    def test_aggregate_groups_by_declared_size(self, tmp_path):
        history = tmp_path / "history.jsonl"
        _write_history(
            history,
            [
                {"id": "s1", "settled_at": "2026-07-15T00:00:00Z", "delivered_size": _ds(100, "ok", "S")},
                {"id": "m1", "settled_at": "2026-07-15T00:00:00Z", "delivered_size": _ds(500, "ok", "M")},
                {"id": "l1", "settled_at": "2026-07-15T00:00:00Z", "delivered_size": _ds(700, "ok", "L")},
            ],
        )

        result = metrics.aggregate_delivered_size(str(history))

        assert result["sample_size"] == 3
        assert result["labels"]["S"]["n"] == 1
        assert result["labels"]["M"]["n"] == 1
        assert result["labels"]["L"]["n"] == 1
        assert result["labels"]["S"]["exceeds_band"] == 0.0
        assert result["labels"]["M"]["exceeds_band"] == 0.0
        assert result["labels"]["L"]["exceeds_band"] == 0.0

    def test_aggregate_excludes_unmeasured_and_failed_records(self, tmp_path):
        history = tmp_path / "history.jsonl"
        _write_history(
            history,
            [
                {"id": "ok", "settled_at": "2026-07-15T00:00:00Z", "delivered_size": _ds(100, "ok", "S")},
                {"id": "missing", "settled_at": "2026-07-15T00:00:00Z"},
                {"id": "failed", "settled_at": "2026-07-15T00:00:00Z", "delivered_size": _ds(None, "failed", "S")},
                {"id": "no_label", "settled_at": "2026-07-15T00:00:00Z", "delivered_size": _ds(100, "ok", None)},
            ],
        )

        result = metrics.aggregate_delivered_size(str(history))

        assert result["sample_size"] == 1
        assert result["labels"]["S"]["n"] == 1

    def test_aggregate_empty_history(self, tmp_path):
        history = tmp_path / "history.jsonl"
        _write_history(history, [])

        result = metrics.aggregate_delivered_size(str(history))

        assert result["since"] is None
        assert result["sample_size"] == 0
        for label in ("S", "M", "L"):
            assert result["labels"][label]["n"] == 0
            assert result["labels"][label]["median"] is None
            assert result["labels"][label]["p90"] is None
            assert result["labels"][label]["exceeds_band"] is None

    def test_aggregate_respects_since_window(self, tmp_path):
        history = tmp_path / "history.jsonl"
        _write_history(
            history,
            [
                {"id": "old", "settled_at": "2026-01-01T00:00:00Z", "delivered_size": _ds(100, "ok", "S")},
                {"id": "new", "settled_at": "2026-07-15T00:00:00Z", "delivered_size": _ds(200, "ok", "S")},
            ],
        )

        result = metrics.aggregate_delivered_size(str(history), since="2026-07-01")

        assert result["sample_size"] == 1
        assert result["labels"]["S"]["n"] == 1
        assert result["labels"]["S"]["median"] == 200


class TestBackfillDeliveredSize:
    """Idempotent backfill of delivered_size onto settled history records."""

    def test_backfill_measures_missing_records(self, tmp_path):
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
                },
            ],
        )

        result = metrics.backfill_delivered_size(str(history), repo_root)

        assert result["measured"] == 1
        assert result["skipped"] == 0
        assert result["unresolvable"] == 0
        tasks = _read_history(history)
        assert tasks[0]["delivered_size"]["status"] == "ok"
        assert tasks[0]["delivered_size"]["declared_size"] == "S"
        assert tasks[0]["delivered_size"]["headline"] == 3

    def test_backfill_skips_already_measured(self, tmp_path):
        repo_root = str(tmp_path / "repo")
        history = tmp_path / "history.jsonl"
        _init_repo(repo_root)
        merge_commit = _make_merge_commit(repo_root, "src/feature.py", "a\nb\n")
        _make_plan_file(repo_root, "docs/plans/test-task.md", "M")
        _write_history(
            history,
            [
                {
                    "id": "test-task",
                    "settled_at": "2026-07-15T00:00:00Z",
                    "merge_commit": merge_commit,
                    "plan_file": "docs/plans/test-task.md",
                    "delivered_size": {
                        "headline": 999,
                        "total": 999,
                        "status": "ok",
                        "reason": None,
                        "declared_size": "M",
                    },
                },
            ],
        )

        result = metrics.backfill_delivered_size(str(history), repo_root)

        assert result["measured"] == 0
        assert result["skipped"] == 1
        assert result["unresolvable"] == 0
        tasks = _read_history(history)
        assert tasks[0]["delivered_size"]["headline"] == 999

    def test_backfill_counts_unresolvable_no_merge_commit(self, tmp_path):
        history = tmp_path / "history.jsonl"
        _write_history(
            history,
            [
                {"id": "no-merge", "settled_at": "2026-07-15T00:00:00Z"},
            ],
        )

        result = metrics.backfill_delivered_size(str(history), str(tmp_path))

        assert result["measured"] == 0
        assert result["skipped"] == 0
        assert result["unresolvable"] == 1
        assert result["reasons"]["no merge_commit recorded"] == 1

    def test_backfill_run_twice_is_idempotent(self, tmp_path):
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
                },
            ],
        )

        first = metrics.backfill_delivered_size(str(history), repo_root)
        assert first["measured"] == 1
        snapshot = history.read_text(encoding="utf-8")

        second = metrics.backfill_delivered_size(str(history), repo_root)
        assert second["measured"] == 0
        assert second["skipped"] == 1
        assert history.read_text(encoding="utf-8") == snapshot

    def test_backfill_counts_unresolvable_invalid_merge_commit(self, tmp_path):
        history = tmp_path / "history.jsonl"
        _write_history(
            history,
            [
                {
                    "id": "bad-commit",
                    "settled_at": "2026-07-15T00:00:00Z",
                    "merge_commit": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
                },
            ],
        )

        result = metrics.backfill_delivered_size(str(history), str(tmp_path))

        assert result["measured"] == 0
        assert result["skipped"] == 0
        assert result["unresolvable"] == 1
        assert any("first parent" in reason for reason in result["reasons"])
