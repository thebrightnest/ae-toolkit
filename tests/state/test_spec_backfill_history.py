"""End-to-end tests for `aet-state backfill-specs --history-file`.

The settled history log is append-only JSONL; these tests verify that the
backfill rewrites it atomically, touches only the ``spec`` key, and names every
unrecoverable record.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

from aet.queue import acquire_lease, read_history
from tests.state._helpers import seed_git_queue

_AET_STATE_PY = Path(__file__).parents[2] / "src" / "aet" / "cli" / "aet_state.py"

_state_spec = importlib.util.spec_from_loader(
    "aet_state", importlib.machinery.SourceFileLoader("aet_state", str(_AET_STATE_PY))
)
aet_state = importlib.util.module_from_spec(_state_spec)
_state_spec.loader.exec_module(aet_state)

pytestmark = pytest.mark.xdist_group("cwd")

PLAN = """---
id: {task_id}
size: M
pipeline: full
security_review: required
docs_sync: skipped
docs_sync_reason: no user-facing surface
work_class: normal
blocked_by: []
---

# Plan: Title for {task_id}

## Task List

1. Do the work (traces: R-19)

---

*Stage: plan-approved*
"""


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repo with a queue, an empty history log, and one deleted plan."""
    root = tmp_path / "repo"
    plans = root / "docs" / "plans"
    plans.mkdir(parents=True)
    (root / ".agents").mkdir()
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test User")
    (plans / "owb-03.md").write_text(PLAN.format(task_id="owb-03"), encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "plans exist")
    (plans / "owb-03.md").unlink()
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "delete the plans")

    queue_path, history_path = seed_git_queue(
        root,
        [
            {
                "id": "owb-03",
                "title": "Title for owb-03",
                "plan_file": "docs/plans/owb-03.md",
                "state": "ready",
                "blocked_by": [],
                "history": [],
            }
        ],
    )
    history_path.write_text("", encoding="utf-8")
    monkeypatch.chdir(root)
    return root


def _history(repo: Path) -> list[dict]:
    return read_history(str(repo / ".agents" / "work-history.jsonl"))


def _write_history(repo: Path, records: list[dict]) -> None:
    path = repo / ".agents" / "work-history.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")


