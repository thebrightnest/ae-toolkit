"""Regression tests for retiring the bare ``ship`` entry point.

- No canonical doc or live SKILL.md references a bare ``ship`` invocation.
- ``aet ship close`` produces the same underlying call as the old positional
  ``ship <task_id> <plan_file>`` syntax.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).parents[1]
_REPO_SRC = _REPO_ROOT / "src"
if str(_REPO_SRC) not in sys.path:
    sys.path.insert(0, str(_REPO_SRC))

# Load src/aet/cli/ship.py as a module for dispatch parity testing.
_SHIP_PY = _REPO_ROOT / "src" / "aet" / "cli" / "ship.py"
_ship_spec = importlib.util.spec_from_loader(
    "aet_ship_legacy", importlib.machinery.SourceFileLoader("aet_ship_legacy", str(_SHIP_PY))
)
ship = importlib.util.module_from_spec(_ship_spec)
sys.modules["aet_ship_legacy"] = ship
_ship_spec.loader.exec_module(ship)


# Canonical command docs and live skill instructions that must not reference a
# standalone ``ship`` binary invocation.
_GREP_ROOTS = (
    _REPO_ROOT / ".agents" / "commands",
    _REPO_ROOT / "skills",
)

# Specific patterns that indicate a bare ``ship`` entry point is still being
# documented. Prose uses of "ship" as a verb ("ship it", "ship stage") and
# canonical ``aet ship <plan_file>`` invocations are deliberately not matched.
_BARE_SHIP_PATTERNS = (
    re.compile(r"~\s*/\.local/bin/ship\b"),
    re.compile(r"\bcommand\s+-v\s+ship\b"),
    re.compile(r"(?<!\baet[\s-])\bship\s+record-merge\b"),
    re.compile(r"(?<!\baet[\s-])\bship\s+<[-_\w]+>"),
    re.compile(r"(?<!\baet[\s-])`ship`"),
)


def _canonical_markdown_files() -> list[Path]:
    files: list[Path] = []
    for root in _GREP_ROOTS:
        if not root.is_dir():
            continue
        for path in root.rglob("*.md"):
            files.append(path)
    return files


class TestShipBareInvocationGrepGuard(unittest.TestCase):
    def test_no_canonical_doc_or_skill_references_bare_ship(self):
        """No canonical doc or live SKILL.md references a bare ``ship`` invocation."""
        offenders: list[str] = []
        for path in _canonical_markdown_files():
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                for pattern in _BARE_SHIP_PATTERNS:
                    if pattern.search(line):
                        offenders.append(f"{path}:{lineno}: {line.strip()}")
                        break
        if offenders:
            self.fail("Bare 'ship' invocations found in canonical docs/skills:\n" + "\n".join(offenders))


class TestShipCloseMatchesLegacyPositional(unittest.TestCase):
    def test_close_produces_same_record_merge_call_as_legacy_positional(self):
        """``aet ship close`` forwards the same namespace the old ``ship <tid> <plan>`` did."""
        captured: list[dict] = []

        def fake_record_merge(ns):
            captured.append(
                {
                    "command": ns.command,
                    "task_id": ns.task_id,
                    "plan": ns.plan,
                    "queue": ns.queue,
                    "dry_run": ns.dry_run,
                    "branch": ns.branch,
                    "merge_commit": ns.merge_commit,
                }
            )
            return 0

        with patch.object(ship.aet_state, "cmd_record_merge", side_effect=fake_record_merge):
            rc_close = ship.main(["close", "t1", "/path/to/plan.md", "/path/to/queue.json"])
            legacy_ns = ship.aet_state.argparse.Namespace(
                command="record-merge",
                task_id="t1",
                plan="/path/to/plan.md",
                queue="/path/to/queue.json",
                dry_run=False,
                branch=None,
                merge_commit=None,
            )
            rc_legacy = ship.cmd_ship(legacy_ns)

        self.assertEqual(rc_close, 0)
        self.assertEqual(rc_legacy, 0)
        self.assertEqual(len(captured), 2)
        self.assertEqual(captured[0], captured[1])


if __name__ == "__main__":
    unittest.main()
