"""Tests for the shared plan-argument resolver in aet.plan_parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from aet.plan_parser import resolve_plan_arg


class TestResolvePlanArg:
    """Behavior-driven tests for ``resolve_plan_arg``."""

    @pytest.fixture
    def tmp_cwd(self, tmp_path: Path, monkeypatch):
        """Run assertions from ``tmp_path`` so relative paths resolve there."""
        monkeypatch.chdir(tmp_path)
        return tmp_path

    def test_resolves_bare_id_to_conventional_path(self, tmp_cwd: Path) -> None:
        plan = tmp_cwd / "docs" / "plans" / "rid-01.md"
        plan.parent.mkdir(parents=True)
        plan.write_text("---\nid: rid-01\n---\n", encoding="utf-8")

        result = resolve_plan_arg("rid-01")

        assert result == "docs/plans/rid-01.md"

    def test_respects_custom_plans_dir(self, tmp_cwd: Path) -> None:
        plans_dir = tmp_cwd / "custom" / "plans"
        plan = plans_dir / "task-01.md"
        plan.parent.mkdir(parents=True)
        plan.write_text("---\nid: task-01\n---\n", encoding="utf-8")

        result = resolve_plan_arg("task-01", plans_dir=plans_dir)

        assert result == str(plans_dir / "task-01.md")

    def test_missing_id_raises_valueerror_naming_both_forms(self, tmp_cwd: Path) -> None:
        (tmp_cwd / "docs" / "plans").mkdir(parents=True)

        with pytest.raises(ValueError) as exc_info:
            resolve_plan_arg("no-such-id")

        message = str(exc_info.value)
        assert "no-such-id" in message
        assert ".md" in message
        assert "docs/plans/no-such-id.md" in message

    def test_resolves_bare_id_to_active_path(self, tmp_cwd: Path) -> None:
        plan = tmp_cwd / "docs" / "plans" / "active" / "rid-01.md"
        plan.parent.mkdir(parents=True)
        plan.write_text("---\nid: rid-01\n---\n", encoding="utf-8")

        result = resolve_plan_arg("rid-01")

        assert result == "docs/plans/active/rid-01.md"

    def test_active_takes_precedence_over_legacy(self, tmp_cwd: Path) -> None:
        active_plan = tmp_cwd / "docs" / "plans" / "active" / "rid-01.md"
        active_plan.parent.mkdir(parents=True)
        active_plan.write_text("---\nid: rid-01\n---\n", encoding="utf-8")

        legacy_plan = tmp_cwd / "docs" / "plans" / "rid-01.md"
        legacy_plan.write_text("---\nid: rid-01\n---\n", encoding="utf-8")

        result = resolve_plan_arg("rid-01")

        assert result == "docs/plans/active/rid-01.md"

    def test_archived_plan_not_resolved_by_bare_id(self, tmp_cwd: Path) -> None:
        archive_plan = tmp_cwd / "docs" / "plans" / "archive" / "archived-01.md"
        archive_plan.parent.mkdir(parents=True)
        archive_plan.write_text("---\nid: archived-01\n---\n", encoding="utf-8")

        with pytest.raises(ValueError):
            resolve_plan_arg("archived-01")

    def test_md_path_passthrough_even_when_missing(self, tmp_cwd: Path) -> None:
        result = resolve_plan_arg("docs/plans/missing.md")

        assert result == "docs/plans/missing.md"

    def test_absolute_md_path_passthrough(self, tmp_cwd: Path) -> None:
        path = str(tmp_cwd / "docs" / "plans" / "absolute.md")

        result = resolve_plan_arg(path)

        assert result == path

    def test_custom_plans_dir_with_active(self, tmp_cwd: Path) -> None:
        plans_dir = tmp_cwd / "custom" / "plans"
        plan = plans_dir / "active" / "task-01.md"
        plan.parent.mkdir(parents=True)
        plan.write_text("---\nid: task-01\n---\n", encoding="utf-8")

        result = resolve_plan_arg("task-01", plans_dir=plans_dir)

        assert result == str(plans_dir / "active" / "task-01.md")


class TestResolvePlanArgDefaultPlansDir:
    """The default ``plans_dir`` is ``Path(\"docs/plans\")`` relative to cwd."""

    def test_default_plans_dir(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        plan = tmp_path / "docs" / "plans" / "defaulted.md"
        plan.parent.mkdir(parents=True)
        plan.write_text("---\nid: defaulted\n---\n", encoding="utf-8")

        result = resolve_plan_arg("defaulted")

        assert result == "docs/plans/defaulted.md"
