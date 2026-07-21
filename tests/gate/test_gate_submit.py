"""Tests for src/aet/cli/gate.py — the fail-closed gate verdict writer."""

from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).parents[2]
_GATE_BIN = _REPO_ROOT / "src" / "aet" / "cli" / "gate.py"
_AET_BIN = _REPO_ROOT / "src" / "aet" / "cli" / "main.py"

_gate_spec = importlib.util.spec_from_loader(
    "gate_bin", importlib.machinery.SourceFileLoader("gate_bin", str(_GATE_BIN))
)
gate = importlib.util.module_from_spec(_gate_spec)
sys.modules["gate_bin"] = gate
_gate_spec.loader.exec_module(gate)


def _qa_payload(**overrides) -> dict:
    record = {
        "task_id": "ewl-01-gate-submit-cli",
        "stage": "qa-complete",
        "skill": "aet-qa",
        "verdict": "pass",
        "summary": "All checks passed",
        "generated_at": "2026-07-13T00:00:00Z",
        "tree_hash": "t0",
        "test_command": "pytest tests/ -q",
        "tests_total": 10,
        "tests_passed": 10,
        "tests_failed": 0,
    }
    record.update(overrides)
    return record


class TestGateSubmit(unittest.TestCase):
    """gate submit validates and writes verdicts through the public CLI."""

    def _run(self, argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            rc = gate.main(argv)
        return rc, stdout.getvalue(), stderr.getvalue()

    @staticmethod
    def _write_payload(tmp: Path, record: dict) -> Path:
        payload = tmp / "payload.json"
        payload.write_text(json.dumps(record), encoding="utf-8")
        return payload

    def test_submit_writes_valid_verdict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            dest = tmp / "verdicts" / "qa.json"
            payload = self._write_payload(tmp, _qa_payload())
            with patch.dict(os.environ, {"AET_EVIDENCE_PATH": str(dest)}, clear=True):
                rc, _out, err = self._run(
                    [
                        "submit",
                        "--stage",
                        "qa",
                        "--verdict",
                        "pass",
                        "--evidence",
                        str(payload),
                    ]
                )
            self.assertEqual(rc, 0, err)
            self.assertTrue(dest.is_file(), "verdict file was not written")
            written = json.loads(dest.read_text(encoding="utf-8"))
            self.assertEqual(written["verdict"], "pass")
            self.assertEqual(written["task_id"], "ewl-01-gate-submit-cli")

    def test_missing_verdict_flag_exits_nonzero(self):
        rc, _out, err = self._run(
            ["submit", "--stage", "qa", "--evidence", "payload.json"]
        )
        self.assertEqual(rc, 2)
        self.assertIn("--verdict", err)

    def test_missing_evidence_flag_exits_nonzero(self):
        rc, _out, err = self._run(["submit", "--stage", "qa", "--verdict", "pass"])
        self.assertEqual(rc, 2)
        self.assertIn("--evidence", err)

    def test_evidence_file_not_found_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "missing.json"
            rc, _out, err = self._run(
                [
                    "submit",
                    "--stage",
                    "qa",
                    "--verdict",
                    "pass",
                    "--evidence",
                    str(missing),
                ]
            )
        self.assertEqual(rc, 1)
        self.assertIn("not found", err)

    def test_schema_invalid_payload_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            payload = self._write_payload(tmp, {"task_id": "t", "verdict": "pass"})
            rc, _out, err = self._run(
                [
                    "submit",
                    "--stage",
                    "qa",
                    "--verdict",
                    "pass",
                    "--evidence",
                    str(payload),
                ]
            )
        self.assertEqual(rc, 1)
        self.assertIn("invalid", err)

    def test_malformed_json_payload_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            payload = tmp / "payload.json"
            payload.write_text("{not json", encoding="utf-8")
            rc, _out, err = self._run(
                [
                    "submit",
                    "--stage",
                    "qa",
                    "--verdict",
                    "pass",
                    "--evidence",
                    str(payload),
                ]
            )
        self.assertEqual(rc, 1)
        self.assertIn("not valid JSON", err)

    def test_non_object_payload_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            payload = tmp / "payload.json"
            payload.write_text('["qa", "pass"]', encoding="utf-8")
            rc, _out, err = self._run(
                [
                    "submit",
                    "--stage",
                    "qa",
                    "--verdict",
                    "pass",
                    "--evidence",
                    str(payload),
                ]
            )
        self.assertEqual(rc, 1)
        self.assertIn("JSON object", err)

    def test_unknown_stage_exits_nonzero(self):
        rc, _out, err = self._run(
            ["submit", "--stage", "nope", "--verdict", "pass", "--evidence", "x.json"]
        )
        self.assertEqual(rc, 1)
        self.assertIn("unknown stage", err)

    def test_verdict_mismatch_exits_nonzero(self):
        """--verdict must match the payload's verdict field (no silent override)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            dest = tmp / "qa.json"
            payload = self._write_payload(tmp, _qa_payload(verdict="fail"))
            with patch.dict(os.environ, {"AET_EVIDENCE_PATH": str(dest)}, clear=True):
                rc, _out, err = self._run(
                    [
                        "submit",
                        "--stage",
                        "qa",
                        "--verdict",
                        "pass",
                        "--evidence",
                        str(payload),
                    ]
                )
            self.assertEqual(rc, 1)
            self.assertIn("does not match", err)
            self.assertFalse(dest.exists(), "mismatched verdict must not be written")

    def test_submit_stamps_tree_hash_when_absent(self):
        """Payloads following the skill writer contract (no tree_hash) are accepted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            dest = tmp / "qa.json"
            record = _qa_payload()
            del record["tree_hash"]
            payload = self._write_payload(tmp, record)
            with patch.dict(os.environ, {"AET_EVIDENCE_PATH": str(dest)}, clear=True):
                rc, _out, err = self._run(
                    [
                        "submit",
                        "--stage",
                        "qa",
                        "--verdict",
                        "pass",
                        "--evidence",
                        str(payload),
                    ]
                )
            self.assertEqual(rc, 0, err)
            self.assertTrue(dest.is_file(), "verdict file was not written")
            written = json.loads(dest.read_text(encoding="utf-8"))
            self.assertIn("tree_hash", written)
            self.assertNotEqual(written["tree_hash"], "")

    def test_submit_preserves_explicit_tree_hash(self):
        """An explicit tree_hash supplied by the caller is not overwritten."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            dest = tmp / "qa.json"
            payload = self._write_payload(tmp, _qa_payload(tree_hash="abc123"))
            with patch.dict(os.environ, {"AET_EVIDENCE_PATH": str(dest)}, clear=True):
                rc, _out, err = self._run(
                    [
                        "submit",
                        "--stage",
                        "qa",
                        "--verdict",
                        "pass",
                        "--evidence",
                        str(payload),
                    ]
                )
            self.assertEqual(rc, 0, err)
            written = json.loads(dest.read_text(encoding="utf-8"))
            self.assertEqual(written["tree_hash"], "abc123")


class TestGateDispatcherRouting(unittest.TestCase):
    """`aet gate submit` reaches src/aet/cli/gate.py through the dispatcher."""

    def test_gate_submit_routed_through_aet_dispatcher(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            dest = tmp / "qa.json"
            payload = tmp / "payload.json"
            payload.write_text(json.dumps(_qa_payload()), encoding="utf-8")
            env = {
                "PATH": os.environ["PATH"],
                "AET_EVIDENCE_PATH": str(dest),
                "AET_BIN_DIR": str(tmp / "aet-bin"),
                "AET_TELEMETRY_ARCHIVE_DIR": str(tmp / "telemetry"),
            }
            result = subprocess.run(
                [
                    sys.executable,
                    str(_AET_BIN),
                    "gate",
                    "submit",
                    "--stage",
                    "qa",
                    "--verdict",
                    "pass",
                    "--evidence",
                    str(payload),
                ],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(dest.is_file(), result.stderr)
            written = json.loads(dest.read_text(encoding="utf-8"))
            self.assertEqual(written["verdict"], "pass")
