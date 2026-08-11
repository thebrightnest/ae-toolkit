"""Tests for t2r-04: the `aet context` session-workflow-context command."""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from tests.cli._helpers import git, run_typer

aet = importlib.import_module("aet.cli.main")
plan_parser = importlib.import_module("aet.plan_parser")
verifier = importlib.import_module("aet.verifier")
context_module = importlib.import_module("aet.cli.context")


def _make_git_repo(tmp_path: Path) -> Path:
    """Initialize a git repo in ``tmp_path`` and return it."""
    git(["init"], tmp_path)
    git(["config", "user.email", "test@example.com"], tmp_path)
    git(["config", "user.name", "Test"], tmp_path)
    return tmp_path


def _write_plan(
    plans_dir: Path,
    name: str,
    *,
    stage: str = "plan-approved",
    title: str | None = None,
) -> Path:
    """Write a minimal plan file and return its path."""
    path = plans_dir / name
    header = title or f"Plan: {name}"
    body = f"""---
id: {Path(name).stem}
size: M
---

# {header}

## Context
PRD: docs/prds/default-prd.md

## Task List

1. Do something (traces: R-1).

---

_Stage: {stage}_
_Next step: run `aet-work`_
"""
    path.write_text(body, encoding="utf-8")
    return path


def _write_prd(prds_dir: Path, name: str, stage: str = "scope-validated") -> Path:
    """Write a minimal PRD file and return its path."""
    path = prds_dir / name
    body = f"""# PRD: {name}

## Requirements

- **R-1**: requirement

---

_Stage: {stage}_
_Next step: run `aet-pipeline-plan`_
"""
    path.write_text(body, encoding="utf-8")
    return path


def _write_learnings(agents_dir: Path, entries: list[dict]) -> None:
    """Write learnings entries to ``.agents/learnings.jsonl``."""
    path = agents_dir / "learnings.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def _set_mtime(path: Path, iso: str) -> None:
    """Set ``path`` mtime from an ISO-8601 timestamp."""
    ts = datetime.fromisoformat(iso).timestamp()
    os.utime(path, (ts, ts))


