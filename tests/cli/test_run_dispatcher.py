"""Tests for the ``aet run`` / ``aet run-one`` dispatcher forwarding surface."""

from __future__ import annotations

import importlib
from unittest.mock import patch

from tests.cli._helpers import run_typer

aet = importlib.import_module("aet.cli.main")


class TestRunBaseForwarding:
    """``--base`` is forwarded to the orchestrator exactly as passed."""

    def test_run_forwards_base_to_orchestrator(self) -> None:
        with patch.object(aet, "_spawn_detached") as spawn:
            spawn.return_value = 0
            result = run_typer(aet.app, ["run", "--base", "feat/x"])

        assert result.exit_code == 0, result.output
        argv = spawn.call_args[0][0]
        assert "--base" in argv
        assert argv[argv.index("--base") + 1] == "feat/x"


class TestRunOneBaseForwarding:
    """``--base`` is forwarded for single-plan runs too."""

    def test_run_one_forwards_base_to_orchestrator(self) -> None:
        with patch.object(aet, "_spawn_detached") as spawn:
            spawn.return_value = 0
            result = run_typer(
                aet.app, ["run-one", "docs/plans/example.md", "--base", "feat/x"]
            )

        assert result.exit_code == 0, result.output
        argv = spawn.call_args[0][0]
        assert "--base" in argv
        assert argv[argv.index("--base") + 1] == "feat/x"
