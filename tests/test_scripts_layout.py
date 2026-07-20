"""Acceptance tests for the scripts/ audience split.

These tests encode the intended repo layout after pkg-13-scripts-split:
migrations are archived, misplaced pytest modules leave scripts/, and the
archive documents when each migration shipped.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
ARCHIVE = SCRIPTS / "archive"


class TestScriptsLayout:
    def test_migration_scripts_are_archived(self):
        assert (ARCHIVE / "migrate-plans-to-frontmatter.py").exists()
        assert (ARCHIVE / "migrate-telemetry-slugs.py").exists()

    def test_misplaced_pytest_modules_removed(self):
        assert not (SCRIPTS / "test-aet-state.py").exists()
        assert not (SCRIPTS / "test-telemetry.py").exists()

    def test_archive_readme_documents_releases(self):
        readme = ARCHIVE / "README.md"
        assert readme.exists()
        text = readme.read_text()
        assert "v0.7.0" in text
        assert "v1.0.0" in text
        assert "migrate-plans-to-frontmatter.py" in text
        assert "migrate-telemetry-slugs.py" in text
