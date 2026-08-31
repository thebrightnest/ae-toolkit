"""Standing guard: every live task record carries its portable plan spec.

R-19 moved a task's spec into the record so a task planned on one machine is
executable on another. A record that carries only ``plan_file`` points at a
path that may not exist in any other clone — which is exactly how the board
became unrunnable when the plan files were deleted.

This file used to read *this repository's own* board and assert over it, which
made ``make validate`` a function of runtime state: a task record left behind by
an interrupted run failed the suite for every developer, on every branch, until
someone reaped the ref by hand. It also meant the property was only ever checked
against whatever records happened to exist, so a record *without* a spec was
never constructed and the detection path was never exercised (ADR-072:
conformance is shown by constructing the divergent case, not the agreeing one).

The property now has two homes. Here it is asserted over a fixture, including
the divergent record. Over the live board it is reported by ``aet state audit``,
where debris is the subject rather than a spurious red.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from aet import plan_parser, spec_backfill, worktree


def _record(task_id: str, **frontmatter: Any) -> dict[str, Any]:
    """A task record carrying a portable spec, as admission writes one."""
    fm = {
        "id": task_id,
        "size": "S",
        "security_review": False,
        "docs_sync": True,
        "pipeline": "standard",
    }
    fm.update(frontmatter)
    return {
        "id": task_id,
        "state": "ready",
        "spec": {
            "frontmatter": fm,
            "title": f"Task {task_id}",
            "body": "## Tasks\n\n1. Do the thing — S",
            "tasks": [],
        },
    }


@pytest.fixture
def queue() -> list[dict[str, Any]]:
    return [
        _record("aaa-01"),
        _record("bbb-02", size="M", security_review=True, pipeline="fast"),
    ]


def test_records_carrying_a_spec_are_not_reported(queue):
    assert spec_backfill.records_missing_spec(queue) == []


def test_a_record_with_no_spec_is_reported():
    """The divergent case the live-board version could never construct."""
    legacy = {"id": "ccc-03", "state": "ready", "plan_file": "docs/plans/ccc-03.md"}
    assert spec_backfill.records_missing_spec([legacy]) == ["ccc-03"]


def test_a_record_whose_spec_is_not_a_mapping_is_reported():
    """A leftover string passes a truthiness test and fails at render time."""
    broken = {"id": "ddd-04", "state": "ready", "spec": "docs/plans/ddd-04.md"}
    assert spec_backfill.records_missing_spec([broken]) == ["ddd-04"]


def test_every_record_renders_its_working_plan(queue, tmp_path: Path):
    """The end-to-end property: a clone with no plan files can still run the board.

    This goes through the production entry point and points it at an empty
    repository root so the legacy ``plan_file`` copy cannot mask a missing
    spec — the plan renders from the record or not at all.
    """
    empty_repo = tmp_path / "empty-repo"
    worktree_dir = tmp_path / "worktree"
    empty_repo.mkdir()
    worktree_dir.mkdir()

    for task in queue:
        assert worktree.render_task_plan(
            str(empty_repo), str(worktree_dir), task
        ), f"{task['id']} rendered no working plan"

        target = worktree_dir / "docs" / "plans" / f"{task['id']}.md"
        rendered = plan_parser.parse_frontmatter(target)
        declared = task["spec"]["frontmatter"]
        for key in ("security_review", "docs_sync", "pipeline", "size"):
            assert rendered.get(key) == declared.get(key), (
                f"{task['id']}: rendered {key}={rendered.get(key)!r} but the "
                f"record declares {declared.get(key)!r}"
            )
        assert target.read_text(encoding="utf-8").count("# ") >= 1


def test_a_specless_record_renders_nothing_from_an_empty_repo(tmp_path: Path):
    """The failure R-19 exists to remove, asserted rather than assumed."""
    legacy = {"id": "eee-05", "state": "ready", "plan_file": "docs/plans/eee-05.md"}
    empty_repo = tmp_path / "empty-repo"
    worktree_dir = tmp_path / "worktree"
    empty_repo.mkdir()
    worktree_dir.mkdir()

    assert not worktree.render_task_plan(str(empty_repo), str(worktree_dir), legacy)
