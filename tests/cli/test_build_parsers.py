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

_REPO_ROOT = Path(__file__).parents[2]

_BINS = {
    "status": _REPO_ROOT / "src" / "aet" / "cli" / "status.py",
    "sprint": _REPO_ROOT / "src" / "aet" / "cli" / "sprint.py",
    "backlog": _REPO_ROOT / "src" / "aet" / "cli" / "backlog.py",
    "review": _REPO_ROOT / "src" / "aet" / "cli" / "review.py",
    "next": _REPO_ROOT / "src" / "aet" / "cli" / "next.py",
    "sync": _REPO_ROOT / "src" / "aet" / "cli" / "sync.py",
    "report": _REPO_ROOT / "src" / "aet" / "cli" / "report.py",
    "init-queue": _REPO_ROOT / "src" / "aet" / "cli" / "init-queue.py",
    "aet-state": _REPO_ROOT / "src" / "aet" / "cli" / "aet-state.py",
    "orchestrator": _REPO_ROOT / "src" / "aet" / "cli" / "orchestrator.py",
    "desk": _REPO_ROOT / "src" / "aet" / "cli" / "desk.py",
    "gate": _REPO_ROOT / "src" / "aet" / "cli" / "gate.py",
    "plan": _REPO_ROOT / "src" / "aet" / "cli" / "plan.py",
    "reconcile": _REPO_ROOT / "src" / "aet" / "cli" / "reconcile.py",
    "metrics": _REPO_ROOT / "src" / "aet" / "cli" / "metrics.py",
    "validate-workflows": _REPO_ROOT / "src" / "aet" / "cli" / "validate-workflows.py",
    "ship": _REPO_ROOT / "src" / "aet" / "cli" / "ship.py",
    "aet-retro": _REPO_ROOT / "src" / "aet" / "cli" / "retro.py",
    "mine-learnings": _REPO_ROOT / "src" / "aet" / "cli" / "mine-learnings.py",
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

    def test_sprint_build_parser_returns_parser_with_add_subcommand(self):
        module = _load_bin("bp_sprint", _BINS["sprint"])
        parser = module.build_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)
        args = parser.parse_args(["add", "docs/plans/x.md"])
        self.assertEqual(args.command, "add")
        self.assertEqual(args.target, "docs/plans/x.md")

    def test_backlog_build_parser_returns_parser_with_add_subcommand(self):
        module = _load_bin("bp_backlog", _BINS["backlog"])
        parser = module.build_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)
        args = parser.parse_args(["add", "docs/plans/x.md"])
        self.assertEqual(args.command, "add")
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

    def test_desk_build_parser_returns_parser_with_known_flag(self):
        module = _load_bin("bp_desk", _BINS["desk"])
        parser = module.build_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)
        args = parser.parse_args([])
        self.assertFalse(args.eligibility)

    def test_gate_build_parser_returns_parser_with_known_flag(self):
        module = _load_bin("bp_gate", _BINS["gate"])
        parser = module.build_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)
        args = parser.parse_args(
            ["submit", "--stage", "qa", "--verdict", "pass", "--evidence", "ev.json"]
        )
        self.assertEqual(args.command, "submit")
        self.assertEqual(args.verdict, "pass")
        self.assertEqual(args.evidence, "ev.json")

    def test_plan_build_parser_returns_parser_with_known_flag(self):
        module = _load_bin("bp_plan", _BINS["plan"])
        parser = module.build_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)
        args = parser.parse_args(["validate", "docs/plans/x.md"])
        self.assertEqual(args.command, "validate")
        self.assertEqual(args.plans, ["docs/plans/x.md"])

    def test_reconcile_build_parser_returns_parser_with_known_flag(self):
        module = _load_bin("bp_reconcile", _BINS["reconcile"])
        parser = module.build_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)
        args = parser.parse_args(["--apply"])
        self.assertTrue(args.apply)

    def test_metrics_build_parser_returns_parser_with_known_flag(self):
        module = _load_bin("bp_metrics", _BINS["metrics"])
        parser = module.build_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)
        args = parser.parse_args([])
        self.assertEqual(args.history_file, ".agents/work-history.jsonl")

    def test_validate_workflows_module_loads_and_has_main(self):
        module = _load_bin("bp_validate_workflows", _BINS["validate-workflows"])
        self.assertTrue(callable(module.main))

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
