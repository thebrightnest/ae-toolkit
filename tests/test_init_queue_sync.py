"""Behavior-driven tests for src/aet/cli/init-queue.py and src/aet/cli/sync.py."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
from aet import plan_parser  # noqa: E402


def run_script(script_name, cwd, queue_file, history_file, plans_dir, prds_dir=None):
    """Run a queue script in an isolated environment and return its result."""
    env = os.environ.copy()
    fake_bin = Path(cwd) / "fakebin"
    fake_bin.mkdir(exist_ok=True)
    fake_python3 = fake_bin / "python3"
    log_file = Path(cwd) / "fake_python3_calls.txt"
    fake_python3.write_text(
        "#!/usr/bin/env python3\n"
        "import sys, os\n"
        f"log = {str(log_file)!r}\n"
        "with open(log, 'a') as f:\n"
        "    f.write(repr(sys.argv[1:]) + '\\n')\n"
        "print('{}')\n"
    )
    fake_python3.chmod(0o755)
    env["PATH"] = str(fake_bin) + os.pathsep + env["PATH"]
    env["FAKE_PYTHON3_LOG"] = str(log_file)

    cmd = [
        sys.executable,
        str(REPO_ROOT / "src" / "aet" / "cli" / f"{script_name}.py"),
        "--queue-file",
        str(queue_file),
        "--history-file",
        str(history_file),
        "--plans-dir",
        str(plans_dir),
    ]
    if prds_dir is not None:
        cmd += ["--prds-dir", str(prds_dir)]

    result = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, text=True)
    return result, log_file



def read_queue_dict(queue_file):
    """Read the queue file, returning the raw dict/list."""
    with open(queue_file, "r", encoding="utf-8") as f:
        return json.load(f)


def read_tasks(queue_file):
    """Read the task list from a queue file, regardless of wrapper format."""
    data = read_queue_dict(queue_file)
    if isinstance(data, dict):
        return data.get("tasks", [])
    return data


def _repo_root_for_plan(path: Path) -> Path:
    """Infer the repo root from a plan file path for PRD resolution."""
    if path.parent.name == "plans" and path.parent.parent.name == "docs":
        return path.parent.parent.parent
    return path.parent.parent


def _ensure_default_prd(path: Path) -> None:
    """Create a default PRD so tests can produce intake-valid plans."""
    repo_root = _repo_root_for_plan(path)
    prds_dir = repo_root / "docs" / "prds"
    prds_dir.mkdir(parents=True, exist_ok=True)
    prd_path = prds_dir / "default-prd.md"
    if not prd_path.exists():
        prd_path.write_text(
            "# Default PRD\n\n## Requirements\n- **R-1**: default requirement\n",
            encoding="utf-8",
        )


def make_plan(path, title, blocked_by=None, size="M", extra_body="", status="queued"):
    """Write a plan markdown file that passes the full intake validation suite.

    ``extra_body`` is inserted before the default task list/validation content so
    tests can supply their own task list (e.g. for oversized-plan tests) while
    still inheriting a PRD reference and other intake-valid boilerplate.
    """
    stem = path.stem
    lines = ["---", f"id: {stem}", f"size: {size}", f"status: {status}"]
    if blocked_by:
        lines.append("blocked_by:")
        for blocker in blocked_by:
            lines.append(f"  - {blocker}")
    lines.extend(["---", "", f"# {title}", ""])

    _ensure_default_prd(path)
    lines.extend(["## Context", "PRD: docs/prds/default-prd.md", ""])

    if extra_body:
        lines.extend([extra_body, ""])

    lines.extend(["## Task List", "1. Do something (traces: R-1).", ""])
    lines.extend(["## Files to Modify", "- `src/widget.py` (new)", ""])
    lines.extend(
        ["## Validation Steps", "- [ ] test_widget_creation verifies widget.py", ""]
    )
    lines.extend(["---", "", "*Stage: plan-approved*"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestFrontmatterParser(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_parse_frontmatter_extracts_id_blocked_by_size(self):
        plan = self.root / "feat-001.md"
        make_plan(plan, "One", blocked_by=["feat-000"], size="S")
        data = plan_parser.parse_frontmatter(plan)
        self.assertEqual(data["id"], "feat-001")
        self.assertEqual(data["blocked_by"], ["feat-000"])
        self.assertEqual(data["size"], "S")

    def test_parse_frontmatter_allows_empty_blocked_by(self):
        plan = self.root / "feat-001.md"
        make_plan(plan, "One")
        data = plan_parser.parse_frontmatter(plan)
        self.assertEqual(data["id"], "feat-001")
        self.assertEqual(data.get("blocked_by"), [])
        self.assertEqual(data["size"], "M")

    def test_parse_frontmatter_returns_empty_dict_without_frontmatter(self):
        plan = self.root / "feat-001.md"
        plan.write_text("# No frontmatter\n", encoding="utf-8")
        data = plan_parser.parse_frontmatter(plan)
        self.assertEqual(data, {})

    def test_parse_frontmatter_inline_list_with_quotes(self):
        plan = self.root / "feat-001.md"
        plan.write_text(
            "---\n"
            "id: feat-001\n"
            "size: M\n"
            "blocked_by: ['feat-000', \"feat-999\", feat-998]\n"
            "---\n\n# One\n",
            encoding="utf-8",
        )
        data = plan_parser.parse_frontmatter(plan)
        self.assertEqual(data["blocked_by"], ["feat-000", "feat-999", "feat-998"])

    def test_parse_frontmatter_inline_list_with_comma_inside_quotes(self):
        plan = self.root / "feat-001.md"
        plan.write_text(
            "---\n"
            "id: feat-001\n"
            "size: M\n"
            "blocked_by: ['feat-000, feat-999']\n"
            "---\n\n# One\n",
            encoding="utf-8",
        )
        data = plan_parser.parse_frontmatter(plan)
        self.assertEqual(data["blocked_by"], ["feat-000, feat-999"])

    def test_parse_frontmatter_scalar_with_colon_in_quotes(self):
        plan = self.root / "feat-001.md"
        plan.write_text(
            '---\n'
            'id: feat-001\n'
            'size: M\n'
            'title: "One: two"\n'
            '---\n\n# One\n',
            encoding="utf-8",
        )
        data = plan_parser.parse_frontmatter(plan)
        self.assertEqual(data["title"], "One: two")

    def test_parse_frontmatter_rejects_unclosed_inline_list_quote(self):
        plan = self.root / "feat-001.md"
        plan.write_text(
            "---\n"
            "id: feat-001\n"
            "size: M\n"
            "blocked_by: ['feat-000\n"
            "---\n\n# One\n",
            encoding="utf-8",
        )
        data = plan_parser.parse_frontmatter(plan)
        # Malformed inline list falls back to raw string for validation to reject.
        self.assertIsInstance(data["blocked_by"], str)

    def test_parse_frontmatter_block_list(self):
        plan = self.root / "feat-001.md"
        plan.write_text(
            "---\n"
            "id: feat-001\n"
            "size: M\n"
            "blocked_by:\n"
            "  - feat-000\n"
            "  - feat-999\n"
            "---\n\n# One\n",
            encoding="utf-8",
        )
        data = plan_parser.parse_frontmatter(plan)
        self.assertEqual(data["blocked_by"], ["feat-000", "feat-999"])

    def test_parse_frontmatter_empty_inline_list(self):
        plan = self.root / "feat-001.md"
        plan.write_text(
            "---\n"
            "id: feat-001\n"
            "size: M\n"
            "blocked_by: []\n"
            "---\n\n# One\n",
            encoding="utf-8",
        )
        data = plan_parser.parse_frontmatter(plan)
        self.assertEqual(data["blocked_by"], [])

    def test_explicit_frontmatter_blocked_by_detection(self):
        """has_explicit_frontmatter_blocked_by is True only when the key is declared."""
        with_frontmatter = self.root / "with.md"
        with_frontmatter.write_text(
            "---\nid: with\nsize: S\nblocked_by: []\n---\n\n# With\n",
            encoding="utf-8",
        )
        self.assertTrue(plan_parser.has_explicit_frontmatter_blocked_by(with_frontmatter))

        without_key = self.root / "without.md"
        without_key.write_text(
            "---\nid: without\nsize: S\n---\n\n# Without\n",
            encoding="utf-8",
        )
        self.assertFalse(plan_parser.has_explicit_frontmatter_blocked_by(without_key))

        no_frontmatter = self.root / "no_frontmatter.md"
        no_frontmatter.write_text("# No frontmatter\n", encoding="utf-8")
        self.assertFalse(plan_parser.has_explicit_frontmatter_blocked_by(no_frontmatter))


class TestFrontmatterIntake(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plans_dir = self.root / "plans"
        self.prds_dir = self.root / "prds"
        self.queue_file = self.root / "work-queue.json"
        self.history_file = self.root / "work-history.jsonl"
        self.plans_dir.mkdir()
        self.prds_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_frontmatter_ingests_real_dag(self):
        """A frontmatter-authored DAG is loaded with correct blocked_by and blocks."""
        make_plan(self.plans_dir / "a.md", "A", size="S")
        make_plan(self.plans_dir / "b.md", "B", blocked_by=["a"], size="S")
        make_plan(self.plans_dir / "c.md", "C", blocked_by=["b"], size="S")

        result, _ = run_script(
            "init-queue",
            self.root,
            self.queue_file,
            self.history_file,
            self.plans_dir,
            self.prds_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        tasks = {t["id"]: t for t in read_tasks(self.queue_file)}
        self.assertEqual(tasks["a"]["blocked_by"], [])
        self.assertEqual(tasks["b"]["blocked_by"], ["a"])
        self.assertEqual(tasks["c"]["blocked_by"], ["b"])
        self.assertEqual(tasks["a"]["blocks"], ["b"])
        self.assertEqual(tasks["b"]["blocks"], ["c"])
        self.assertEqual(tasks["c"]["blocks"], [])

    def test_reject_missing_or_mismatched_id(self):
        """Plans without id or with mismatched id are rejected with a clear message."""
        bad = self.plans_dir / "bad.md"
        bad.write_text("---\nsize: M\n---\n\n# Bad\n", encoding="utf-8")
        make_plan(self.plans_dir / "good.md", "Good", size="S")

        result, _ = run_script(
            "init-queue",
            self.root,
            self.queue_file,
            self.history_file,
            self.plans_dir,
            self.prds_dir,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("bad.md", result.stderr)
        self.assertIn("missing id", result.stderr)

        mismatched = self.plans_dir / "mismatched.md"
        mismatched.write_text(
            "---\nid: other\nsize: S\n---\n\n# Mismatched\n", encoding="utf-8"
        )
        self.queue_file.write_text(json.dumps([]))
        result, _ = run_script(
            "init-queue",
            self.root,
            self.queue_file,
            self.history_file,
            self.plans_dir,
            self.prds_dir,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("mismatched.md", result.stderr)
        self.assertIn("id mismatch", result.stderr)

    def test_reject_duplicate_id(self):
        """Two plans declaring the same id are rejected."""
        make_plan(self.plans_dir / "first.md", "First", size="S")
        second = self.plans_dir / "second.md"
        second.write_text(
            "---\nid: first\nsize: S\n---\n\n# Second\n", encoding="utf-8"
        )

        result, _ = run_script(
            "init-queue",
            self.root,
            self.queue_file,
            self.history_file,
            self.plans_dir,
            self.prds_dir,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate id", result.stderr.lower())

    def test_reject_unknown_blocker(self):
        """A blocker id that does not name another plan is rejected."""
        make_plan(
            self.plans_dir / "feat-001.md", "One", blocked_by=["missing"], size="S"
        )

        result, _ = run_script(
            "init-queue",
            self.root,
            self.queue_file,
            self.history_file,
            self.plans_dir,
            self.prds_dir,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown blocker", result.stderr)

    def test_reject_oversize_without_marker(self):
        """A plan exceeding atomic complexity limits is rejected unless marked oversized."""
        body_lines = ["## Task List"] + [f"{i}. task {i}" for i in range(302)]
        make_plan(
            self.plans_dir / "big.md",
            "Big",
            size="M",
            extra_body="\n".join(body_lines),
        )

        result, _ = run_script(
            "init-queue",
            self.root,
            self.queue_file,
            self.history_file,
            self.plans_dir,
            self.prds_dir,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("complexity limit", result.stderr)

    def test_oversize_with_marker_is_accepted(self):
        """A marked oversized plan is accepted despite complexity limits."""
        body_lines = ["\u26a0\ufe0f ATOMIC OVERSIZED", "", "## Task List"] + [
            f"{i}. task {i} (traces: R-1)" for i in range(302)
        ]
        make_plan(
            self.plans_dir / "big.md",
            "Big",
            size="L",
            extra_body="\n".join(body_lines),
        )

        result, _ = run_script(
            "init-queue",
            self.root,
            self.queue_file,
            self.history_file,
            self.plans_dir,
            self.prds_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("big", {t["id"] for t in read_tasks(self.queue_file)})

    def test_emitted_task_has_state_pending_blockers_history(self):
        """Intake emits the fods-02 schema: state, pending_blockers, history."""
        make_plan(self.plans_dir / "ready.md", "Ready", size="S")
        make_plan(
            self.plans_dir / "blocked.md", "Blocked", blocked_by=["ready"], size="S"
        )

        result, _ = run_script(
            "init-queue",
            self.root,
            self.queue_file,
            self.history_file,
            self.plans_dir,
            self.prds_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        tasks = {t["id"]: t for t in read_tasks(self.queue_file)}
        self.assertEqual(tasks["ready"]["state"], "ready")
        self.assertEqual(tasks["ready"]["pending_blockers"], 0)
        self.assertEqual(tasks["blocked"]["state"], "blocked")
        self.assertEqual(tasks["blocked"]["pending_blockers"], 1)

        for task in tasks.values():
            self.assertEqual(len(task["history"]), 1)
            self.assertIsNone(task["history"][0]["from"])
            self.assertEqual(task["history"][0]["to"], task["state"])
            self.assertEqual(task["history"][0]["by"], "sync")
            self.assertIn("at", task["history"][0])

    def test_init_queue_rejects_invalid_plan_identically(self):
        """init-queue uses the same validation as sync and fails closed."""
        bad = self.plans_dir / "bad.md"
        bad.write_text("---\nsize: M\n---\n\n# Bad\n", encoding="utf-8")

        result, _ = run_script(
            "init-queue",
            self.root,
            self.queue_file,
            self.history_file,
            self.plans_dir,
            self.prds_dir,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing id", result.stderr)

    def test_sync_does_not_emit_task_with_empty_blocked_by_from_unparsed_section(self):
        """A plan with a legacy dependency section is rejected, not ingested as empty."""
        plan = self.plans_dir / "legacy.md"
        plan.write_text(
            "---\nid: legacy\nsize: S\n---\n\n# Legacy\n\n"
            "## Blocked by\n- missing-link\n\n"
            "---\n\n*Stage: plan-approved*\n",
            encoding="utf-8",
        )

        result, _ = run_script(
            "init-queue",
            self.root,
            self.queue_file,
            self.history_file,
            self.plans_dir,
            self.prds_dir,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.queue_file.exists())


class TestGateKeyIntakeValidation(unittest.TestCase):
    """security_review/docs_sync frontmatter contract at intake (wfd-01)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _plan(self, name, frontmatter_lines):
        path = self.root / name
        path.write_text(
            "---\n" + "\n".join(frontmatter_lines) + "\n---\n\n# Plan\n",
            encoding="utf-8",
        )
        return path

    def _errors(self, *plans, limit_to=None):
        return plan_parser.intake_validation_errors(list(plans), limit_to=limit_to)

    def test_required_values_with_reasons_are_accepted(self):
        plan = self._plan(
            "feat-1.md",
            [
                "id: feat-1",
                "size: S",
                "security_review: required",
                "security_review_reason: touches auth",
                "docs_sync: required",
                "docs_sync_reason: changes documented contract",
            ],
        )
        self.assertEqual(self._errors(plan), [])

    def test_missing_keys_are_accepted(self):
        # Grandfathered plans carry no keys; the runtime fail-safe covers them.
        plan = self._plan("feat-1.md", ["id: feat-1", "size: S"])
        self.assertEqual(self._errors(plan), [])

    def test_invalid_security_review_value_rejected(self):
        plan = self._plan(
            "feat-1.md", ["id: feat-1", "size: S", "security_review: maybe"]
        )
        errors = self._errors(plan)
        self.assertEqual(len(errors), 1)
        self.assertIn("security_review", errors[0][1])

    def test_invalid_docs_sync_value_rejected(self):
        plan = self._plan(
            "feat-1.md", ["id: feat-1", "size: S", "docs_sync: later"]
        )
        errors = self._errors(plan)
        self.assertEqual(len(errors), 1)
        self.assertIn("docs_sync", errors[0][1])

    def test_skipped_without_reason_rejected(self):
        plan = self._plan(
            "feat-1.md", ["id: feat-1", "size: S", "security_review: skipped"]
        )
        errors = self._errors(plan)
        self.assertEqual(len(errors), 1)
        self.assertIn("security_review_reason", errors[0][1])

    def test_skipped_with_empty_reason_rejected(self):
        plan = self._plan(
            "feat-1.md",
            [
                "id: feat-1",
                "size: S",
                "docs_sync: skipped",
                'docs_sync_reason: ""',
            ],
        )
        errors = self._errors(plan)
        self.assertEqual(len(errors), 1)
        self.assertIn("docs_sync_reason", errors[0][1])

    def test_skipped_with_reason_accepted(self):
        plan = self._plan(
            "feat-1.md",
            [
                "id: feat-1",
                "size: S",
                "security_review: skipped",
                "security_review_reason: docs-only change",
            ],
        )
        self.assertEqual(self._errors(plan), [])

    def test_grandfathered_plans_outside_limit_to_pass(self):
        # Already-queued plans are exempt from the new contract even when
        # their values would fail it; only newly added plans are validated.
        bad = self._plan(
            "feat-old.md", ["id: feat-old", "size: S", "security_review: maybe"]
        )
        good = self._plan("feat-new.md", ["id: feat-new", "size: S"])
        self.assertEqual(self._errors(bad, good, limit_to={good}), [])