class TestPlanParserStageReader(unittest.TestCase):
    """Unit tests for the plan_parser stage-reader consolidation (task 1)."""

    def test_most_recent_plan_returns_most_recently_modified_plan(self):
        """most_recent_plan mirrors most_recent_prd for the plans directory."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plans_dir = tmp_path / "docs" / "plans"
            plans_dir.mkdir(parents=True)

            older = plans_dir / "older.md"
            older.write_text("---\nid: older\n---\n# Older\n", encoding="utf-8")
            newer = plans_dir / "newer.md"
            newer.write_text("---\nid: newer\n---\n# Newer\n", encoding="utf-8")

            # Ensure mtime ordering even on fast filesystems.
            os.utime(older, (older.stat().st_atime, older.stat().st_mtime - 10))

            result = plan_parser.most_recent_plan(plans_dir)
            self.assertEqual(result, newer)

    def test_most_recent_plan_returns_none_for_missing_dir(self):
        """most_recent_plan returns None when the plans directory does not exist."""
        result = plan_parser.most_recent_plan(Path("/nonexistent/plans"))
        self.assertIsNone(result)

    def test_stage_from_plan_uses_last_match(self):
        """stage_from_plan returns the final _Stage: footer value."""
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.md"
            plan.write_text(
                "---\nid: plan\n---\n# Plan\n\n"
                "---\n\n"
                "_Stage: implemented_\n"
                "_Next step: run `aet-qa`_\n",
                encoding="utf-8",
            )
            self.assertEqual(plan_parser.stage_from_plan(plan), "implemented")

    def test_stage_from_plan_prefers_last_match_on_polluted_body(self):
        """A body with a leading stage line resolves to the footer last match."""
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.md"
            plan.write_text(
                "---\nid: plan\n---\n# Plan\n\n"
                "_Stage: superseded_ in body (legacy mention).\n"
                "Then discusses _Stage: plan-approved_ as a target.\n\n"
                "---\n\n"
                "_Stage: qa-complete_\n",
                encoding="utf-8",
            )
            self.assertEqual(plan_parser.stage_from_plan(plan), "qa-complete")

    def test_stage_from_plan_returns_none_when_no_stage(self):
        """stage_from_plan returns None for plans without a stage footer."""
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.md"
            plan.write_text("---\nid: plan\n---\n# Plan\n", encoding="utf-8")
            self.assertIsNone(plan_parser.stage_from_plan(plan))

    def test_read_plan_stage_delegates_to_stage_from_plan(self):
        """verifier.read_plan_stage is a thin delegate keeping last-match semantics."""
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.md"
            plan.write_text(
                "---\nid: plan\n---\n# Plan\n\n"
                "_Stage: first_ in body.\n\n"
                "---\n\n"
                "_Stage: last_\n",
                encoding="utf-8",
            )
            self.assertEqual(verifier.read_plan_stage(str(plan)), "last")

    def test_read_plan_stage_returns_none_for_missing_file(self):
        """verifier.read_plan_stage returns None when the plan file is absent."""
        self.assertIsNone(verifier.read_plan_stage("/nonexistent/plan.md"))



class TestContextCollectors(unittest.TestCase):
    """Unit tests for individual context collectors."""

    def test_collect_branch_returns_branch_name(self):
        """collect_branch returns the current git branch."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = _make_git_repo(Path(tmp))
            (tmp_path / "file.txt").write_text("x", encoding="utf-8")
            git(["add", "-A"], tmp_path)
            git(["commit", "-m", "initial"], tmp_path)
            git(["checkout", "-b", "feat-123"], tmp_path)
            self.assertEqual(context_module.collect_branch(tmp_path), "feat-123")

    def test_collect_branch_returns_none_outside_git(self):
        """collect_branch returns None when not inside a git repository."""
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(context_module.collect_branch(Path(tmp)))

    def test_repo_state_clean(self):
        """A clean repo reports repo_state clean."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = _make_git_repo(Path(tmp))
            (tmp_path / "file.txt").write_text("hello", encoding="utf-8")
            git(["add", "-A"], tmp_path)
            git(["commit", "-m", "initial"], tmp_path)
            self.assertEqual(context_module.collect_repo_state(tmp_path), "clean")

    def test_repo_state_dirty(self):
        """An uncommitted change reports repo_state dirty."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = _make_git_repo(Path(tmp))
            (tmp_path / "file.txt").write_text("hello", encoding="utf-8")
            git(["add", "-A"], tmp_path)
            git(["commit", "-m", "initial"], tmp_path)
            (tmp_path / "file.txt").write_text("changed", encoding="utf-8")
            self.assertEqual(context_module.collect_repo_state(tmp_path), "dirty")

    def test_repo_state_merge_conflict(self):
        """MERGE_HEAD or unmerged entries report merge-conflict."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = _make_git_repo(Path(tmp))
            (tmp_path / "file.txt").write_text("x", encoding="utf-8")
            git(["add", "-A"], tmp_path)
            git(["commit", "-m", "initial"], tmp_path)
            git_dir = (tmp_path / ".git").resolve()
            merge_head = git_dir / "MERGE_HEAD"
            merge_head.write_text("deadbeef", encoding="utf-8")
            self.assertEqual(context_module.collect_repo_state(tmp_path), "merge-conflict")

    def test_collect_agents_md(self):
        """collect_agents_md returns path and mtime."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            agents_md = tmp_path / "AGENTS.md"
            agents_md.write_text("# Agents\n", encoding="utf-8")
            _set_mtime(agents_md, "2026-08-01T12:00:00+00:00")
            result = context_module.collect_agents_md(tmp_path)
            self.assertIsNotNone(result)
            self.assertEqual(result["path"], "AGENTS.md")
            self.assertTrue(result["mtime"].startswith("2026-08-01T12:00:00"))

    def test_collect_learnings_top_three_by_recency(self):
        """collect_learnings returns the three most recent entries."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            agents_dir = tmp_path / ".agents"
            agents_dir.mkdir()
            _write_learnings(
                agents_dir,
                [
                    {"timestamp": "2026-08-01T10:00:00Z", "trigger": ["old"]},
                    {"timestamp": "2026-08-03T10:00:00Z", "trigger": ["newest"]},
                    {"date": "2026-08-02T10:00:00Z", "trigger": ["middle"]},
                    {"timestamp": "2026-07-01T10:00:00Z", "trigger": ["oldest"]},
                ],
            )
            result = context_module.collect_learnings(tmp_path, limit=3)
            self.assertEqual(len(result), 3)
            self.assertEqual(result[0]["trigger"], ["newest"])
            self.assertEqual(result[1]["trigger"], ["middle"])
            self.assertEqual(result[2]["trigger"], ["old"])

    def test_collect_learnings_skips_malformed_lines(self):
        """Malformed JSONL lines are skipped without failing."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            agents_dir = tmp_path / ".agents"
            agents_dir.mkdir()
            path = agents_dir / "learnings.jsonl"
            path.write_text(
                '{"timestamp": "2026-08-01T10:00:00Z", "trigger": ["ok"]}\n'
                "not-json\n"
                '{"trigger": ["no-date"]}\n',
                encoding="utf-8",
            )
            result = context_module.collect_learnings(tmp_path)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["trigger"], ["ok"])

    def test_collect_last_piv_touches_both_domains(self):
        """last_piv is the most recent commit touching plans and src/tests."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = _make_git_repo(Path(tmp))
            plans_dir = tmp_path / "docs" / "plans"
            src_dir = tmp_path / "src"
            plans_dir.mkdir(parents=True)
            src_dir.mkdir()

            # First PIV commit touches both.
            _write_plan(plans_dir, "feat-001.md")
            (src_dir / "widget.py").write_text("x", encoding="utf-8")
            git(["add", "-A"], tmp_path)
            git(["commit", "-m", "piv 1"], tmp_path)

            # Second commit touches only src.
            (src_dir / "widget.py").write_text("y", encoding="utf-8")
            git(["add", "-A"], tmp_path)
            git(["commit", "-m", "only src"], tmp_path)

            # Third commit touches only plans.
            _write_plan(plans_dir, "feat-002.md")
            git(["add", "-A"], tmp_path)
            git(["commit", "-m", "only plans"], tmp_path)

            result = context_module.collect_last_piv(tmp_path)
            self.assertIsNotNone(result)
            # The most recent commit touching both domains is still piv 1.
            hashes = subprocess.run(
                ["git", "log", "--format=%H %s"],
                cwd=tmp_path,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip().splitlines()
            piv1_hash = next(line.split()[0] for line in hashes if line.endswith(" piv 1"))
            expected = subprocess.run(
                ["git", "log", "-1", "--format=%cI", piv1_hash],
                cwd=tmp_path,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            self.assertEqual(result, expected)

    def test_collect_last_piv_null_when_no_overlap(self):
        """last_piv is None when no commit touches both domains."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = _make_git_repo(Path(tmp))
            plans_dir = tmp_path / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            _write_plan(plans_dir, "feat-001.md")
            git(["add", "-A"], tmp_path)
            git(["commit", "-m", "only plans"], tmp_path)
            self.assertIsNone(context_module.collect_last_piv(tmp_path))

    def test_resolve_budget_order_explicit_flag(self):
        """Explicit --budget wins over env and MCP markers."""
        env = {"AET_CONTEXT_CLIENT": "mcp", "AET_MCP_SESSION": "1"}
        self.assertEqual(
            context_module._resolve_budget("cli", env), "cli"
        )

    def test_resolve_budget_order_env_over_mcp(self):
        """AET_CONTEXT_CLIENT wins over MCP env markers."""
        env = {"AET_CONTEXT_CLIENT": "cli", "AET_MCP_SESSION": "1"}
        self.assertEqual(context_module._resolve_budget("auto", env), "cli")

    def test_resolve_budget_mcp_marker(self):
        """MCP env markers select mcp budget when no explicit flag/client."""
        env = {"AET_MCP_SESSION": "session-123"}
        self.assertEqual(context_module._resolve_budget("auto", env), "mcp")

    def test_resolve_budget_defaults_to_cli(self):
        """Default budget is cli when no signals are present."""
        self.assertEqual(context_module._resolve_budget("auto", {}), "cli")


