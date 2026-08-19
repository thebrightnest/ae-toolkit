"""Tests for intake-gate wiring: every queue door runs the plan_validate suite."""

from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path

from tests.cli._helpers import run_typer

aet = importlib.import_module("aet.cli.main")


def _write_json_file(data) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        return f.name


def _make_history(tasks: list[dict]) -> str:
    path = Path(tempfile.mkstemp(suffix=".jsonl")[1])
    with open(path, "w", encoding="utf-8") as f:
        for task in tasks:
            json.dump(task, f)
            f.write("\n")
    return str(path)


def _make_plan(
    plans_dir: Path,
    name: str,
    *,
    frontmatter: dict | None = None,
    body: str = "",
    footer_stage: str = "plan-approved",
) -> Path:
    """Write a plan markdown file with customizable frontmatter and body."""
    path = plans_dir / name
    data = {"id": Path(name).stem, "size": "S", "status": "queued"}
    data.update(frontmatter or {})
    lines = ["---"]
    for key, value in data.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {value}")
    lines.extend(["---", "", f"# Plan: {name}"])
    if body:
        lines.extend(["", body])
    lines.extend(["", "---", "", f"*Stage: {footer_stage}*"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _make_prd(prds_dir: Path, name: str, rids: list[str]) -> Path:
    """Write a PRD with a Requirements section containing the given R-ids."""
    path = prds_dir / name
    lines = [f"# PRD: {path.stem}"]
    if rids:
        lines.append("## Requirements")
        for rid in rids:
            lines.append(f"- **{rid}**: description of {rid}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _make_clean_plan(
    plans_dir: Path,
    prds_dir: Path,
    name: str,
    *,
    frontmatter: dict | None = None,
    extra_body: str = "",
    footer_stage: str = "plan-approved",
) -> Path:
    """Write a plan that passes the full plan_validate suite."""
    prd_name = "prd.md"
    _make_prd(prds_dir, prd_name, ["R-1"])
    body = (
        "## Context\n"
        f"PRD: docs/prds/{prd_name}\n"
        "\n"
        "## Task List\n"
        "1. Do something (traces: R-1)\n"
        "\n"
        "## Files to Modify\n"
        "- `src/widget.py` (new)\n"
        "\n"
        "## Validation Steps\n"
        "- [ ] test_widget_creation verifies widget.py\n"
    )
    if extra_body:
        body += "\n" + extra_body + "\n"
    return _make_plan(
        plans_dir,
        name,
        frontmatter=frontmatter,
        body=body,
        footer_stage=footer_stage,
    )


class TestAddIntakeGate(unittest.TestCase):
    def test_add_rejects_failing_unacked_plan_queue_unmutated(self):
        """A plan failing the validate suite with no ack is refused and the queue is untouched."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans_dir = root / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            # Missing id is a structural failure.
            bad = plans_dir / "bad.md"
            bad.write_text(
                "---\nsize: S\n---\n\n# Bad\n\n---\n\n_Stage: plan-approved_\n",
                encoding="utf-8",
            )
            queue_file = _write_json_file([])
            history_file = _make_history([])

            result = run_typer(aet.app, [
                "sprint",
                "add",
                str(bad),
                "--queue-file", queue_file,
                "--history-file", history_file,
                "--plans-dir", str(plans_dir),
            ])

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("missing id", result.stderr.lower())
            with open(queue_file, "r", encoding="utf-8") as f:
                self.assertEqual(json.load(f), [])

    def test_add_admits_clean_plan(self):
        """A clean plan is admitted exactly as before."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans_dir = root / "docs" / "plans"
            prds_dir = root / "docs" / "prds"
            plans_dir.mkdir(parents=True)
            prds_dir.mkdir(parents=True)
            plan = _make_clean_plan(plans_dir, prds_dir, "good.md")
            queue_file = _write_json_file([])
            history_file = _make_history([])

            result = run_typer(aet.app, [
                "sprint",
                "add",
                str(plan),
                "--queue-file", queue_file,
                "--history-file", history_file,
                "--plans-dir", str(plans_dir),
            ])

            self.assertEqual(result.exit_code, 0)
            with open(queue_file, "r", encoding="utf-8") as f:
                queue = json.load(f)
            self.assertEqual(len(queue), 1)
            self.assertEqual(queue[0]["id"], "good")

    def test_add_admits_fully_acked_plan(self):
        """A plan with failures is admitted when every failure is explicitly acked."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans_dir = root / "docs" / "plans"
            prds_dir = root / "docs" / "prds"
            plans_dir.mkdir(parents=True)
            prds_dir.mkdir(parents=True)
            # Multiple Phase sections is a structural failure; ack it. The plan
            # is otherwise clean so only the acked structural failure remains.
            plan = _make_clean_plan(
                plans_dir,
                prds_dir,
                "acked.md",
                extra_body=(
                    "## Phase One\n\n## Phase Two\n\n"
                    "⚠️ VALIDATE ACK: structural — intentional multi-phase spike\n"
                ),
            )
            queue_file = _write_json_file([])
            history_file = _make_history([])

            result = run_typer(aet.app, [
                "sprint",
                "add",
                str(plan),
                "--queue-file", queue_file,
                "--history-file", history_file,
                "--plans-dir", str(plans_dir),
            ])

            self.assertEqual(result.exit_code, 0)
            with open(queue_file, "r", encoding="utf-8") as f:
                queue = json.load(f)
            self.assertEqual(len(queue), 1)
            self.assertEqual(queue[0]["id"], "acked")

    def test_add_partially_acked_plan_still_rejected(self):
        """A plan with unacked failures is rejected even if some failures are acked."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans_dir = root / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            # Missing id (unacked) + multi-phase (acked).
            plan = plans_dir / "partial.md"
            plan.write_text(
                "---\nsize: S\n---\n\n# Partial\n\n## Phase One\n\n## Phase Two\n\n"
                "⚠️ VALIDATE ACK: structural — acked reason\n\n---\n\n_Stage: plan-approved_\n",
                encoding="utf-8",
            )
            queue_file = _write_json_file([])
            history_file = _make_history([])

            result = run_typer(aet.app, [
                "sprint",
                "add",
                str(plan),
                "--queue-file", queue_file,
                "--history-file", history_file,
                "--plans-dir", str(plans_dir),
            ])

            self.assertNotEqual(result.exit_code, 0)
            stderr_text = result.stderr.lower()
            self.assertIn("intake validation failed", stderr_text)
            # The structural failure is acked; the rtrace failure is not.
            self.assertIn("rtrace", stderr_text)

    def test_add_rejects_invalid_work_class(self):
        """An invalid work_class is rejected at the add intake door (R-7)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans_dir = root / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            plan = _make_plan(
                plans_dir, "bad-class.md", frontmatter={"work_class": "urgent"}
            )
            queue_file = _write_json_file([])
            history_file = _make_history([])

            result = run_typer(aet.app, [
                "sprint",
                "add",
                str(plan),
                "--queue-file", queue_file,
                "--history-file", history_file,
                "--plans-dir", str(plans_dir),
            ])

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("work_class", result.stderr)
            with open(queue_file, "r", encoding="utf-8") as f:
                self.assertEqual(json.load(f), [])

    def test_validate_runs_before_any_mutation(self):
        """When add fails validation, the queue file is byte-identical afterward."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plans_dir = root / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            bad = plans_dir / "bad.md"
            bad.write_text("---\nsize: S\n---\n\n# Bad\n", encoding="utf-8")
            queue_file = _write_json_file([{"id": "existing", "state": "ready"}])
            original_bytes = Path(queue_file).read_bytes()
            history_file = _make_history([])

            result = run_typer(aet.app, [
                "sprint",
                "add",
                str(bad),
                "--queue-file", queue_file,
                "--history-file", history_file,
                "--plans-dir", str(plans_dir),
            ])

            self.assertNotEqual(result.exit_code, 0)
            self.assertEqual(Path(queue_file).read_bytes(), original_bytes)


if __name__ == "__main__":
    unittest.main()
