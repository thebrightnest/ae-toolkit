"""Tests for the post-ADR-055 plan contract: no frontmatter status authority."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pytest

from aet import plans_lint

pytestmark = pytest.mark.xdist_group("telemetry-dir")


def _make_plan(
    plans_dir: Path,
    name: str,
    *,
    frontmatter: dict | None = None,
    body: str = "",
    footer: str = "",
    prd: str = "docs/prds/default-prd.md",
) -> Path:
    """Create a minimal plan file with the given frontmatter and PRD context."""
    path = plans_dir / name
    fm: dict[str, object] = {"id": Path(name).stem, "size": "S"}
    fm.update(frontmatter or {})

    fm_lines: list[str] = []
    for key, value in fm.items():
        if isinstance(value, list):
            fm_lines.append(f"{key}:")
            for item in value:
                fm_lines.append(f"  - {item}")
        else:
            fm_lines.append(f"{key}: {value}")

    fm_block = "\n".join(fm_lines)
    footer_block = f"\n\n---\n\n{footer}" if footer else ""
    text = (
        f"---\n{fm_block}\n---\n\n"
        f"# Plan\n\n"
        f"## Context\n\n"
        f"PRD: {prd}\n\n"
        f"## Task List\n\n"
        f"1. Do something (traces: R-1).\n\n"
        f"{body}"
        f"{footer_block}"
    )
    path.write_text(text, encoding="utf-8")
    return path


class TestStatusFieldRejected(unittest.TestCase):
    """The status frontmatter field is no longer part of the plan contract."""

    def test_plans_lint_flags_any_status_field(self):
        """Any live status frontmatter field is reported as an error."""
        with tempfile.TemporaryDirectory() as tmp:
            plans_dir = Path(tmp) / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            _make_plan(
                plans_dir,
                "has-status.md",
                frontmatter={"status": "draft"},
            )
            violations = plans_lint.lint_corpus(plans_dir)
            self.assertEqual(len(violations), 1, violations)
            self.assertIn("status", violations[0][1])