class TestInitQueue(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plans_dir = self.root / "plans"
        self.prds_dir = self.root / "prds"
        self.queue_file = self.root / "work-queue.json"
        self.history_file = self.root / "work-history.jsonl"
        self.plans_dir.mkdir()
        self.prds_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_rebuilds_facts_with_state_and_wrapper(self):
        """init-queue creates a wrapped queue of state facts with blocks inverse."""
        make_plan(self.plans_dir / "feat-001.md", "First task")
        make_plan(
            self.plans_dir / "feat-002.md", "Second task", blocked_by=["feat-001"]
        )
        (self.prds_dir / "latest.md").write_text("# Latest PRD\n")

        result, _ = run_script(
            "init-queue",
            self.root,
            self.queue_file,
            self.history_file,
            self.plans_dir,
            self.prds_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        data = read_queue_dict(self.queue_file)
        self.assertIsInstance(data, dict)
        self.assertIn("queue_updated_at", data)
        self.assertEqual(data.get("source_prd"), str(self.prds_dir / "latest.md"))

        tasks = {t["id"]: t for t in data["tasks"]}
        self.assertEqual(tasks["feat-001"]["state"], "ready")
        self.assertEqual(tasks["feat-002"]["state"], "blocked")
        self.assertEqual(tasks["feat-002"]["blocked_by"], ["feat-001"])
        self.assertEqual(tasks["feat-001"]["blocks"], ["feat-002"])

    def test_preserves_terminal_status_and_metadata_and_resets_non_terminal(self):
        """Existing terminal tasks keep status/metadata; non-terminal become planned."""
        make_plan(self.plans_dir / "old.md", "Old task")
        make_plan(self.plans_dir / "new.md", "New task")
        make_plan(self.plans_dir / "stale.md", "Stale task")
        initial = {
            "source_prd": "docs/prds/old.md",
            "queue_updated_at": "2026-01-01T00:00:00Z",
            "tasks": [
                {
                    "id": "old",
                    "title": "Old task",
                    "plan_file": str(self.plans_dir / "old.md"),
                    "blocked_by": [],
                    "blocks": [],
                    "status": "merged",
                    "merge_commit": "abc1234",
                    "merge_strategy": "squash",
                    "branch": "feat-old",
                    "worktree": "/worktrees/old",
                    "completed_at": "2026-01-01T00:00:00Z",
                    "merged_at": "2026-01-01T00:00:00Z",
                },
                {
                    "id": "stale",
                    "title": "Stale task",
                    "plan_file": str(self.plans_dir / "stale.md"),
                    "blocked_by": [],
                    "blocks": [],
                    "status": "blocked",
                    "merge_commit": None,
                    "branch": None,
                    "worktree": None,
                    "completed_at": None,
                    "merged_at": None,
                },
            ],
        }
        self.queue_file.write_text(json.dumps(initial))

        result, _ = run_script(
            "init-queue",
            self.root,
            self.queue_file,
            self.history_file,
            self.plans_dir,
            self.prds_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        tasks = {t["id"]: t for t in read_tasks(self.queue_file)}
        history = {
            json.loads(line)["id"]: json.loads(line)
            for line in self.history_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
        # Terminal task sealed to history with metadata preserved.
        self.assertNotIn("old", tasks)
        self.assertEqual(history["old"]["state"], "merged")
        self.assertEqual(history["old"]["merge_commit"], "abc1234")
        self.assertEqual(history["old"]["merge_strategy"], "squash")
        self.assertEqual(history["old"]["branch"], "feat-old")
        self.assertEqual(history["old"]["worktree"], "/worktrees/old")
        # Non-terminal task reset based on frontmatter blockers (ready for no blockers).
        self.assertEqual(tasks["stale"]["state"], "ready")

    def test_init_queue_preserves_state_only_metadata(self):
        """init-queue emits tasks with canonical state and no legacy status key."""
        make_plan(self.plans_dir / "old.md", "Old task")
        make_plan(self.plans_dir / "new.md", "New task")
        initial = {
            "tasks": [
                {
                    "id": "old",
                    "title": "Old task",
                    "plan_file": str(self.plans_dir / "old.md"),
                    "blocked_by": [],
                    "blocks": [],
                    "state": "merged",
                    "merge_commit": "abc1234",
                    "merge_strategy": "squash",
                    "branch": "feat-old",
                    "worktree": "/worktrees/old",
                }
            ]
        }
        self.queue_file.write_text(json.dumps(initial))

        result, _ = run_script(
            "init-queue",
            self.root,
            self.queue_file,
            self.history_file,
            self.plans_dir,
            self.prds_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        history = {
            json.loads(line)["id"]: json.loads(line)
            for line in self.history_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
        # Terminal task is sealed to history with metadata preserved.
        self.assertEqual(history["old"]["state"], "merged")
        self.assertEqual(history["old"]["merge_commit"], "abc1234")
        self.assertEqual(history["old"]["merge_strategy"], "squash")
        self.assertEqual(history["old"]["branch"], "feat-old")
        self.assertEqual(history["old"]["worktree"], "/worktrees/old")
        self.assertNotIn("status", history["old"])

        tasks = {t["id"]: t for t in read_tasks(self.queue_file)}
        self.assertNotIn("old", tasks)
        self.assertEqual(tasks["new"]["state"], "ready")
        self.assertNotIn("status", tasks["new"])

    def test_does_not_call_derive(self):
        """init-queue must not invoke aet-state derive."""
        make_plan(self.plans_dir / "feat-001.md", "First task")
        result, log_file = run_script(
            "init-queue",
            self.root,
            self.queue_file,
            self.history_file,
            self.plans_dir,
            self.prds_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        derive_calls = []
        if log_file.exists():
            for line in log_file.read_text().splitlines():
                if "derive" in line:
                    derive_calls.append(line)
        self.assertEqual(derive_calls, [])

    def test_creates_missing_queue_and_history_files(self):
        """init-queue recreates missing queue and history files on demand."""
        make_plan(self.plans_dir / "qes-rebuild-001.md", "Rebuild task")
        self.assertFalse(self.queue_file.exists())
        self.assertFalse(self.history_file.exists())

        result, _ = run_script(
            "init-queue",
            self.root,
            self.queue_file,
            self.history_file,
            self.plans_dir,
            self.prds_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(
            self.queue_file.exists(),
            "init-queue must create the queue file when it is missing",
        )
        self.assertTrue(
            self.history_file.exists(),
            "init-queue must create the history file when it is missing",
        )

    def test_skips_settled_plans_from_history(self):
        """init-queue skips plans whose committed status is terminal."""
        make_plan(self.plans_dir / "settled.md", "Settled task", status="merged")
        make_plan(self.plans_dir / "active.md", "Active task")

        result, _ = run_script(
            "init-queue",
            self.root,
            self.queue_file,
            self.history_file,
            self.plans_dir,
            self.prds_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        tasks = {t["id"]: t for t in read_tasks(self.queue_file)}
        self.assertNotIn("settled", tasks)
        self.assertIn("active", tasks)
        self.assertIn("1 settled tasks skipped", result.stdout)


class TestSync(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plans_dir = self.root / "plans"
        self.prds_dir = self.root / "prds"
        self.queue_file = self.root / "work-queue.json"
        self.history_file = self.root / "work-history.jsonl"
        self.plans_dir.mkdir()
        self.prds_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_preserves_existing_and_does_not_auto_add(self):
        """sync reconciles existing entries and never auto-adds new plans."""
        existing_plan = self.plans_dir / "existing.md"
        make_plan(existing_plan, "Existing task")
        initial = {
            "source_prd": "docs/prds/p.md",
            "queue_updated_at": "2026-01-01T00:00:00Z",
            "tasks": [
                {
                    "id": "existing",
                    "title": "Existing task",
                    "plan_file": str(existing_plan),
                    "blocked_by": [],
                    "blocks": [],
                    "state": "in_progress",
                    "merge_commit": None,
                    "branch": "feat-existing",
                    "worktree": "/worktrees/existing",
                    "completed_at": None,
                    "merged_at": None,
                }
            ],
        }
        self.queue_file.write_text(json.dumps(initial))

        make_plan(self.plans_dir / "new.md", "New task", blocked_by=["existing"])

        result, _ = run_script(
            "sync", self.root, self.queue_file, self.history_file, self.plans_dir, None
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        data = read_queue_dict(self.queue_file)
        self.assertIsInstance(data, dict)
        tasks = {t["id"]: t for t in data["tasks"]}

        # Existing task preserved.
        self.assertEqual(tasks["existing"]["state"], "in_progress")
        self.assertEqual(tasks["existing"]["branch"], "feat-existing")
        # New plan was not auto-added.
        self.assertNotIn("new", tasks)
        # blocks inverse recomputed for the whole queue.
        self.assertEqual(tasks["existing"]["blocks"], [])
        self.assertIn("0 new tasks added", result.stdout)

    def test_reports_drift_without_mutating_status(self):
        """Missing plan files are reported as drift; stored status is not changed."""
        initial = {
            "tasks": [
                {
                    "id": "missing",
                    "title": "Missing task",
                    "plan_file": "docs/plans/missing.md",
                    "blocked_by": [],
                    "blocks": [],
                    "state": "in_progress",
                    "merge_commit": None,
                    "branch": "feat-missing",
                    "worktree": None,
                    "completed_at": None,
                    "merged_at": None,
                }
            ]
        }
        self.queue_file.write_text(json.dumps(initial))

        result, _ = run_script(
            "sync", self.root, self.queue_file, self.history_file, self.plans_dir, None
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        tasks = {t["id"]: t for t in read_tasks(self.queue_file)}
        self.assertEqual(tasks["missing"]["state"], "in_progress")
        self.assertIn("drift", result.stdout.lower())

    def test_normalizes_merge_verified_to_merged(self):
        """sync normalizes legacy merge_verified statuses to merged."""
        existing_plan = self.plans_dir / "legacy.md"
        make_plan(existing_plan, "Legacy task")
        initial = {
            "tasks": [
                {
                    "id": "legacy",
                    "title": "Legacy task",
                    "plan_file": str(existing_plan),
                    "blocked_by": [],
                    "blocks": [],
                    "status": "merge_verified",
                    "merge_commit": "def5678",
                    "branch": None,
                    "worktree": None,
                    "completed_at": None,
                    "merged_at": None,
                }
            ]
        }
        self.queue_file.write_text(json.dumps(initial))

        result, _ = run_script(
            "sync", self.root, self.queue_file, self.history_file, self.plans_dir, None
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        tasks = {t["id"]: t for t in read_tasks(self.queue_file)}
        self.assertEqual(tasks["legacy"]["state"], "merged")

    def test_does_not_call_derive(self):
        """sync must not invoke aet-state derive."""
        self.queue_file.write_text(json.dumps({"tasks": []}))
        result, log_file = run_script(
            "sync", self.root, self.queue_file, self.history_file, self.plans_dir, None
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        derive_calls = []
        if log_file.exists():
            for line in log_file.read_text().splitlines():
                if "derive" in line:
                    derive_calls.append(line)
        self.assertEqual(derive_calls, [])

    def test_creates_missing_queue_file(self):
        """sync recreates a missing queue file on demand."""
        self.assertFalse(self.queue_file.exists())

        result, _ = run_script(
            "sync", self.root, self.queue_file, self.history_file, self.plans_dir, None
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(
            self.queue_file.exists(),
            "sync must create the queue file when it is missing",
        )

    def test_skips_settled_plans_from_history(self):
        """sync skips existing queue entries whose committed status is terminal."""
        make_plan(self.plans_dir / "settled.md", "Settled task", status="merged")

        settled_record = {
            "id": "settled",
            "plan_file": str(self.plans_dir / "settled.md"),
            "state": "merged",
        }
        # Seed queue with a settled task so sync has something to skip.
        self.queue_file.write_text(json.dumps({"tasks": [settled_record]}))

        result, _ = run_script(
            "sync", self.root, self.queue_file, self.history_file, self.plans_dir, None
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        tasks = {t["id"]: t for t in read_tasks(self.queue_file)}
        self.assertNotIn("settled", tasks)
        self.assertIn("1 skipped (already settled)", result.stdout)

    def test_sync_validates_existing_queued_plans(self):
        """sync validates existing queue entries and rejects invalid ones."""
        existing = self.plans_dir / "existing.md"
        existing.write_text(
            "---\nid: existing\nsize: S\nstatus: queued\n---\n\n# Existing\n\n"
            "## Blocked by\n- missing-link\n\n"
            "---\n\n*Stage: plan-approved*\n",
            encoding="utf-8",
        )
        initial = {
            "tasks": [
                {
                    "id": "existing",
                    "title": "Existing task",
                    "plan_file": str(existing),
                    "blocked_by": [],
                    "blocks": [],
                    "state": "planned",
                    "merge_commit": None,
                    "branch": None,
                    "worktree": None,
                    "completed_at": None,
                    "merged_at": None,
                }
            ]
        }
        self.queue_file.write_text(json.dumps(initial))

        result, _ = run_script(
            "sync", self.root, self.queue_file, self.history_file, self.plans_dir, None
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("legacy dependency section", result.stderr)

        # Fail-closed: the queue file is not mutated, so the existing entry stays.
        tasks = {t["id"]: t for t in read_tasks(self.queue_file)}
        self.assertIn("existing", tasks)

    def test_sync_never_adds_new_plans(self):
        """sync reconciles existing entries and never auto-adds plans from disk."""
        existing_plan = self.plans_dir / "existing.md"
        make_plan(existing_plan, "Existing task")
        initial = {
            "tasks": [
                {
                    "id": "existing",
                    "title": "Existing task",
                    "plan_file": str(existing_plan),
                    "blocked_by": [],
                    "blocks": [],
                    "state": "in_progress",
                    "merge_commit": None,
                    "branch": None,
                    "worktree": None,
                    "completed_at": None,
                    "merged_at": None,
                }
            ]
        }
        self.queue_file.write_text(json.dumps(initial))
        # A second plan exists on disk but was never explicitly added via `add`.
        make_plan(self.plans_dir / "new.md", "New task", size="S")

        result, _ = run_script(
            "sync", self.root, self.queue_file, self.history_file, self.plans_dir, None
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        tasks = {t["id"]: t for t in read_tasks(self.queue_file)}
        self.assertIn("existing", tasks)
        self.assertNotIn("new", tasks)
        self.assertIn("0 new tasks added", result.stdout)

    def test_sync_still_reports_drift_and_rebuilds_edges(self):
        """sync recomputes reverse blocks edges and reports drift for missing plan files."""
        plan_a = self.plans_dir / "a.md"
        plan_b = self.plans_dir / "b.md"
        make_plan(plan_a, "Task A", size="S")
        make_plan(plan_b, "Task B", blocked_by=["a"], size="S")
        initial = {
            "tasks": [
                {
                    "id": "a",
                    "title": "Task A",
                    "plan_file": str(plan_a),
                    "blocked_by": [],
                    "blocks": [],  # stale; build_blocks must rebuild to ["b"]
                    "state": "ready",
                    "merge_commit": None,
                    "branch": None,
                    "worktree": None,
                    "completed_at": None,
                    "merged_at": None,
                },
                {
                    "id": "b",
                    "title": "Task B",
                    "plan_file": str(plan_b),
                    "blocked_by": ["a"],
                    "blocks": [],
                    "state": "blocked",
                    "merge_commit": None,
                    "branch": None,
                    "worktree": None,
                    "completed_at": None,
                    "merged_at": None,
                },
                {
                    "id": "ghost",
                    "title": "Ghost task",
                    "plan_file": "docs/plans/ghost.md",  # missing on disk -> drift
                    "blocked_by": [],
                    "blocks": [],
                    "state": "in_progress",
                    "merge_commit": None,
                    "branch": None,
                    "worktree": None,
                    "completed_at": None,
                    "merged_at": None,
                },
            ]
        }
        self.queue_file.write_text(json.dumps(initial))

        result, _ = run_script(
            "sync", self.root, self.queue_file, self.history_file, self.plans_dir, None
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        tasks = {t["id"]: t for t in read_tasks(self.queue_file)}
        # Reverse edges rebuilt for the whole queue.
        self.assertEqual(tasks["a"]["blocks"], ["b"])
        self.assertEqual(tasks["b"]["blocks"], [])
        # Drift reported for the missing plan file; stored state is not mutated.
        self.assertIn("drift", result.stdout.lower())
        self.assertIn("ghost", result.stdout)
        self.assertEqual(tasks["ghost"]["state"], "in_progress")



if __name__ == "__main__":
    unittest.main()
