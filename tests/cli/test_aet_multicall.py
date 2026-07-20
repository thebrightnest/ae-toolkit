"""Tests for nested dispatch through the aet multicall dispatcher.

The dispatcher treats command groups (`aet state <sub>`, `aet sprint <sub>`,
`aet backlog <sub>`) as opaque forward targets: validation of the nested
subcommand happens in the target binary's argparse parser, not in the
dispatcher. These tests verify that forwarding is faithful.
"""

import importlib.machinery
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).parents[2]
_AET_PY = _REPO_ROOT / "aet-work" / "bin" / "aet"

_aet_spec = importlib.util.spec_from_loader(
    "aet_dispatcher",
    importlib.machinery.SourceFileLoader("aet_dispatcher", str(_AET_PY)),
)
aet = importlib.util.module_from_spec(_aet_spec)
_aet_spec.loader.exec_module(aet)


class _IsolatedBinDir(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.bin_dir = Path(self._tmp.name) / "bin"

    def _bin_env(self):
        return patch.dict(os.environ, {"AET_BIN_DIR": str(self.bin_dir)})


class TestNestedCommandGroupDispatch(_IsolatedBinDir):
    """Command groups forward the full argv to their target binary."""

    def _capture_exec(self, argv):
        captured = {}

        def mock_execvp(path, exec_argv):
            captured["path"] = path
            captured["argv"] = exec_argv
            raise SystemExit(0)

        with patch.object(sys, "argv", argv):
            with self._bin_env():
                with patch.object(aet.os, "execvp", mock_execvp):
                    rc = aet.main()
        return rc, captured.get("path"), captured.get("argv")

    def test_sprint_add_forwards_to_sprint_binary(self):
        rc, path, argv = self._capture_exec(
            ["aet", "sprint", "add", "docs/plans/feat-001.md"]
        )
        self.assertEqual(rc, 0)
        self.assertEqual(Path(path), Path(sys.executable))
        self.assertEqual(
            argv,
            [
                sys.executable,
                str(_REPO_ROOT / "src" / "aet" / "cli" / "sprint.py"),
                "add",
                "docs/plans/feat-001.md",
            ],
        )

    def test_backlog_add_forwards_to_backlog_binary(self):
        rc, path, argv = self._capture_exec(
            ["aet", "backlog", "add", "docs/plans/feat-001.md"]
        )
        self.assertEqual(rc, 0)
        self.assertEqual(Path(path), Path(sys.executable))
        self.assertEqual(
            argv,
            [
                sys.executable,
                str(_REPO_ROOT / "src" / "aet" / "cli" / "backlog.py"),
                "add",
                "docs/plans/feat-001.md",
            ],
        )

    def test_sprint_with_flags_forwards_verbatim(self):
        rc, path, argv = self._capture_exec(
            [
                "aet",
                "sprint",
                "add",
                "--queue-file",
                "q.json",
                "feat-001",
            ]
        )
        self.assertEqual(rc, 0)
        self.assertEqual(Path(path), Path(sys.executable))
        self.assertEqual(
            argv,
            [
                sys.executable,
                str(_REPO_ROOT / "src" / "aet" / "cli" / "sprint.py"),
                "add",
                "--queue-file",
                "q.json",
                "feat-001",
            ],
        )

    def test_state_audit_still_forwards_verbatim(self):
        """The existing `aet state <sub>` nesting remains intact."""
        rc, path, argv = self._capture_exec(["aet", "state", "audit", "q.json"])
        self.assertEqual(rc, 0)
        self.assertEqual(Path(path), Path(sys.executable))
        self.assertEqual(
            argv,
            [
                sys.executable,
                str(_REPO_ROOT / "src" / "aet" / "cli" / "aet-state.py"),
                "audit",
                "q.json",
            ],
        )


if __name__ == "__main__":
    unittest.main()