class TestBackfillSpecsHistory:
    def test_history_dry_run_reports_without_writing(self, repo: Path, capsys):
        _write_history(repo, [{"id": "owb-03", "plan_file": "docs/plans/owb-03.md"}])

        rc = aet_state.main(
            [
                "backfill-specs",
                ".agents/aet-queue",
                "--history-file",
                ".agents/work-history.jsonl",
                "--rev",
                "HEAD~1",
            ]
        )

        assert rc == 0
        out = capsys.readouterr().out
        assert "owb-03" in out
        assert "dry-run" in out.lower() or "would" in out
        assert all("spec" not in record for record in _history(repo))

    def test_history_apply_writes_spec_and_preserves_count_and_order(
        self, repo: Path, capsys
    ):
        records = [
            {"id": "owb-03", "plan_file": "docs/plans/owb-03.md"},
            {
                "id": "owb-04",
                "plan_file": "docs/plans/owb-04.md",
                "spec": {
                    "frontmatter": {"size": "S"},
                    "title": "Plan: Title for owb-04",
                    "body": "",
                    "tasks": [],
                },
            },
        ]
        _write_history(repo, records)

        rc = aet_state.main(
            [
                "backfill-specs",
                ".agents/aet-queue",
                "--history-file",
                ".agents/work-history.jsonl",
                "--rev",
                "HEAD~1",
                "--apply",
            ]
        )

        assert rc == 0
        history = _history(repo)
        assert len(history) == 2
        assert [r["id"] for r in history] == ["owb-03", "owb-04"]
        assert isinstance(history[0]["spec"], dict)
        assert history[0]["spec"]["frontmatter"]["size"] == "M"
        assert history[1]["spec"]["frontmatter"]["size"] == "S"
        captured = capsys.readouterr()
        assert "Records carrying spec.frontmatter.size" in captured.out

    def test_history_archive_fallback_when_rev_and_disk_miss(
        self, repo: Path, capsys
    ):
        archive = repo / "docs" / "plans" / "archive"
        archive.mkdir(parents=True)
        (archive / "owb-03.md").write_text(
            PLAN.format(task_id="owb-03").replace("size: M", "size: S"),
            encoding="utf-8",
        )
        _write_history(repo, [{"id": "owb-03", "plan_file": "docs/plans/owb-03.md"}])

        rc = aet_state.main(
            [
                "backfill-specs",
                ".agents/aet-queue",
                "--history-file",
                ".agents/work-history.jsonl",
                "--rev",
                "deadbeef~1",
                "--apply",
            ]
        )

        assert rc == 0
        history = _history(repo)
        assert history[0]["spec"]["frontmatter"]["size"] == "S"

    def test_history_unrecoverable_record_is_named_and_others_still_fill(
        self, repo: Path, capsys
    ):
        records = [
            {"id": "owb-03", "plan_file": "docs/plans/owb-03.md"},
            {"id": "ghost-99", "plan_file": "docs/plans/ghost-99.md"},
        ]
        _write_history(repo, records)

        rc = aet_state.main(
            [
                "backfill-specs",
                ".agents/aet-queue",
                "--history-file",
                ".agents/work-history.jsonl",
                "--rev",
                "HEAD~1",
                "--apply",
            ]
        )

        assert rc == 0
        captured = capsys.readouterr()
        assert "ghost-99" in captured.out + captured.err
        history = _history(repo)
        by_id = {r["id"]: r for r in history}
        assert "spec" not in by_id["ghost-99"]
        assert isinstance(by_id["owb-03"]["spec"], dict)

    def test_history_rerun_after_apply_is_a_noop(self, repo: Path, capsys):
        _write_history(repo, [{"id": "owb-03", "plan_file": "docs/plans/owb-03.md"}])
        aet_state.main(
            [
                "backfill-specs",
                ".agents/aet-queue",
                "--history-file",
                ".agents/work-history.jsonl",
                "--rev",
                "HEAD~1",
                "--apply",
            ]
        )
        before = _history(repo)
        capsys.readouterr()

        rc = aet_state.main(
            [
                "backfill-specs",
                ".agents/aet-queue",
                "--history-file",
                ".agents/work-history.jsonl",
                "--rev",
                "HEAD~1",
                "--apply",
            ]
        )

        assert rc == 0
        assert "nothing to backfill" in capsys.readouterr().out
        assert _history(repo) == before

    def test_history_apply_refused_while_another_run_holds_the_lease(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        monkeypatch.delenv("AET_RUN_ID", raising=False)
        queue_path = repo / ".agents" / "aet-queue"
        acquire_lease(str(queue_path), "foreign-run")
        _write_history(repo, [{"id": "owb-03", "plan_file": "docs/plans/owb-03.md"}])

        rc = aet_state.main(
            [
                "backfill-specs",
                ".agents/aet-queue",
                "--history-file",
                ".agents/work-history.jsonl",
                "--rev",
                "HEAD~1",
                "--apply",
            ]
        )

        assert rc == 1
        assert "foreign-run" in capsys.readouterr().err
        assert all("spec" not in record for record in _history(repo))

    def test_history_force_overrides_a_held_lease(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.delenv("AET_RUN_ID", raising=False)
        queue_path = repo / ".agents" / "aet-queue"
        acquire_lease(str(queue_path), "foreign-run")
        _write_history(repo, [{"id": "owb-03", "plan_file": "docs/plans/owb-03.md"}])

        rc = aet_state.main(
            [
                "backfill-specs",
                ".agents/aet-queue",
                "--history-file",
                ".agents/work-history.jsonl",
                "--rev",
                "HEAD~1",
                "--apply",
                "--force",
            ]
        )

        assert rc == 0
        assert all(isinstance(record.get("spec"), dict) for record in _history(repo))
