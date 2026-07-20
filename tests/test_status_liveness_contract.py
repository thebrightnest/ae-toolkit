"""Tests for the status liveness contract (gib-03)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from aet import plan_parser, plan_validate

_REPO_ROOT = Path(__file__).parent.parent


def _make_plan(
    plans_dir: Path,
    name: str,
    *,
    frontmatter: dict | None = None,
    body: str = "",
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
    text = (
        f"---\n{fm_block}\n---\n\n"
        f"# Plan\n\n"
        f"## Context\n\n"
        f"PRD: {prd}\n\n"
        f"## Task List\n\n"
        f"1. Do something (traces: R-1).\n\n"
        f"{body}\n"
    )
    path.write_text(text, encoding="utf-8")
    return path


class TestStatusValidation(unittest.TestCase):
    """Status field validation in plan_validate."""

    def test_status_required_for_new_plan(self):
        """A plan that declares status must use a legal lifecycle value."""
        with tempfile.TemporaryDirectory() as tmp:
            plans_dir = Path(tmp) / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            plan = _make_plan(
                plans_dir,
                "has-status.md",
                frontmatter={"status": "draft"},
            )
            findings = plan_validate.validate([plan])
            self.assertFalse(
                any(f.check_id == "status" for f in findings),
                "legal status: draft should not produce a status finding",
            )

    def test_statusless_legacy_plan_is_exempt_and_settled(self):
        """A plan with no status field is exempt from the requirement and settled."""
        with tempfile.TemporaryDirectory() as tmp:
            plans_dir = Path(tmp) / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            plan = _make_plan(plans_dir, "legacy.md")
            findings = plan_validate.validate([plan])
            self.assertFalse(
                any(f.check_id == "status" for f in findings),
                "statusless legacy plan should be exempt from the status requirement",
            )
            self.assertTrue(
                plan_validate.is_settled_plan(plan),
                "statusless legacy plan should be classified as settled",
            )

    def test_illegal_status_value_rejected(self):
        """An illegal status value is rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            plans_dir = Path(tmp) / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            plan = _make_plan(
                plans_dir,
                "bad-status.md",
                frontmatter={"status": "unknown"},
            )
            findings = plan_validate.validate([plan])
            status_findings = [f for f in findings if f.check_id == "status"]
            self.assertEqual(len(status_findings), 1, status_findings)
            self.assertIn("unknown", status_findings[0].message)


class TestSettledDecision(unittest.TestCase):
    """Settled-ness derives from committed plan data, not local history."""

    def test_settled_decision_ignores_history_log(self):
        """init-queue rebuild skips settled plans even when history log is absent."""
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

            _make_plan(plans_dir, "legacy.md")
            _make_plan(plans_dir, "merged.md", frontmatter={"status": "merged"})
            _make_plan(plans_dir, "live.md", frontmatter={"status": "queued"})

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

            queue_file = root / ".agents" / "work-queue.json"
            history_file = root / ".agents" / "work-history.jsonl"
            config_file = root / ".agents" / "aet-work.json"

            # No history file exists — this is the R-7 regression case.
            result = subprocess.run(
                [
                    sys.executable,
                    str(_REPO_ROOT / "aet-work" / "bin" / "init-queue"),
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
            self.assertNotIn("legacy", ids)
            self.assertNotIn("merged", ids)

    def test_corpus_classifier_matches_known_live_set(self):
        """Over the real docs/plans/ corpus, only statusless + terminal plans are settled."""
        plans_dir = _REPO_ROOT / "docs" / "plans"
        plan_files = sorted(plans_dir.glob("*.md"))
        self.assertGreater(len(plan_files), 0, "corpus should contain plans")

        statusless: list[Path] = []
        terminal: list[Path] = []
        live: list[Path] = []
        for pf in plan_files:
            data = plan_parser.parse_frontmatter(pf)
            status = data.get("status")
            if status is None:
                statusless.append(pf)
            elif status in plan_validate.TERMINAL_PLAN_STATUSES:
                terminal.append(pf)
            else:
                live.append(pf)

        actual_settled = [pf for pf in plan_files if plan_validate.is_settled_plan(pf)]
        expected_settled = sorted(statusless + terminal)
        self.assertEqual(
            actual_settled,
            expected_settled,
            f"settled classification diverged from committed status: "
            f"statusless={len(statusless)} terminal={len(terminal)} live={len(live)}",
        )

        # Hardcoded census regression guard. Update when the corpus changes.
        self.assertEqual(len(plan_files), 238)
        self.assertEqual(len(statusless), 120)
        self.assertEqual(len(terminal), 101)
        self.assertEqual(len(live), 17)
