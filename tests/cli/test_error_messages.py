"""CLI-boundary tests for teaching error messages."""

from __future__ import annotations

from aet.cli.main import app
from tests.cli._helpers import run_typer

_BOX_DRAWING = set("│─┌┐└┘╭╮╰╯")


def test_missing_argument_error_includes_runnable_example() -> None:
    """A missing required argument error names a working invocation."""
    result = run_typer(app, ["sprint", "add"])
    assert result.exit_code == 2, result.output
    assert "Missing argument 'target'" in result.output
    assert "Example: aet sprint add <target>" in result.output


def test_unknown_subcommand_error_keeps_suggestion_and_adds_example() -> None:
    """An unknown subcommand error preserves 'Did you mean' and gains an example."""
    result = run_typer(app, ["sprint", "ad"])
    assert result.exit_code == 2, result.output
    assert "No such command 'ad'" in result.output
    assert "Did you mean 'add'?" in result.output
    assert "Example: aet sprint add <target>" in result.output


def test_unknown_subcommand_without_suggestion_has_no_example() -> None:
    """When there is no close match, no example is appended."""
    result = run_typer(app, ["sprint", "xyz"])
    assert result.exit_code == 2, result.output
    assert "No such command 'xyz'" in result.output
    assert "Did you mean" not in result.output
    assert "Example:" not in result.output


def test_error_output_has_no_box_drawing_characters() -> None:
    """Non-TTY error output is plain text with no decorative characters."""
    result = run_typer(app, ["sprint", "add"])
    assert result.exit_code == 2, result.output
    found = _BOX_DRAWING & set(result.output)
    assert not found, f"found box-drawing characters: {sorted(found)}"
