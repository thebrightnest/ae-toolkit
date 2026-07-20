"""Tests for the one-time plan frontmatter migration and queue rebuild."""

import importlib.machinery
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
MIGRATION_PY = REPO_ROOT / "scripts" / "archive" / "migrate-plans-to-frontmatter.py"

_spec = importlib.util.spec_from_loader(
    "migration", importlib.machinery.SourceFileLoader("migration", str(MIGRATION_PY))
)
migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration)


def write_plan(path: Path, body: str, frontmatter: str | None = None) -> None:
    """Write a plan file, optionally with a leading frontmatter block."""
    if frontmatter is not None:
        content = frontmatter.rstrip() + "\n\n" + body.lstrip("\n")
    else:
        content = body
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestInferBlockedBy(unittest.TestCase):
    """Inference behavior: recover, ignore intra-plan text, flag ambiguity."""

    def test_unambiguous_edge_recovered(self):
        """A markdown link to another plan file becomes a blocked_by edge."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans = root / "plans"
            plans.mkdir()
            write_plan(
                plans / "base.md",
                "# Base\n\n## Validation Steps\n- [ ] x\n",
            )
            write_plan(
                plans / "dependent.md",
                "# Dependent\n\n## Dependencies\n- [base](base.md)\n",
            )

            all_ids = {"base", "dependent"}
            ticket_map: dict[str, str] = {}
            inference = migration.infer_blocked_by(
                plans / "dependent.md", all_ids, ticket_map
            )

            self.assertEqual(inference["recovered"], ["base"])
            self.assertEqual(inference["unresolved"], [])
            self.assertEqual(inference["flagged"], [])

    def test_intra_plan_text_not_promoted_to_edge(self):
        """Task-list prose inside a plan is never promoted to an inter-plan edge."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans = root / "plans"
            plans.mkdir()
            write_plan(
                plans / "self-contained.md",
                (
                    "# Self-contained\n\n"
                    "## Dependencies\n- none\n\n"
                    "## Task List\n"
                    "- Task 1: build the parser\n"
                    "- Task 2: wire the UI (blocked by Task 1)\n"
                ),
            )

            all_ids = {"self-contained"}
            inference = migration.infer_blocked_by(
                plans / "self-contained.md", all_ids, {}
            )

            self.assertEqual(inference["recovered"], [])
            self.assertEqual(inference["flagged"], [])

    def test_ambiguous_dependency_flagged(self):
        """A line that matches multiple known ids is flagged, not guessed."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans = root / "plans"
            plans.mkdir()
            write_plan(plans / "auth-core.md", "# Auth Core\n")
            write_plan(plans / "auth-ui.md", "# Auth UI\n")
            write_plan(
                plans / "consumer.md",
                "# Consumer\n\n## Dependencies\n- auth-core or auth-ui\n",
            )

            all_ids = {"auth-core", "auth-ui", "consumer"}
            inference = migration.infer_blocked_by(
                plans / "consumer.md", all_ids, {}
            )

            self.assertEqual(inference["recovered"], [])
            self.assertTrue(
                any("ambiguous" in f for f in inference["flagged"]),
                f"expected an ambiguous flag, got {inference['flagged']}",
            )


class TestQueueRebuild(unittest.TestCase):
    """Driver mode: fail-closed validation and settled-history backfill."""

    def test_rebuilt_queue_validates_under_fail_closed_sync(self):
        """A plan with an unknown blocker prevents the queue from being written."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans = root / "plans"
            plans.mkdir()
            write_plan(
                plans / "good.md",
                "# Good\n",
                frontmatter="---\nid: good\nblocked_by: []\nsize: S\n---",
            )
            write_plan(
                plans / "bad.md",
                "# Bad\n",
                frontmatter="---\nid: bad\nblocked_by:\n  - missing-plan\nsize: M\n---",
            )
            queue_file = root / "work-queue.json"
            history_file = root / "work-history.jsonl"

            ok, report = migration.rebuild_queue(
                plans, queue_file, history_file, dry_run=False
            )

            self.assertFalse(ok, f"expected validation failure, got {report}")
            self.assertTrue(
                any("missing-plan" in err for err in report["errors"]),
                f"expected unknown-blocker error, got {report['errors']}",
            )
            self.assertFalse(queue_file.exists())

    def test_merged_work_backfilled_into_history_not_live(self):
        """Terminal tasks from the old queue are sealed to history, not live."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans = root / "plans"
            plans.mkdir()
            write_plan(
                plans / "old-done.md",
                "# Old Done\n",
                frontmatter="---\nid: old-done\nblocked_by: []\nsize: S\n---",
            )
            existing_queue = root / "existing-queue.json"
            existing_queue.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "id": "old-done",
                                "state": "merged",
                                "status": "merged",
                                "plan_file": str(plans / "old-done.md"),
                                "merge_commit": "abc1234",
                                "blocked_by": [],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            queue_file = root / "work-queue.json"
            history_file = root / "work-history.jsonl"

            ok, report = migration.rebuild_queue(
                plans,
                queue_file,
                history_file,
                existing_queue_file=existing_queue,
                dry_run=False,
            )

            self.assertTrue(ok, report)
            self.assertEqual(report["sealed_ids"], ["old-done"])

            with open(history_file, "r", encoding="utf-8") as f:
                history = [json.loads(line) for line in f if line.strip()]
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["id"], "old-done")

            with open(queue_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            live_ids = {t["id"] for t in data["tasks"]}
            self.assertNotIn("old-done", live_ids)


if __name__ == "__main__":
    unittest.main()
