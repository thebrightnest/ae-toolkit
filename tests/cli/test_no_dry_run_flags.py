"""Regression guard: mutating `aet ship`, `aet state`, and `aet setup` commands
execute directly and expose no `--dry-run` option (RDR-01)."""

from __future__ import annotations

import pytest
import typer.main

from aet.cli import aet_state, setup, ship

RETIRED = [
    (ship.app, "default"),
    (ship.app, "gate"),
    (ship.app, "open"),
    (ship.app, "open-epic"),
    (ship.app, "merge"),
    (ship.app, "split"),
    (ship.app, "close"),
    (aet_state.app, "reset"),
    (aet_state.app, "transition"),
    (aet_state.app, "set-stage"),
    (aet_state.app, "record-merge"),
    (setup.app, "link"),
    (setup.app, "skills"),
    (setup.app, "verify"),
]


@pytest.mark.parametrize(("app", "name"), RETIRED, ids=[n for _, n in RETIRED])
def test_command_has_no_dry_run_option(app, name):
    group = typer.main.get_command(app)
    command = group.commands[name]
    opts = {opt for param in command.params for opt in getattr(param, "opts", [])}
    assert "--dry-run" not in opts
