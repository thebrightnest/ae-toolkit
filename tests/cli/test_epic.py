"""Tests for `aet epic` CLI command group."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aet.backends.factory import create_backend
from aet.cli.main import app
from tests.cli._helpers import git, run_typer


class TestEpicCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        git(["init"], self.repo)
        git(["config", "user.email", "test@example.com"], self.repo)
        git(["config", "user.name", "Test User"], self.repo)
        (self.repo / "README.md").write_text("# Test Repo\n", encoding="utf-8")
        git(["add", "README.md"], self.repo)
        git(["commit", "-m", "initial"], self.repo)
        git(["branch", "-M", "main"], self.repo)

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, rel: str, text: str) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _save_queue(self, queue: list[dict]) -> None:
        backend = create_backend(
            queue_file=str(self.repo / ".agents" / "aet-queue"),
            history_file=str(self.repo / ".agents" / "work-history.jsonl"),
        )
        try:
            backend.save(queue)
        finally:
            backend.close()

    def test_removed_declaration_commands_are_unknown(self):
        """R-12: `aet epic set`, `show` and `clear` exit as unknown commands."""
        for argv in (["epic", "set", "feat/x"], ["epic", "show"], ["epic", "clear"]):
            result = run_typer(app, argv, cwd=self.repo)
            self.assertNotEqual(result.exit_code, 0, argv)
            self.assertIn("No such command", result.output, argv)

    def test_list_prints_one_row_per_prd_branch(self):
        """R-12: a queue with tasks from two PRDs lists two branches with provenance, counts and title."""
        self._write(".agents/aet-config.json", '{"integration_mode": "single-pr"}\n')
        self._write(
            "docs/prds/alpha-prd.md",
            "---\npr_title: Alpha suite\n---\n\n# Alpha\n",
        )
        self._write("docs/prds/beta.md", "---\nbranch: feat/declared-beta\n---\n\n# Beta\n")
        alpha = {"frontmatter": {"source_prd": "docs/prds/alpha-prd.md"}}
        beta = {"frontmatter": {"source_prd": "docs/prds/beta.md"}}
        self._save_queue(
            [
                {"id": "a-1", "state": "queued", "spec": alpha},
                {"id": "a-2", "state": "implemented", "spec": alpha},
                {"id": "b-1", "state": "queued", "spec": beta},
            ]
        )

        result = run_typer(app, ["epic", "list"], cwd=self.repo)

        self.assertEqual(result.exit_code, 0, result.output)
        rows = [line for line in result.output.splitlines() if line.startswith("  ")]
        self.assertEqual(len(rows), 2, result.output)
        alpha_row = next(row for row in rows if "feat/alpha" in row)
        beta_row = next(row for row in rows if "feat/declared-beta" in row)
        self.assertIn("(prd)", alpha_row)
        self.assertIn("implemented=1", alpha_row)
        self.assertIn("queued=1", alpha_row)
        self.assertIn("Alpha suite", alpha_row)
        self.assertIn("(document)", beta_row)
        self.assertIn("queued=1", beta_row)

    def test_list_on_empty_queue_reports_no_tasks(self):
        """R-12: an empty queue lists no epic branches."""
        result = run_typer(app, ["epic", "list"], cwd=self.repo)

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("No queued tasks", result.output)


if __name__ == "__main__":
    unittest.main()
