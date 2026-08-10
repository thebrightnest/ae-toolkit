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
            assert data["schema_version"] == 1
            assert data["run_id"] == "run-20260810-093000-abcd1234"
            assert len(data["entries"]) == 1
            entry = data["entries"][0]
            assert entry["stage"] == "plan-approved"
            assert entry["decisions"] == ["use JSON"]
            assert entry["pre_existing_failures"] == ["flaky test"]
            assert entry["validation_commands"] == ["make test"]
            assert entry["evidence_path"] == "/path/to/evidence.json"
            assert "recorded_at" in entry

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
