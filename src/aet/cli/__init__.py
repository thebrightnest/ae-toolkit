"""aet.cli — package entry point for the AE Toolkit Typer CLI.

The CLI has been consolidated into ``src/aet/cli/main.py`` as a single Typer
application. This package re-exports the public entry point so the installed
console script (``aet = "aet.cli:main"``) and import-time tooling both resolve
to the same source of truth.
"""

from __future__ import annotations

from aet.cli.main import app, main

__all__ = ["app", "main"]
