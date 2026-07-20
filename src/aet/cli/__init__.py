"""aet.cli — package entry point for the AE Toolkit multicall dispatcher.

The dispatcher executable remains at ``aet-work/bin/aet`` during the staged
package extraction.  This package re-exports its public interface so the
installed console script (``aet = "aet.cli:main"``) and import-time tooling
both resolve to the same source of truth.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_AET_DISPATCHER = _REPO_ROOT / "aet-work" / "bin" / "aet"

_spec = importlib.util.spec_from_loader(
    "aet._work_dispatcher",
    importlib.machinery.SourceFileLoader(
        "aet._work_dispatcher", str(_AET_DISPATCHER)
    ),
)
_work_dispatcher = importlib.util.module_from_spec(_spec)
sys.modules["aet._work_dispatcher"] = _work_dispatcher
_spec.loader.exec_module(_work_dispatcher)

main = _work_dispatcher.main
SUBCOMMANDS = _work_dispatcher.SUBCOMMANDS
LEGACY_NAMES = _work_dispatcher.LEGACY_NAMES

__all__ = ["main", "SUBCOMMANDS", "LEGACY_NAMES"]
