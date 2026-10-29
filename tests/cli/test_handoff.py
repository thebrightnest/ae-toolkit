"""Integration tests for the ``aet handoff`` CLI group."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from aet.cli import handoff as handoff_cli
from tests.cli._helpers import run_typer


class TestHandoffAppend:
    def test_append_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_typer(
                handoff_cli.app,
                [
                    "append",
                    "--run-id",
                    "run-20260810-093000-abcd1234",
                    "--stage",
                    "plan-approved",
                    "--decision",
                    "use JSON",
                    "--pre-existing-failure",
                    "flaky test",
                    "--validation-command",
                    "make test",
                    "--evidence-path",
                    "/path/to/evidence.json",
                ],
                cwd=tmp,
            )
            assert result.exit_code == 0
            path = Path(tmp) / ".agents" / "runs" / "run-20260810-093000-abcd1234" / "handoff.json"
            assert path.exists()
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data["schema_version"] == 2
            assert data["run_id"] == "run-20260810-093000-abcd1234"
            assert len(data["entries"]) == 1
            entry = data["entries"][0]
            assert entry["stage"] == "plan-approved"
            assert entry["task_id"] is None
            assert entry["decisions"] == ["use JSON"]
            assert entry["pre_existing_failures"] == ["flaky test"]
            assert entry["validation_commands"] == ["make test"]
            assert entry["evidence_path"] == "/path/to/evidence.json"
            assert "recorded_at" in entry

    def test_append_with_explicit_task_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_typer(
                handoff_cli.app,
                [
                    "append",
                    "--run-id",
                    "run-task-opt",
                    "--stage",
                    "plan-approved",
                    "--task",
                    "task-123",
                    "--decision",
                    "d",
                ],
                cwd=tmp,
            )
            assert result.exit_code == 0
            path = Path(tmp) / ".agents" / "runs" / "run-task-opt" / "handoff.json"
            assert path.exists()
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data["entries"][0]["task_id"] == "task-123"

    def test_append_with_env_task_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_typer(
                handoff_cli.app,
                [
                    "append",
                    "--run-id",
                    "run-task-env",
                    "--stage",
                    "plan-approved",
                    "--decision",
                    "d",
                ],
                cwd=tmp,
                env={"AET_TASK_ID": "task-env-456"},
            )
            assert result.exit_code == 0
            path = Path(tmp) / ".agents" / "runs" / "run-task-env" / "handoff.json"
            assert path.exists()
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data["entries"][0]["task_id"] == "task-env-456"

    def test_env_run_id_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_typer(
                handoff_cli.app,
                ["append", "--stage", "implemented", "--decision", "d"],
                cwd=tmp,
                env={"AET_RUN_ID": "run-env"},
            )
            assert result.exit_code == 0
            path = Path(tmp) / ".agents" / "runs" / "run-env" / "handoff.json"
            assert path.exists()

    def test_missing_run_id_exits_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_typer(
                handoff_cli.app,
                ["append", "--stage", "plan-approved", "--decision", "d"],
                cwd=tmp,
                env={"AET_RUN_ID": None},
            )
            assert result.exit_code == 1
            assert "--run-id" in result.output or "AET_RUN_ID" in result.output

    def test_missing_fields_exits_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_typer(
                handoff_cli.app,
                [
                    "append",
                    "--run-id",
                    "run-x",
                    "--stage",
                    "plan-approved",
                ],
                cwd=tmp,
            )
            assert result.exit_code == 1
            assert "at least one" in result.output.lower()


class TestHandoffShow:
    def test_show_renders_prompt_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_typer(
                handoff_cli.app,
                [
                    "append",
                    "--run-id",
                    "run-show",
                    "--stage",
                    "plan-approved",
                    "--decision",
                    "d1",
                    "--validation-command",
                    "make test",
                ],
                cwd=tmp,
            )
            result = run_typer(
                handoff_cli.app,
                ["show", "--run-id", "run-show"],
                cwd=tmp,
            )
            assert result.exit_code == 0
            assert "Run handoff note" in result.output
            assert "[stage: plan-approved]" in result.output
            assert "decisions: d1" in result.output
            assert "validation commands: make test" in result.output

    def test_show_filters_by_task_flag_and_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_typer(
                handoff_cli.app,
                [
                    "append",
                    "--run-id",
                    "run-filter",
                    "--stage",
                    "plan-approved",
                    "--task",
                    "task-A",
                    "--decision",
                    "decision A",
                ],
                cwd=tmp,
            )
            run_typer(
                handoff_cli.app,
                [
                    "append",
                    "--run-id",
                    "run-filter",
                    "--stage",
                    "implemented",
                    "--task",
                    "task-B",
                    "--decision",
                    "decision B",
                ],
                cwd=tmp,
            )

            # Explicit --task filters
            res_a = run_typer(
                handoff_cli.app,
                ["show", "--run-id", "run-filter", "--task", "task-A"],
                cwd=tmp,
            )
            assert res_a.exit_code == 0
            assert "decision A" in res_a.output
            assert "decision B" not in res_a.output

            # Env AET_TASK_ID filters
            res_b = run_typer(
                handoff_cli.app,
                ["show", "--run-id", "run-filter"],
                cwd=tmp,
                env={"AET_TASK_ID": "task-B"},
            )
            assert res_b.exit_code == 0
            assert "decision B" in res_b.output
            assert "decision A" not in res_b.output

            # Unset task renders all entries
            res_all = run_typer(
                handoff_cli.app,
                ["show", "--run-id", "run-filter"],
                cwd=tmp,
                env={"AET_TASK_ID": None},
            )
            assert res_all.exit_code == 0
            assert "decision A" in res_all.output
            assert "decision B" in res_all.output
