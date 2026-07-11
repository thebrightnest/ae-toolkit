"""Tests that every wrapped binary exposes build_parser() (R-6).

Each of the twelve bins must expose a module-level ``build_parser()`` that
returns the ``argparse.ArgumentParser`` the bin parses with, so external
tooling (cli-03 skills-lint) can introspect the real parser tree.
"""

from __future__ import annotations

import argparse
import importlib.machinery
import importlib.util
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent

_BINS = {
    "status": _REPO_ROOT / "aet-work" / "bin" / "status",
    "add": _REPO_ROOT / "aet-work" / "bin" / "add",
    "review": _REPO_ROOT / "aet-work" / "bin" / "review",
    "next": _REPO_ROOT / "aet-work" / "bin" / "next",
    "sync": _REPO_ROOT / "aet-work" / "bin" / "sync",
    "report": _REPO_ROOT / "aet-work" / "bin" / "report",
    "init-queue": _REPO_ROOT / "aet-work" / "bin" / "init-queue",
    "aet-state": _REPO_ROOT / "aet-work" / "bin" / "aet-state",
    "orchestrator": _REPO_ROOT / "aet-work" / "bin" / "orchestrator",
    "ship": _REPO_ROOT / "aet-ship" / "bin" / "ship",
    "aet-retro": _REPO_ROOT / "aet-evolve" / "bin" / "aet-retro",
    "mine-learnings": _REPO_ROOT / "aet-evolve" / "bin" / "mine-learnings",
}


def _load_bin(name: str, path: Path):
    spec = importlib.util.spec_from_loader(
        name, importlib.machinery.SourceFileLoader(name, str(path))
    )
    module = importlib.util.module_from_spec(spec)
    # Register before exec: dataclass-decorated bins introspect sys.modules.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class TestBuildParserExposure(unittest.TestCase):
    def test_status_build_parser_returns_parser_with_known_flag(self):
        module = _load_bin("bp_status", _BINS["status"])
        parser = module.build_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)
        args = parser.parse_args([])
        self.assertEqual(args.queue_file, ".agents/work-queue.json")

    def test_add_build_parser_returns_parser_with_known_flag(self):
        module = _load_bin("bp_add", _BINS["add"])
        parser = module.build_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)
        args = parser.parse_args(["docs/plans/x.md"])
        self.assertEqual(args.target, "docs/plans/x.md")

    def test_review_build_parser_returns_parser_with_known_flag(self):
        module = _load_bin("bp_review", _BINS["review"])
        parser = module.build_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)
        args = parser.parse_args([])
        self.assertEqual(args.plans_dir, "docs/plans")

    def test_next_build_parser_returns_parser_with_known_flag(self):
        module = _load_bin("bp_next", _BINS["next"])
        parser = module.build_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)
        args = parser.parse_args([])
        self.assertEqual(args.queue_file, ".agents/work-queue.json")

    def test_sync_build_parser_returns_parser_with_known_flag(self):
        module = _load_bin("bp_sync", _BINS["sync"])
        parser = module.build_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)
        args = parser.parse_args([])
        self.assertEqual(args.config, ".agents/aet-work.json")

    def test_report_build_parser_returns_parser_with_known_flag(self):
        module = _load_bin("bp_report", _BINS["report"])
        parser = module.build_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)
        args = parser.parse_args(["--since", "2026-01-01T00:00:00Z"])
        self.assertEqual(args.since, "2026-01-01T00:00:00Z")

    def test_init_queue_build_parser_returns_parser_with_known_flag(self):
        module = _load_bin("bp_init_queue", _BINS["init-queue"])
        parser = module.build_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)
        args = parser.parse_args([])
        self.assertEqual(args.prds_dir, "docs/prds")

    def test_aet_state_build_parser_returns_parser_with_known_flag(self):
        module = _load_bin("bp_aet_state", _BINS["aet-state"])
        parser = module.build_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)
        args = parser.parse_args(["validate", "t1", "ready", "in_progress"])
        self.assertEqual(args.command, "validate")
        self.assertEqual(args.task_id, "t1")

    def test_orchestrator_build_parser_returns_parser_with_known_flag(self):
        module = _load_bin("bp_orchestrator", _BINS["orchestrator"])
        parser = module.build_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)
        args = parser.parse_args(["--plan-file", "docs/plans/x.md"])
        self.assertEqual(args.plan_file, "docs/plans/x.md")
        self.assertEqual(args.isolation, "standard")

    def test_ship_build_parser_returns_parser_with_known_flag(self):
        module = _load_bin("bp_ship", _BINS["ship"])
        parser = module.build_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)
        args = parser.parse_args(["t1", "docs/plans/t1.md"])
        self.assertEqual(args.task_id, "t1")
        self.assertEqual(args.plan, "docs/plans/t1.md")
        self.assertFalse(args.dry_run)

    def test_aet_retro_build_parser_returns_parser_with_known_flag(self):
        module = _load_bin("bp_aet_retro", _BINS["aet-retro"])
        parser = module.build_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)
        args = parser.parse_args(["--lookback-days", "14", "--no-mine"])
        self.assertEqual(args.lookback_days, 14)
        self.assertTrue(args.no_mine)

    def test_mine_learnings_build_parser_returns_parser_with_known_flag(self):
        module = _load_bin("bp_mine_learnings", _BINS["mine-learnings"])
        parser = module.build_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)
        args = parser.parse_args(["--propose"])
        self.assertTrue(args.propose)
        self.assertIsNone(args.archive_dir)


if __name__ == "__main__":
    unittest.main()
