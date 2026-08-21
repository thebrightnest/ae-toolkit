"""Tests for the flat single-hop ``aet --help`` index."""

from __future__ import annotations

import sys

import click
import pytest
import typer.core as typer_core
import typer.main as typer_main

from aet.cli.help_index import (
    SECTIONS,
    LeafCommand,
    _render_plain,
    _walk_commands,
    render_help_index,
    resolve_section,
    walk_leaf_commands,
)
from aet.cli.main import app
from tests.cli._helpers import run_typer

# Baseline from the PRD: three sequential help hops totalled 8,244 bytes.
_BASELINE_BYTES = 8244
_BOX_DRAWING = set("│─┌┐└┘╭╮╰╯")


@pytest.fixture
def leaves() -> list[LeafCommand]:
    return list(walk_leaf_commands(app))


@pytest.fixture
def leaves_by_name(leaves: list[LeafCommand]) -> dict[str, LeafCommand]:
    return {leaf.name: leaf for leaf in leaves}


def _is_runnable_group(cmd: click.Command) -> bool:
    """Return True when *cmd* is a group with no subcommands but a callback."""
    return (
        isinstance(cmd, (click.Group, typer_core.TyperGroup))
        and not getattr(cmd, "commands", {})
        and cmd.callback is not None
    )


def _expected_leaf_paths() -> set[tuple[str, ...]]:
    """Build the expected set of leaf command paths from the raw tree walk."""
    group = typer_main.get_group(app)
    expected: set[tuple[str, ...]] = set()
    for path, cmd in _walk_commands(group, ("aet",)):
        if isinstance(cmd, (click.Group, typer_core.TyperGroup)):
            if not getattr(cmd, "commands", {}):
                if cmd.callback is not None:
                    expected.add(path)
        else:
            expected.add(path)
    return expected


def test_walk_leaf_commands_covers_full_tree(leaves: list[LeafCommand]) -> None:
    """Every runnable leaf in the Typer tree appears in the flat index."""
    actual = {leaf.path for leaf in leaves}
    expected = _expected_leaf_paths()
    assert actual == expected, f"missing: {expected - actual}, extra: {actual - expected}"


def test_walk_leaf_commands_includes_required_arguments(leaves_by_name: dict[str, LeafCommand]) -> None:
    """Required positional arguments are captured inline; options are excluded."""
    assert leaves_by_name["sprint add"].args == ("target",)
    assert leaves_by_name["run-one"].args == ("plan_file",)
    assert leaves_by_name["ship gate"].args == ("plan",)
    assert leaves_by_name["state transition"].args == ("task_id", "from_stage", "to_stage")


def test_walk_leaf_commands_excludes_options(leaves_by_name: dict[str, LeafCommand]) -> None:
    """Options like ``--queue-file`` are not treated as required arguments."""
    assert "queue_file" not in leaves_by_name["sprint add"].args
    assert "--queue-file" not in leaves_by_name["sprint add"].args
    assert leaves_by_name["docs lint"].args == ()


def test_every_leaf_command_resolves_to_exactly_one_section(leaves: list[LeafCommand]) -> None:
    """The static section map covers every top-level name without overlap."""
    seen: dict[str, str] = {}
    for leaf in leaves:
        section = resolve_section(leaf.path)
        assert section in SECTIONS.values()
        top = leaf.path[1]
        if top in seen:
            assert seen[top] == section, f"{top} mapped to multiple sections"
        else:
            seen[top] = section
    # Every mapped top-level name produced at least one leaf.
    assert seen.keys() == set(SECTIONS.keys())


def test_render_plain_contains_sections_and_commands(leaves: list[LeafCommand]) -> None:
    """Plain-text output groups commands under their section headings."""
    text = _render_plain(leaves)
    assert "Plan work" in text
    assert "Run work" in text
    assert "Ship work" in text
    assert "Inspect & learn" in text
    assert "Set up & maintain" in text
    assert "sprint add <target>" in text
    assert "run-one <plan_file>" in text
    assert "ship gate <plan>" in text
    assert "configure" in text


def test_render_plain_has_no_box_drawing_characters(leaves: list[LeafCommand]) -> None:
    """Non-TTY help contains no decorative box-drawing characters."""
    text = _render_plain(leaves)
    found = _BOX_DRAWING & set(text)
    assert not found, f"found box-drawing characters: {sorted(found)}"


def test_cli_help_renders_flat_index() -> None:
    """``aet --help`` returns the flat index with sections."""
    result = run_typer(app, ["--help"])
    assert result.exit_code == 0, result.output
    assert "Plan work" in result.output
    assert "Run work" in result.output
    assert "Ship work" in result.output
    assert "Inspect & learn" in result.output
    assert "Set up & maintain" in result.output
    assert "sprint add <target>" in result.output


def test_cli_help_non_tty_has_no_box_drawing() -> None:
    """CliRunner output (non-TTY by construction) has no box-drawing chars."""
    result = run_typer(app, ["--help"])
    assert result.exit_code == 0, result.output
    found = _BOX_DRAWING & set(result.output)
    assert not found, f"found box-drawing characters: {sorted(found)}"


def test_cli_no_args_shows_help_index() -> None:
    """Invoking ``aet`` with no arguments shows the flat help index (exit 2)."""
    result = run_typer(app, [])
    assert result.exit_code == 2, result.output
    assert "Usage:" in result.output
    assert "Commands:" in result.output
    assert "Plan work" in result.output


def test_render_help_index_uses_plain_for_non_tty(
    monkeypatch, capsys, leaves: list[LeafCommand]
) -> None:
    """``render_help_index`` writes plain text when stdout is not a terminal."""
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    render_help_index(app)
    captured = capsys.readouterr()
    assert "Plan work" in captured.out
    assert not (_BOX_DRAWING & set(captured.out))


def test_cli_subcommand_help_unchanged() -> None:
    """Subcommand ``--help`` still renders through Typer's normal formatter."""
    result = run_typer(app, ["run", "--help"])
    assert result.exit_code == 0, result.output
    assert "Usage:" in result.output
    # Typer's default help uses box-drawing; CliRunner is non-TTY, so this
    # confirms the top-level change did not bleed into subcommand rendering.
    assert "╭─ Options ─────────────────────────────────" in result.output


def test_help_byte_count_recorded_and_below_baseline() -> None:
    """The new single-hop help is smaller than the old three-hop baseline."""
    result = run_typer(app, ["--help"])
    assert result.exit_code == 0, result.output
    size = len(result.output.encode("utf-8"))
    print(
        f"help-byte-count: before={_BASELINE_BYTES} bytes/3 hops, "
        f"after={size} bytes/1 hop"
    )
    assert size < _BASELINE_BYTES, (
        f"help output grew to {size} bytes, exceeding baseline {_BASELINE_BYTES}"
    )
