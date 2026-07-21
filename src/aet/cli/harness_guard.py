#!/usr/bin/env python3
"""aet harness-guard — detect the active harness and install a per-provider merge guard."""

from __future__ import annotations

import typer

from aet import harness_guard

app = typer.Typer()


@app.command("install")
def install_harness_guard() -> None:
    """Detect the harness and generate the matching merge guard."""
    raise typer.Exit(harness_guard.main(["install"]))


@app.command("check")
def check_harness_guard() -> None:
    """Report which merge guard is installed for the detected harness."""
    raise typer.Exit(harness_guard.main(["check"]))


if __name__ == "__main__":
    app()
