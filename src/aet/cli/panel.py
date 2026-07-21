#!/usr/bin/env python3
"""CLI entry point for `aet panel`."""

from __future__ import annotations

import typer

from aet.panel.serve import main as panel_main

app = typer.Typer(invoke_without_command=True)


@app.callback()
def panel() -> None:
    """Launch the AET panel server."""
    raise typer.Exit(panel_main())


def main(argv: list[str] | None = None) -> int:
    try:
        return app(argv or [], standalone_mode=False)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0


if __name__ == "__main__":
    app()
