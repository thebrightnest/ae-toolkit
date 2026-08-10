"""Tests for the post-ADR-055 plan contract: no frontmatter status authority."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

from aet import plans_lint

_REPO_ROOT = Path(__file__).parents[2]

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


class TestSettledDecision(unittest.TestCase):
    """Settled-ness derives from footer stage and git ancestry, not status."""

    def test_init_queue_skips_terminal_footer_without_history(self):
        """init-queue skips plans whose footer says they are terminal."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans_dir = root / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            prds_dir = root / "docs" / "prds"
            prds_dir.mkdir(parents=True)
            (prds_dir / "default-prd.md").write_text(
                "# Default PRD\n\n## Requirements\n- **R-1**: default requirement\n",
                encoding="utf-8",
            )

            live = _make_plan(
                plans_dir,
                "live.md",
                footer="*Stage: plan-approved*",
            )
            _make_plan(
                plans_dir,
                "merged.md",
                footer="*Stage: merged*",
            )

            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(
                ["git", "-C", str(root), "config", "user.email", "test@example.com"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(root), "config", "user.name", "Test"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(root), "add", "."],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(root), "commit", "-q", "-m", "initial"],
                check=True,
            )

            agents_dir = root / ".agents"
            agents_dir.mkdir(parents=True)
            queue_file = agents_dir / "work-queue.json"
            history_file = agents_dir / "work-history.jsonl"
            config_file = agents_dir / "aet-config.json"
            queue_file.write_text(
                json.dumps({
                    "tasks": [
                        {
                            "id": "live",
                            "title": "Live",
                            "plan_file": str(live),
                            "blocked_by": [],
                            "blocks": [],
                            "state": "planned",
                        },
                        {
                            "id": "merged",
                            "title": "Merged",
                            "plan_file": str(root / "docs" / "plans" / "merged.md"),
                            "blocked_by": [],
                            "blocks": [],
                            "state": "planned",
                        },
                    ]
                }),
                encoding="utf-8",
            )

            # No history file exists — settled-ness comes from the plan footer.
            result = subprocess.run(
                [
                    sys.executable,
                    str(_REPO_ROOT / "src" / "aet" / "cli" / "init_queue.py"),
                    "--plans-dir",
                    str(plans_dir),
                    "--queue-file",
                    str(queue_file),
                    "--history-file",
                    str(history_file),
                    "--config",
                    str(config_file),
                ],
                cwd=str(root),
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            queue = json.loads(queue_file.read_text(encoding="utf-8"))
            ids = {t["id"] for t in queue["tasks"]}
            self.assertIn("live", ids)
            self.assertNotIn("merged", ids)
