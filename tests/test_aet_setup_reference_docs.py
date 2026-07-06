"""Tests for aet-setup reference documentation scaffolding."""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SKILL_FILE = REPO_ROOT / "aet-setup" / "SKILL.md"
CHECKLIST_FILE = REPO_ROOT / "aet-setup" / "checklist.md"
EXAMPLES_DIR = REPO_ROOT / "aet-setup" / "examples"

REFERENCE_EXAMPLES = [
    "reference-README.md.example",
    "testing-strategy.md.example",
    "api-conventions.md.example",
    "security-guidelines.md.example",
    "ui-conventions.md.example",
    "worktree-ship-hygiene.md.example",
]


def test_skill_line_count_under_400():
    """SKILL.md must remain under the 400-line project limit."""
    lines = SKILL_FILE.read_text().splitlines()
    assert len(lines) <= 400, f"aet-setup/SKILL.md has {len(lines)} lines (max 400)"


def test_skill_mentions_reference_templates():
    """SKILL.md must list the reference template files that are copied during setup."""
    content = SKILL_FILE.read_text()
    for filename in REFERENCE_EXAMPLES:
        assert filename in content, f"SKILL.md should mention {filename}"


def test_skill_mentions_reference_copy_destination():
    """SKILL.md must describe where reference templates are copied in target projects."""
    content = SKILL_FILE.read_text()
    assert "docs/references/" in content


def test_checklist_has_reference_doc_items():
    """Checklist must verify that reference docs are scaffolded and kept load-on-demand."""
    content = CHECKLIST_FILE.read_text()
    assert "docs/references/" in content
    assert "load-on-demand" in content.lower()
    assert "bloat" in content.lower()


def test_reference_example_files_exist():
    """All reference templates referenced by the skill must exist in examples/."""
    for filename in REFERENCE_EXAMPLES:
        assert (
            EXAMPLES_DIR / filename
        ).exists(), f"Missing reference example: aet-setup/examples/{filename}"
