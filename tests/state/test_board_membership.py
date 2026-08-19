"""Tests for the open-work board contract: membership is the explicit queue record."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SYNC_PY = _REPO_ROOT / "src" / "aet" / "cli" / "sync.py"

_sync_spec = __import__("importlib.util").util.spec_from_loader(
    "sync_cmd", __import__("importlib.machinery").machinery.SourceFileLoader("sync_cmd", str(_SYNC_PY))
)
sync_cmd = __import__("importlib.util").util.module_from_spec(_sync_spec)
_sync_spec.loader.exec_module(sync_cmd)


def _write_plan(plans_dir: Path, stem: str, blocked_by=None):
    """Write a minimal valid plan file without frontmatter status."""
    path = plans_dir / f"{stem}.md"
    lines = ["---", f"id: {stem}", "size: S"]
    if blocked_by:
        lines.append("blocked_by:")
        for b in blocked_by:
            lines.append(f"  - {b}")
    lines.extend(
        [
            "---",
            "",
            f"# {stem}",
            "",
            "## Context",
            "PRD: docs/prds/default.md",
            "",
            "## Task List",
            "1. Do something (traces: R-1).",
            "",
            "## Files to Modify",
            "- `src/widget.py` (new)",
            "",
            "## Validation Steps",
            "- [ ] test_widget_creation verifies widget.py",
            "",
            "---",
            "",
            "*Stage: plan-approved*",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_default_prd(plans_dir: Path):
    prds_dir = plans_dir.parent / "prds"
    prds_dir.mkdir(parents=True, exist_ok=True)
    (prds_dir / "default.md").write_text(
        "# Default PRD\n\n## Requirements\n- **R-1**: default\n", encoding="utf-8"
    )


def _git_init(root: Path):
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Test"],
        check=True,
    )
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", "initial"],
        check=True,
    )


def _write_queue_file(queue_file: Path, tasks: list[dict]) -> None:
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text(json.dumps({"tasks": tasks}), encoding="utf-8")


class TestBoardMembershipFromExplicitRecord(unittest.TestCase):
    """Board membership is the explicit queue record, never frontmatter status."""

    def test_sync_preserves_explicit_members_regardless_of_status(self):
        """sync does not remove tasks based on frontmatter status changes."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans_dir = root / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            _write_default_prd(plans_dir)
            _git_init(root)
            queued_plan = _write_plan(plans_dir, "queued")
            draft_plan = _write_plan(plans_dir, "draft")
            # Inject a stale status line into one plan; membership is still explicit.
            content = draft_plan.read_text(encoding="utf-8")
            draft_plan.write_text(content.replace("---\n", "---\nstatus: draft\n", 1))

            queue_file = root / ".agents" / "work-queue.json"
            history_file = root / ".agents" / "work-history.jsonl"
            _write_queue_file(
                queue_file,
                [
                    {
                        "id": "queued",
                        "title": "Queued",
                        "plan_file": str(queued_plan),
                        "blocked_by": [],
                        "blocks": [],
                        "state": "ready",
                    },
                    {
                        "id": "draft",
                        "title": "Draft",
                        "plan_file": str(draft_plan),
                        "blocked_by": [],
                        "blocks": [],
                        "state": "ready",
                    },
                ],
            )

            with patch.object(
                sys,
                "argv",
                [
                    "sync",
                    "--queue-file",
                    str(queue_file),
                    "--history-file",
                    str(history_file),
                    "--plans-dir",
                    str(plans_dir),
                ],
            ):
                rc = sync_cmd.main()

            self.assertEqual(rc, 0)
            data = json.loads(queue_file.read_text(encoding="utf-8"))
            ids = {t["id"] for t in data.get("tasks", [])}
            self.assertEqual(ids, {"queued", "draft"})


if __name__ == "__main__":
    unittest.main()
