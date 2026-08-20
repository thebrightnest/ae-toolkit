"""Tests for nested routing through the consolidated Typer CLI.

The dispatcher no longer forwards argv to sibling binaries.  These tests run
commands through the top-level ``aet`` app and assert on the resulting
behaviour and output.
"""

from __future__ import annotations

import importlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from aet.backends.factory import create_backend
from tests.cli._helpers import git, make_plan, run_typer

# Module objects (not the functions re-exported by ``aet.cli``).
aet = importlib.import_module("aet.cli.main")
sprint = importlib.import_module("aet.cli.sprint")
backlog = importlib.import_module("aet.cli.backlog")
state = importlib.import_module("aet.cli.aet_state")
gate = importlib.import_module("aet.cli.gate")


class TestNestedCommandGroupRouting(unittest.TestCase):
    """Noun groups route to their Typer subcommands and execute them."""

    def _make_git_repo_with_plan(self, tmp_path: Path):
        """Initialise a git repo with a default PRD and one plan file."""
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        prds_dir = tmp_path / "docs" / "prds"
        prds_dir.mkdir(parents=True)
        (prds_dir / "default-prd.md").write_text(
            "# Default PRD\n\n## Requirements\n- **R-1**: default requirement\n",
            encoding="utf-8",
        )
        make_plan(plans_dir, "feat-001.md")
        git(["init"], tmp_path)
        git(["config", "user.email", "test@example.com"], tmp_path)
        git(["config", "user.name", "Test"], tmp_path)
        git(["add", "-A"], tmp_path)
        git(["commit", "-m", "initial"], tmp_path)
        return plans_dir

    def test_sprint_add_routes_through_main_app(self):
        """``aet sprint add <plan>`` promotes the plan and adds it to the queue."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plans_dir = self._make_git_repo_with_plan(tmp_path)
            queue_file = str(tmp_path / ".agents" / "aet-queue")
            history_file = str(tmp_path / ".agents" / "work-history.jsonl")
            Path(history_file).parent.mkdir(parents=True, exist_ok=True)

            with patch.object(sprint, "resolve_projections", return_value=MagicMock()):
                with patch.object(sprint, "resolve_config", return_value={}):
                    result = run_typer(
                        aet.app,
                        [
                            "sprint",
                            "add",
                            "feat-001",
                            "--queue-file",
                            queue_file,
                            "--history-file",
                            history_file,
                            "--plans-dir",
                            str(plans_dir),
                        ],
                        cwd=tmp_path,
                    )

            self.assertEqual(result.exit_code, 0, result.output + result.stderr)
            self.assertIn("queued without publishing", result.output)

            backend = create_backend(queue_file=queue_file, history_file=history_file)
            queue = backend.load()["queue"]
            self.assertEqual(len(queue), 1)
            self.assertEqual(queue[0]["id"], "feat-001")
            self.assertEqual(queue[0]["state"], "ready")

            plan_text = (plans_dir / "feat-001.md").read_text(encoding="utf-8")
            self.assertNotIn("status:", plan_text)
            self.assertIn("_Stage: plan-approved_", plan_text)

            # Intake no longer commits plan-path status updates (ADR-054).
            log = subprocess.run(
                ["git", "log", "--format=%s"],
                cwd=tmp_path,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(log.stdout.strip(), "initial")

    def test_backlog_add_routes_through_main_app(self):
        """``aet backlog add <plan>`` adds an approved plan to the backlog board."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plans_dir = self._make_git_repo_with_plan(tmp_path)

            with patch.object(backlog, "resolve_projections", return_value=MagicMock()):
                with patch.object(backlog, "resolve_config", return_value={}):
                    result = run_typer(
                        aet.app,
                        [
                            "backlog",
                            "add",
                            "feat-001",
                            "--plans-dir",
                            str(plans_dir),
                        ],
                        cwd=tmp_path,
                    )

            self.assertEqual(result.exit_code, 0, result.output + result.stderr)
            self.assertIn("Added feat-001.md", result.output)

    def test_state_audit_routes_through_main_app(self):
        """``aet state audit <queue>`` runs the audit through the main app."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            queue_file = tmp_path / ".agents" / "aet-queue"
            queue_file.parent.mkdir(parents=True)
            queue_file.write_text("[]", encoding="utf-8")
            git(["init", "-q"], tmp_path)
            git(["config", "user.email", "test@example.com"], tmp_path)
            git(["config", "user.name", "Test"], tmp_path)
            git(["add", "-A"], tmp_path)
            git(["commit", "-q", "-m", "initial"], tmp_path)

            result = run_typer(
                aet.app,
                ["state", "audit", str(queue_file)],
                cwd=tmp_path,
            )

            self.assertEqual(result.exit_code, 0, result.output + result.stderr)
            self.assertIn("{", result.output)

    def test_gate_review_routes_through_main_app(self):
        """``aet gate review`` renders the board through the main app."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plans_dir = tmp_path / "plans"
            plans_dir.mkdir()
            make_plan(plans_dir, "feat-001.md", footer_stage="plan-approved")

            result = run_typer(
                aet.app,
                ["gate", "review", "--plans-dir", str(plans_dir)],
                cwd=tmp_path,
            )

            self.assertEqual(result.exit_code, 0, result.output + result.stderr)
            self.assertIn("feat-001", result.output)


if __name__ == "__main__":
    unittest.main()
