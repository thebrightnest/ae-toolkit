"""Tests for the ``aet learnings append`` command."""

from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path

from tests.cli._helpers import run_typer

aet = importlib.import_module("aet.cli.main")


class TestLearningsAppend(unittest.TestCase):
    """Behavior-driven tests for appending canonical learning entries."""

    def _run_append(self, *extra_args: str) -> tuple[run_typer.Result, Path]:
        """Run ``aet learnings append`` against a temp file and return result + path."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = Path(f.name)
        path.write_text("", encoding="utf-8")
        argv = [
            "learnings",
            "append",
            "--file",
            str(path),
            *extra_args,
        ]
        return run_typer(aet.app, argv), path

    def test_append_writes_canonical_entry(self):
        """A minimal append produces the dominant timestamp-shaped JSONL entry."""
        result, path = self._run_append(
            "--problem", "p",
            "--layer", "l",
            "--fix", "f",
            "--prevents", "pr",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
        self.assertEqual(len(lines), 1)
        entry = json.loads(lines[0])
        self.assertIn("timestamp", entry)
        self.assertRegex(entry["timestamp"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
        self.assertEqual(entry["problem"], "p")
        self.assertEqual(entry["layer"], "l")
        self.assertEqual(entry["fix"], "f")
        self.assertEqual(entry["prevents"], "pr")
        self.assertNotIn("trigger", entry)
        self.assertNotIn("recurrence", entry)

    def test_append_preserves_existing_lines(self):
        """The command never rewrites history; earlier bytes stay intact."""
        existing = '{"date":"2026-01-01","problem":"legacy"}\n'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = Path(f.name)
        path.write_text(existing, encoding="utf-8")
        result = run_typer(
            aet.app,
            [
                "learnings",
                "append",
                "--file",
                str(path),
                "--problem", "p",
                "--layer", "l",
                "--fix", "f",
                "--prevents", "pr",
            ],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        lines = path.read_bytes().splitlines()
        self.assertEqual(lines[0].decode("utf-8"), '{"date":"2026-01-01","problem":"legacy"}')
        entry = json.loads(lines[1])
        self.assertEqual(entry["problem"], "p")

    def test_missing_required_field_exits_nonzero(self):
        """Each required option is enforced; omitting one fails the command."""
        required = {
            "--problem": "p",
            "--layer": "l",
            "--fix": "f",
            "--prevents": "pr",
        }
        for omitted in required:
            with self.subTest(omitted=omitted):
                args = []
                for flag, value in required.items():
                    if flag != omitted:
                        args.extend([flag, value])
                result, _ = self._run_append(*args)
                self.assertNotEqual(result.exit_code, 0, result.output)
                self.assertIn(omitted, result.output)

    def test_empty_required_field_exits_1(self):
        """A required option that is empty or whitespace-only is rejected with exit 1."""
        for flag in ("--problem", "--layer", "--fix", "--prevents"):
            with self.subTest(flag=flag):
                args = {
                    "--problem": "p",
                    "--layer": "l",
                    "--fix": "f",
                    "--prevents": "pr",
                }
                args[flag] = "   "
                flat = []
                for k, v in args.items():
                    flat.extend([k, v])
                result, _ = self._run_append(*flat)
                self.assertEqual(result.exit_code, 1, result.output)
                self.assertIn(flag, result.output)

    def test_recurrence_zero_rejected(self):
        """Recurrence must be a positive integer; zero is rejected."""
        result, _ = self._run_append(
            "--problem", "p",
            "--layer", "l",
            "--fix", "f",
            "--prevents", "pr",
            "--recurrence", "0",
        )
        self.assertEqual(result.exit_code, 1, result.output)

    def test_recurrence_negative_rejected(self):
        """Recurrence must be a positive integer; negative values are rejected."""
        result, _ = self._run_append(
            "--problem", "p",
            "--layer", "l",
            "--fix", "f",
            "--prevents", "pr",
            "--recurrence", "-3",
        )
        self.assertEqual(result.exit_code, 1, result.output)

    def test_no_trigger_omits_key(self):
        """When no --trigger is supplied, the entry has no trigger field."""
        result, path = self._run_append(
            "--problem", "p",
            "--layer", "l",
            "--fix", "f",
            "--prevents", "pr",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        entry = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        self.assertNotIn("trigger", entry)

    def test_multiple_triggers_preserved(self):
        """Repeatable --trigger is collected into a list."""
        result, path = self._run_append(
            "--problem", "p",
            "--layer", "l",
            "--fix", "f",
            "--prevents", "pr",
            "--trigger", "a",
            "--trigger", "b",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        entry = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(entry["trigger"], ["a", "b"])

    def test_recurrence_positive_accepted(self):
        """A positive recurrence integer is stored in the entry."""
        result, path = self._run_append(
            "--problem", "p",
            "--layer", "l",
            "--fix", "f",
            "--prevents", "pr",
            "--recurrence", "2",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        entry = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(entry["recurrence"], 2)


class TestLearningsGroup(unittest.TestCase):
    """Smoke tests for the noun-scoped ``learnings`` group."""

    def test_learnings_group_renders_help(self):
        """The learnings group is registered and renders usage help."""
        result = run_typer(aet.app, ["learnings", "--help"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Usage:", result.output)
        self.assertIn("append", result.output)


if __name__ == "__main__":
    unittest.main()
