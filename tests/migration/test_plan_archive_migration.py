"""Tests for the one-time legacy plan-archive migration."""

from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
MIGRATION_PY = REPO_ROOT / "scripts" / "archive" / "migrate-plan-archive.py"
_spec = importlib.util.spec_from_loader(
    "migrate_plan_archive", importlib.machinery.SourceFileLoader("migrate_plan_archive", str(MIGRATION_PY))
)
migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration)


def test_copy_legacy_plan_archive_copies_files(monkeypatch, tmp_path):
    """The migration copies legacy archive files into the plans archive."""
    repo_root = tmp_path / "repo"
    legacy = repo_root / "docs" / "plans" / "archive"
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / "old-1.md").write_text("# old 1\n", encoding="utf-8")
    (legacy / "nested").mkdir(parents=True, exist_ok=True)
    (legacy / "nested" / "old-2.md").write_text("# old 2\n", encoding="utf-8")
    dest = tmp_path / "plans-archive"
    monkeypatch.setenv("AET_PLANS_ARCHIVE_DIR", str(dest))

    result = migration.copy_legacy_plan_archive(repo_root, dest)

    assert result["copied"] == 2
    assert result["skipped"] == 0
    assert (dest / "old-1.md").exists()
    assert (dest / "nested" / "old-2.md").exists()


def test_copy_legacy_plan_archive_skips_existing(monkeypatch, tmp_path):
    """The migration is idempotent: existing destination files are skipped."""
    repo_root = tmp_path / "repo"
    legacy = repo_root / "docs" / "plans" / "archive"
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / "old.md").write_text("# old\n", encoding="utf-8")
    dest = tmp_path / "plans-archive"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "old.md").write_text("# existing\n", encoding="utf-8")
    monkeypatch.setenv("AET_PLANS_ARCHIVE_DIR", str(dest))

    result = migration.copy_legacy_plan_archive(repo_root, dest)

    assert result["copied"] == 0
    assert result["skipped"] == 1
    assert (dest / "old.md").read_text(encoding="utf-8") == "# existing\n"


def test_copy_legacy_plan_archive_missing_source(tmp_path):
    """When the legacy archive is absent, the migration reports no source."""
    result = migration.copy_legacy_plan_archive(tmp_path / "repo", tmp_path / "dest")

    assert result["source_exists"] is False
    assert result["copied"] == 0


def test_copy_legacy_plan_archive_dry_run_does_not_write(monkeypatch, tmp_path):
    """Dry-run reports counts without writing files."""
    repo_root = tmp_path / "repo"
    legacy = repo_root / "docs" / "plans" / "archive"
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / "old.md").write_text("# old\n", encoding="utf-8")
    dest = tmp_path / "plans-archive"
    monkeypatch.setenv("AET_PLANS_ARCHIVE_DIR", str(dest))

    result = migration.copy_legacy_plan_archive(repo_root, dest, dry_run=True)

    assert result["copied"] == 1
    assert not dest.exists()
