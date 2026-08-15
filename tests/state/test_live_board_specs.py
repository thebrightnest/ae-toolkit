"""Standing guard: every live task record carries its portable plan spec.

R-19 moved a task's spec into the record so a task planned on one machine is
executable on another. A record that carries only ``plan_file`` points at a
path that may not exist in any other clone — which is exactly how the board
became unrunnable when the plan files were deleted.

This test reads this repository's own board and fails if any record has no
spec, so a record cannot be admitted without one and go unnoticed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aet import plan_parser, spec_backfill, worktree
from aet.cli.aet_state import make_backend

pytestmark = pytest.mark.xdist_group("cwd")

REPO_ROOT = Path(__file__).parents[2]
QUEUE_PATH = REPO_ROOT / ".agents" / "work-queue.json"


def _live_queue() -> list[dict]:
    """Load the board without fetching — local refs only, no network."""
    backend = make_backend(str(QUEUE_PATH))
    try:
        return backend.load(verify=False)["queue"]
    finally:
        backend.close()


def test_every_live_record_carries_a_plan_spec():
    queue = _live_queue()
    if not queue:
        pytest.skip("no board in this checkout")

    missing = spec_backfill.records_missing_spec(queue)

    assert missing == [], (
        "these live task records carry no plan spec and are not executable in "
        f"another clone: {', '.join(missing)}. Run "
        "`aet-state backfill-specs --apply` to recover them from git."
    )


def test_every_live_record_renders_its_working_plan(tmp_path: Path):
    """The end-to-end property: a clone with no plan files can still run the board.

    This goes through the production entry point, and points it at an empty
    repository root so the legacy ``plan_file`` copy cannot mask a missing
    spec — the plan renders from the record or not at all.
    """
    queue = _live_queue()
    if not queue:
        pytest.skip("no board in this checkout")

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