class TestContextCommand(unittest.TestCase):
    """Integration tests for the ``aet context`` CLI."""

    def _make_populated_repo(self, tmp_path: Path) -> None:
        """Set up a controlled git repo with plans, PRDs, learnings, and src."""
        _make_git_repo(tmp_path)
        plans_dir = tmp_path / "docs" / "plans"
        prds_dir = tmp_path / "docs" / "prds"
        agents_dir = tmp_path / ".agents"
        src_dir = tmp_path / "src"
        for d in (plans_dir, prds_dir, agents_dir, src_dir):
            d.mkdir(parents=True)

        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("# AGENTS\n", encoding="utf-8")
        _set_mtime(agents_md, "2026-08-01T12:00:00+00:00")

        _write_prd(prds_dir, "default-prd.md", stage="scope-validated")
        _write_plan(plans_dir, "feat-001.md", stage="implemented")
        _write_plan(plans_dir, "feat-002.md", stage="plan-approved")
        # Make feat-002 the most recent plan.
        os.utime(
            plans_dir / "feat-002.md",
            (
                (plans_dir / "feat-002.md").stat().st_atime,
                (plans_dir / "feat-001.md").stat().st_mtime + 10,
            ),
        )

        _write_learnings(
            agents_dir,
            [
                {"timestamp": "2026-08-03T10:00:00Z", "trigger": ["newest"]},
                {"timestamp": "2026-08-02T10:00:00Z", "trigger": ["middle"]},
                {"timestamp": "2026-08-01T10:00:00Z", "trigger": ["old"]},
            ],
        )

        (src_dir / "widget.py").write_text("x", encoding="utf-8")
        git(["add", "-A"], tmp_path)
        git(["commit", "-m", "initial"], tmp_path)

    def test_context_default_emits_banner_and_battery(self):
        """Default output includes the banner, digest section, and battery keys."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._make_populated_repo(tmp_path)
            result = run_typer(aet.app, ["context"], cwd=tmp_path)
            self.assertEqual(result.exit_code, 0, result.output + result.stderr)
            self.assertIn("📍 Current stage: plan-approved.", result.output)
            self.assertIn("Current rules: none", result.output)
            data = json.loads(result.output[result.output.index("{"):])
            self.assertEqual(data["schema_version"], 1)
            self.assertIn("branch", data)
            self.assertIn("repo_state", data)
            self.assertIn("agents_md", data)
            self.assertIn("learnings", data)
            self.assertIn("active_plan", data)
            self.assertIn("last_piv", data)
            self.assertIn("active_prd_stage", data)
            self.assertIn("active_plan_stage", data)
            self.assertEqual(data["repo_state"], "clean")
            self.assertEqual(data["active_prd_stage"], "scope-validated")
            self.assertEqual(data["active_plan_stage"], "plan-approved")

    def test_context_json_emits_battery_only(self):
        """--json emits only the JSON battery, no banner."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._make_populated_repo(tmp_path)
            result = run_typer(aet.app, ["context", "--json"], cwd=tmp_path)
            self.assertEqual(result.exit_code, 0, result.output + result.stderr)
            self.assertNotIn("📍 Current stage:", result.output)
            data = json.loads(result.output)
            self.assertEqual(data["schema_version"], 1)
            self.assertEqual(data["active_plan_stage"], "plan-approved")

    def test_context_target_pin_by_task_id(self):
        """A bare task id pin resolves active_plan and active_plan_stage."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._make_populated_repo(tmp_path)
            result = run_typer(aet.app, ["context", "--json", "feat-001"], cwd=tmp_path)
            self.assertEqual(result.exit_code, 0, result.output + result.stderr)
            data = json.loads(result.output)
            self.assertEqual(data["active_plan"], "docs/plans/feat-001.md")
            self.assertEqual(data["active_plan_stage"], "implemented")

    def test_context_target_pin_by_plan_path(self):
        """A .md path pin resolves active_plan and active_plan_stage."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._make_populated_repo(tmp_path)
            result = run_typer(
                aet.app, ["context", "--json", "docs/plans/feat-001.md"], cwd=tmp_path
            )
            self.assertEqual(result.exit_code, 0, result.output + result.stderr)
            data = json.loads(result.output)
            self.assertEqual(data["active_plan"], "docs/plans/feat-001.md")
            self.assertEqual(data["active_plan_stage"], "implemented")

    def test_context_target_pin_by_ticket_number(self):
        """A numeric ticket number resolves through the title map."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._make_populated_repo(tmp_path)
            plan = tmp_path / "docs" / "plans" / "feat-001.md"
            text = plan.read_text(encoding="utf-8")
            plan.write_text(text.replace("# Plan: feat-001.md", "# Plan: ticket 42"), encoding="utf-8")
            git(["add", "-A"], tmp_path)
            git(["commit", "-m", "ticket title"], tmp_path)
            result = run_typer(aet.app, ["context", "--json", "42"], cwd=tmp_path)
            self.assertEqual(result.exit_code, 0, result.output + result.stderr)
            data = json.loads(result.output)
            self.assertEqual(data["active_plan"], "docs/plans/feat-001.md")

    def test_context_unknown_target_exits_nonzero(self):
        """An unresolvable target exits non-zero with a clear message."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._make_populated_repo(tmp_path)
            result = run_typer(aet.app, ["context", "--json", "no-such-plan"], cwd=tmp_path)
            self.assertEqual(result.exit_code, 1)
            self.assertIn("Plan not found", result.output + result.stderr)

    def test_context_memories_only(self):
        """--memories-only emits the stage line and compact learnings only."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._make_populated_repo(tmp_path)
            result = run_typer(aet.app, ["context", "--memories-only"], cwd=tmp_path)
            self.assertEqual(result.exit_code, 0, result.output + result.stderr)
            self.assertIn("📍 Current stage: plan-approved.", result.output)
            self.assertIn("[2026-08-03T10:00:00Z] newest:", result.output)
            self.assertNotIn('"schema_version"', result.output)

    def test_context_prime_md_override(self):
        """PRIME.md replaces human-facing output and sets the JSON flag."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._make_populated_repo(tmp_path)
            prime = tmp_path / "PRIME.md"
            prime.write_text("# Custom Prime\n", encoding="utf-8")

            result = run_typer(aet.app, ["context"], cwd=tmp_path)
            self.assertEqual(result.exit_code, 0, result.output + result.stderr)
            self.assertEqual(result.output.strip(), "# Custom Prime")

            result_json = run_typer(aet.app, ["context", "--json"], cwd=tmp_path)
            data = json.loads(result_json.output)
            self.assertTrue(data.get("prime_md_override"))

    def test_context_hook_json_envelope(self):
        """--hook-json wraps output in a SessionStart envelope."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._make_populated_repo(tmp_path)
            for harness in ("claude-code", "codex", "gemini"):
                result = run_typer(
                    aet.app, ["context", "--hook-json", harness], cwd=tmp_path
                )
                self.assertEqual(result.exit_code, 0, result.output + result.stderr)
                data = json.loads(result.output)
                self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "SessionStart")
                self.assertEqual(data["hookSpecificOutput"]["harness"], harness)
                self.assertIn("📍 Current stage:", data["hookSpecificOutput"]["additionalContext"])

    def test_context_json_and_hook_json_mutually_exclusive(self):
        """--json and --hook-json together exit non-zero."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._make_populated_repo(tmp_path)
            result = run_typer(
                aet.app, ["context", "--json", "--hook-json", "claude-code"], cwd=tmp_path
            )
            self.assertEqual(result.exit_code, 1)
            self.assertIn("mutually exclusive", result.output + result.stderr)

    def test_context_budget_mcp_compact(self):
        """mcp budget renders compact human output."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._make_populated_repo(tmp_path)
            result = run_typer(
                aet.app, ["context", "--budget", "mcp"], cwd=tmp_path
            )
            self.assertEqual(result.exit_code, 0, result.output + result.stderr)
            self.assertIn("📍 Current stage:", result.output)
            self.assertIn("[2026-08-03T10:00:00Z] newest:", result.output)
            self.assertIn("branch:", result.output)
            self.assertNotIn('"schema_version"', result.output)

    def test_context_max_lines_caps_output(self):
        """--max-lines caps the number of rendered lines."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._make_populated_repo(tmp_path)
            result = run_typer(aet.app, ["context", "--max-lines", "2"], cwd=tmp_path)
            self.assertEqual(result.exit_code, 0, result.output + result.stderr)
            self.assertEqual(len(result.output.strip().splitlines()), 2)

    def test_context_fails_open_outside_git(self):
        """Outside a git repo the command exits 0 with null git-backed fields."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            plans_dir = tmp_path / "docs" / "plans"
            plans_dir.mkdir(parents=True)
            _write_plan(plans_dir, "feat-001.md")
            result = run_typer(aet.app, ["context", "--json"], cwd=tmp_path)
            self.assertEqual(result.exit_code, 0, result.output + result.stderr)
            data = json.loads(result.output)
            self.assertIsNone(data["branch"])
            self.assertIsNone(data["repo_state"])
            self.assertIsNone(data["last_piv"])

    def _make_golden_repo(self, tmp_path: Path) -> None:
        """Set up the deterministic repo used for golden hook envelopes."""
        _make_git_repo(tmp_path)
        plans_dir = tmp_path / "docs" / "plans"
        prds_dir = tmp_path / "docs" / "prds"
        agents_dir = tmp_path / ".agents"
        src_dir = tmp_path / "src"
        for d in (plans_dir, prds_dir, agents_dir, src_dir):
            d.mkdir(parents=True)

        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("# AGENTS\n", encoding="utf-8")
        _set_mtime(agents_md, "2026-08-01T12:00:00+00:00")

        _write_prd(prds_dir, "default-prd.md", stage="scope-validated")
        _write_plan(plans_dir, "feat-001.md", stage="implemented")
        _write_plan(plans_dir, "feat-002.md", stage="plan-approved")

        _write_learnings(
            agents_dir,
            [
                {"timestamp": "2026-08-03T10:00:00Z", "trigger": ["newest"]},
                {"timestamp": "2026-08-02T10:00:00Z", "trigger": ["middle"]},
                {"timestamp": "2026-08-01T10:00:00Z", "trigger": ["old"]},
            ],
        )

        (src_dir / "widget.py").write_text("x", encoding="utf-8")

        env = os.environ.copy()
        env["GIT_AUTHOR_DATE"] = "2026-08-05T12:00:00+00:00"
        env["GIT_COMMITTER_DATE"] = "2026-08-05T12:00:00+00:00"
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, env=env)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, env=env)

    def test_context_hook_json_matches_golden_fixture(self):
        """--hook-json output matches the checked-in golden envelopes byte-for-byte."""
        fixtures_dir = Path(__file__).resolve().parents[1] / "fixtures" / "context"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._make_golden_repo(tmp_path)
            for harness in ("claude-code", "codex", "gemini"):
                result = run_typer(
                    aet.app, ["context", "--hook-json", harness], cwd=tmp_path
                )
                self.assertEqual(result.exit_code, 0, result.output + result.stderr)
                fixture_path = fixtures_dir / f"{harness.replace('-', '_')}_envelope.json"
                expected = fixture_path.read_text(encoding="utf-8")
                self.assertEqual(result.output, expected)

    def test_context_learnings_tolerates_legacy_date_field(self):
        """Learnings entries with legacy ``date`` field are selected correctly."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _make_git_repo(tmp_path)
            plans_dir = tmp_path / "docs" / "plans"
            agents_dir = tmp_path / ".agents"
            plans_dir.mkdir(parents=True)
            agents_dir.mkdir()
            _write_plan(plans_dir, "feat-001.md")
            _write_learnings(
                agents_dir,
                [
                    {"date": "2026-08-03T10:00:00Z", "trigger": ["newest"]},
                    {"timestamp": "2026-08-02T10:00:00Z", "trigger": ["older"]},
                ],
            )
            git(["add", "-A"], tmp_path)
            git(["commit", "-m", "initial"], tmp_path)
            result = run_typer(aet.app, ["context", "--json"], cwd=tmp_path)
            self.assertEqual(result.exit_code, 0, result.output + result.stderr)
            data = json.loads(result.output)
            self.assertEqual(len(data["learnings"]), 2)
            self.assertEqual(data["learnings"][0]["trigger"], ["newest"])


