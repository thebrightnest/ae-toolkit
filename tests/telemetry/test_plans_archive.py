"""Tests for the settled-plan archive path and copy helper."""

from __future__ import annotations

from pathlib import Path

from aet import queue, telemetry


def test_plans_archive_dir_default_includes_slug(monkeypatch, tmp_path):
    """Default plans archive lives under ~/.aet/<slug>/plans/archive/."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("AET_PLANS_ARCHIVE_DIR", raising=False)
    monkeypatch.setattr(telemetry, "derive_project_slug", lambda _=None: "owner/project")

    result = telemetry.plans_archive_dir()

    assert result == tmp_path / ".aet" / "owner" / "project" / "plans" / "archive"


def test_plans_archive_dir_env_override_wins(monkeypatch, tmp_path):
    """AET_PLANS_ARCHIVE_DIR overrides the computed archive directory."""
    override = tmp_path / "custom-plans-archive"
    monkeypatch.setenv("AET_PLANS_ARCHIVE_DIR", str(override))

    assert telemetry.plans_archive_dir() == override


def test_archive_plan_file_copies_to_plans_archive(monkeypatch, tmp_path):
    """archive_plan_file copies an existing plan into the archive and returns the path."""
    archive = tmp_path / "plans-archive"
    monkeypatch.setenv("AET_PLANS_ARCHIVE_DIR", str(archive))
    src = tmp_path / "docs" / "plans" / "relocated.md"
    src.write_text("---\nid: relocated\n---\n", encoding="utf-8")

    dest = queue.archive_plan_file(src)

    assert dest == archive / "relocated.md"
    assert dest.exists()
    assert dest.read_text(encoding="utf-8") == src.read_text(encoding="utf-8")


def test_archive_plan_file_creates_parent_directories(monkeypatch, tmp_path):
    """archive_plan_file creates the archive directory tree if absent."""
    archive = tmp_path / "nested" / "plans-archive"
    monkeypatch.setenv("AET_PLANS_ARCHIVE_DIR", str(archive))
    src = tmp_path / "live.md"
    src.write_text("---\nid: live\n---\n", encoding="utf-8")

    queue.archive_plan_file(src)

    assert (archive / "live.md").exists()


def test_archive_plan_file_missing_source_returns_none(tmp_path):
    """archive_plan_file returns None when the source plan does not exist."""
    assert queue.archive_plan_file(tmp_path / "missing.md") is None
