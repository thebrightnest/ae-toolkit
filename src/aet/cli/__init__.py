"""aet.cli — package entry point for the AE Toolkit multicall dispatcher.

The dispatcher executable has been extracted from ``aet-work/bin/aet`` into
``src/aet/cli/main.py``. This package re-exports its public interface so the
installed console script (``aet = "aet.cli:main"``) and import-time tooling
both resolve to the same source of truth.
"""

from __future__ import annotations

from aet.cli.main import LEGACY_NAMES, SUBCOMMANDS, main

__all__ = ["main", "SUBCOMMANDS", "LEGACY_NAMES"]