def _write_adr(
    adr_dir: Path,
    name: str,
    *,
    subject: str | None = None,
    supersedes: list[int] | None = None,
) -> Path:
    """Write a minimal ADR file with optional subject/supersedes frontmatter."""
    lines = ["---"]
    if subject is not None:
        lines.append(f"subject: {subject}")
    if supersedes:
        lines.append(f"supersedes: [{', '.join(str(n) for n in supersedes)}]")
    lines.append("---")
    lines.append("")
    lines.append(f"# {name}")
    path = adr_dir / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


class TestContextDigestInjection(unittest.TestCase):
    """Integration tests for the R-5 digest/insight fields in ``aet context``."""

    def _make_digest_repo(self, tmp_path: Path) -> None:
        """Set up a repo with ADR frontmatter and learnings."""
        _make_git_repo(tmp_path)
        plans_dir = tmp_path / "docs" / "plans"
        adr_dir = tmp_path / "docs" / "adr"
        agents_dir = tmp_path / ".agents"
        for d in (plans_dir, adr_dir, agents_dir):
            d.mkdir(parents=True)

        _write_plan(plans_dir, "feat-001.md", stage="plan-approved")
        _write_adr(adr_dir, "010-old-work-state.md", subject="work-state")
        _write_adr(
            adr_dir, "011-new-work-state.md", subject="work-state", supersedes=[10]
        )
        _write_adr(adr_dir, "003-branch-cleanup.md", subject="branch-cleanup")
        _write_adr(adr_dir, "001-no-subject.md")

        entries = [
            {"timestamp": f"2026-08-0{i}T10:00:00Z", "problem": f"p{i}"}
            for i in range(1, 8)
        ]
        _write_learnings(agents_dir, entries)

        git(["add", "-A"], tmp_path)
        git(["commit", "-m", "initial"], tmp_path)

    def test_context_json_includes_rules_digest_and_durable_insights(self):
        """The JSON battery carries both new R-5 fields with resolved content."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._make_digest_repo(tmp_path)
            result = run_typer(aet.app, ["context", "--json"], cwd=tmp_path)
            self.assertEqual(result.exit_code, 0, result.output + result.stderr)
            data = json.loads(result.output)

            digest = data["rules_digest"]
            self.assertEqual([r["subject"] for r in digest], ["branch-cleanup", "work-state"])
            work_state = digest[1]
            self.assertEqual(work_state["status"], "live")
            self.assertEqual(work_state["live"], "011-new-work-state")
            self.assertEqual(work_state["lineage"], ["010-old-work-state"])

            insights = data["durable_insights"]
            self.assertEqual(len(insights), 5)
            self.assertEqual(insights[0]["problem"], "p7")
            self.assertEqual(insights[-1]["problem"], "p3")

    def test_context_banner_renders_digest_section(self):
        """The human-facing banner includes the generated digest section."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            self._make_digest_repo(tmp_path)
            result = run_typer(aet.app, ["context"], cwd=tmp_path)
            self.assertEqual(result.exit_code, 0, result.output + result.stderr)
            self.assertIn("Current rules:", result.output)
            self.assertIn(
                "- work-state: 011-new-work-state (supersedes 010-old-work-state)",
                result.output,
            )
            self.assertIn("- branch-cleanup: 003-branch-cleanup", result.output)

    def test_context_degrades_to_empty_sections(self):
        """No ADR frontmatter and no learnings yield empty sections, not errors."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _make_git_repo(tmp_path)
            plans_dir = tmp_path / "docs" / "plans"
            adr_dir = tmp_path / "docs" / "adr"
            plans_dir.mkdir(parents=True)
            adr_dir.mkdir(parents=True)
            _write_plan(plans_dir, "feat-001.md")
            _write_adr(adr_dir, "001-no-subject.md")
            git(["add", "-A"], tmp_path)
            git(["commit", "-m", "initial"], tmp_path)

            result = run_typer(aet.app, ["context", "--json"], cwd=tmp_path)
            self.assertEqual(result.exit_code, 0, result.output + result.stderr)
            data = json.loads(result.output)
            self.assertEqual(data["rules_digest"], [])
            self.assertEqual(data["durable_insights"], [])

            result = run_typer(aet.app, ["context"], cwd=tmp_path)
            self.assertEqual(result.exit_code, 0, result.output + result.stderr)
            self.assertIn("Current rules: none", result.output)
