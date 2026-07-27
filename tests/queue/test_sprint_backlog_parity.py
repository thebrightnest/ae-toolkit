"""Parity tests for sprint/backlog plan-argument resolution (R-11b)."""

from __future__ import annotations

from pathlib import Path

import pytest

from aet.cli.backlog import resolve_plan as backlog_resolve_plan
from aet.cli.sprint import resolve_plan as sprint_resolve_plan


@pytest.fixture
def tmp_plans(tmp_path: Path):
    """Create a temporary plans directory with one valid plan."""
    plans_dir = tmp_path / "docs" / "plans"
    plans_dir.mkdir(parents=True)
    (plans_dir / "rid-01.md").write_text("---\nid: rid-01\n---\n", encoding="utf-8")
    return plans_dir


@pytest.mark.parametrize("resolve_plan", [sprint_resolve_plan, backlog_resolve_plan])
class TestSprintBacklogResolutionParity:
    """Both intake commands resolve plan arguments the same way."""

    def test_valid_id_returns_plan_path(
        self, resolve_plan, tmp_plans: Path
    ) -> None:
        result = resolve_plan("rid-01", tmp_plans)
        assert result == tmp_plans / "rid-01.md"

    def test_missing_id_returns_none(
        self, resolve_plan, tmp_plans: Path
    ) -> None:
        result = resolve_plan("no-such-id", tmp_plans)
        assert result is None

    def test_nonexistent_md_path_passthrough(
        self, resolve_plan, tmp_plans: Path
    ) -> None:
        result = resolve_plan(str(tmp_plans / "missing.md"), tmp_plans)
        assert result == tmp_plans / "missing.md"

    def test_existing_md_path_passthrough(
        self, resolve_plan, tmp_plans: Path
    ) -> None:
        result = resolve_plan(str(tmp_plans / "rid-01.md"), tmp_plans)
        assert result == tmp_plans / "rid-01.md"
