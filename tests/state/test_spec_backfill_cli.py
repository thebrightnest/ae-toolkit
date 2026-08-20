"""End-to-end tests for `aet-state backfill-specs`.

The migration writes through the sanctioned queue backend so the board's
sole-writer rule holds; these tests drive the real CLI against a real
temporary git repository and read the result back through the backend.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import subprocess
from pathlib import Path

import pytest

from aet.queue import acquire_lease
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
    """A repo with a pre-R-19 queue and plan files deleted one commit back."""
    root = tmp_path / "repo"
    plans = root / "docs" / "plans"
    plans.mkdir(parents=True)
    (root / ".agents").mkdir()
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test User")
    for task_id in ("owb-03", "owb-04"):
        (plans / f"{task_id}.md").write_text(PLAN.format(task_id=task_id), encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "plans exist")
    for task_id in ("owb-03", "owb-04"):
        (plans / f"{task_id}.md").unlink()
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "delete the plans")

    queue_path, history_path = seed_git_queue(
        root,
        [
            {
                "id": task_id,
                "title": f"Title for {task_id}",
                "plan_file": f"docs/plans/{task_id}.md",
                "state": "ready",
                "blocked_by": [],
                "history": [],
            }
            for task_id in ("owb-03", "owb-04")
        ],
    )
    history_path.write_text("", encoding="utf-8")
    monkeypatch.chdir(root)
    return root


def _queue(repo: Path) -> list[dict]:
    backend = aet_state.make_backend(str(repo / ".agents" / "aet-queue"))
    return backend.load()["queue"]


class TestBackfillSpecsCommand:
    def test_dry_run_reports_without_writing(self, repo: Path, capsys):
        rc = aet_state.main(
            ["backfill-specs", ".agents/aet-queue", "--rev", "HEAD~1"]
        )

        assert rc == 0
        out = capsys.readouterr().out
        assert "owb-03" in out
        assert "owb-04" in out
        assert "dry-run" in out
        assert all("spec" not in task for task in _queue(repo))

    def test_an_unresolvable_revision_is_called_out(self, repo: Path, capsys):
        """The operator must be told the source is missing, not that the plans are."""
        rc = aet_state.main(
            ["backfill-specs", ".agents/aet-queue", "--rev", "deadbeef~1"]
        )

        assert rc == 0
        captured = capsys.readouterr()
        assert "does not resolve in this clone" in captured.err
        assert "nothing to backfill" not in captured.out

    def test_apply_writes_the_spec_into_every_record(self, repo: Path):
        rc = aet_state.main(
            ["backfill-specs", ".agents/aet-queue", "--rev", "HEAD~1", "--apply"]
        )

        assert rc == 0
        tasks = _queue(repo)
        assert len(tasks) == 2
        for task in tasks:
            spec = task["spec"]
            assert spec["frontmatter"]["pipeline"] == "full"
            assert spec["frontmatter"]["security_review"] == "required"
            assert spec["frontmatter"]["docs_sync"] == "skipped"
            assert spec["tasks"] == ["1. Do the work (traces: R-19)"]

    def test_rerunning_after_apply_is_a_noop(self, repo: Path, capsys):
        aet_state.main(
            ["backfill-specs", ".agents/aet-queue", "--rev", "HEAD~1", "--apply"]
        )
        before = _queue(repo)
        capsys.readouterr()

        rc = aet_state.main(
            ["backfill-specs", ".agents/aet-queue", "--rev", "HEAD~1", "--apply"]
        )

        assert rc == 0
        assert "nothing to backfill" in capsys.readouterr().out
        assert _queue(repo) == before

    def test_apply_refused_while_another_run_holds_the_lease(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        """The migration mutates the board, so it obeys the run lease.

        A batch that is mid-flight owns the queue; backfilling underneath it
        would write over state the running orchestrator is about to save.
        """
        monkeypatch.delenv("AET_RUN_ID", raising=False)
        queue_path = repo / ".agents" / "aet-queue"
        acquire_lease(str(queue_path), "foreign-run")

        rc = aet_state.main(
            ["backfill-specs", ".agents/aet-queue", "--rev", "HEAD~1", "--apply"]
        )

        assert rc == 1
        assert "foreign-run" in capsys.readouterr().err
        assert all("spec" not in task for task in _queue(repo))

    def test_force_overrides_a_held_lease(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.delenv("AET_RUN_ID", raising=False)
        queue_path = repo / ".agents" / "aet-queue"
        acquire_lease(str(queue_path), "foreign-run")

        rc = aet_state.main([
            "backfill-specs",
            ".agents/aet-queue",
            "--rev",
            "HEAD~1",
            "--apply",
            "--force",
        ])

        assert rc == 0
        assert all(isinstance(task["spec"], dict) for task in _queue(repo))

    def test_unrecoverable_record_is_named_and_the_rest_still_land(
        self, repo: Path, capsys
    ):
        queue_path = repo / ".agents" / "aet-queue"
        backend = aet_state.make_backend(str(queue_path))
        data = backend.load()
        data["queue"].append(
            {
                "id": "ghost-99",
                "title": "Ghost",
                "plan_file": "docs/plans/ghost-99.md",
                "state": "ready",
                "blocked_by": [],
                "history": [],
            }
        )
        backend.save(data["queue"])

        rc = aet_state.main(
            ["backfill-specs", ".agents/aet-queue", "--rev", "HEAD~1", "--apply"]
        )

        assert rc == 0
        captured = capsys.readouterr()
        assert "ghost-99" in captured.out + captured.err
        by_id = {task["id"]: task for task in _queue(repo)}
        assert "spec" not in by_id["ghost-99"]
        assert isinstance(by_id["owb-03"]["spec"], dict)
        assert isinstance(by_id["owb-04"]["spec"], dict)
