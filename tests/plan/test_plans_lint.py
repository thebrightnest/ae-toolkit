"""Tests for the ``aet plans lint`` corpus classifier stage."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
from aet import plans_lint  # noqa: E402


def make_plan(path: Path, plan_id: str | None = None, status: str | None = None) -> None:
    """Write a minimal plan file using the frontmatter contract."""
    stem = plan_id or path.stem
    lines = ["---", f"id: {stem}", "size: S"]
    if status is not None:
        lines.append(f"status: {status}")
    lines.extend(
        [
            "---",
            "",
            f"# Plan {stem}",
            "",
            "## Context",
            "",
            "PRD: docs/prds/default-prd.md",
            "",
            "## Task List",
            "",
            "1. Do something (traces: R-1).",
            "",
            "---",
            "",
            "*Stage: plan-approved*",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_plan_with_files(
    path: Path,
    plan_id: str | None = None,
    blocked_by: list[str] | None = None,
    files: list[str] | None = None,
    status: str | None = None,
) -> None:
    """Write a plan file with frontmatter, a task list and Files to Modify."""
    stem = plan_id or path.stem
    lines = ["---", f"id: {stem}", "size: S"]
    if status is not None:
        lines.append(f"status: {status}")
    if blocked_by is not None:
        lines.append("blocked_by:")
        for blocker in blocked_by:
            lines.append(f"  - {blocker}")
    lines.extend(
        [
            "---",
            "",
            f"# Plan {stem}",
            "",
            "## Context",
            "",
            "PRD: docs/prds/default-prd.md",
            "",
            "## Task List",
            "",
            "1. Do something (traces: R-1).",
            "",
            "## Files to Modify",
            "",
        ]
    )
    for file_path in files or []:
        lines.append(f"- `{file_path}`")
    lines.extend(
        [
            "",
            "---",
            "",
            "*Stage: plan-approved*",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestCorpusLint(unittest.TestCase):
    """Direct tests of ``plans_lint.lint_corpus``."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plans_dir = self.root / "docs" / "plans"
        self.plans_dir.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_clean_corpus_passes(self):
        """Plans without a status field pass the linter."""
        make_plan(self.plans_dir / "one.md")
        make_plan(self.plans_dir / "two.md")

        violations = plans_lint.lint_corpus(self.plans_dir)

        self.assertEqual(violations, [])

    def test_status_field_fails(self):
        """A live (non-terminal) status frontmatter field is reported as a violation."""
        make_plan(self.plans_dir / "legacy.md", status="queued")
        make_plan(self.plans_dir / "terminal.md", status="merged")

        violations = plans_lint.lint_corpus(self.plans_dir)

        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0][0].name, "legacy.md")
        self.assertIn("live status field is present", violations[0][1])

    def test_empty_corpus_passes(self):
        """An empty plans directory produces no violations."""
        violations = plans_lint.lint_corpus(self.plans_dir)

        self.assertEqual(violations, [])

    def test_missing_plans_dir_passes(self):
        """A missing plans directory produces no violations."""
        missing = self.root / "docs" / "plans"
        violations = plans_lint.lint_corpus(missing)

        self.assertEqual(violations, [])

    def test_archived_plans_are_excluded_from_corpus(self):
        """Plans under docs/plans/archive/ are invisible to the linter."""
        make_plan(self.plans_dir / "active.md")
        archive_dir = self.plans_dir / "archive"
        archive_dir.mkdir()
        make_plan(archive_dir / "settled.md", status="merged")
        # Even with an illegal live status, archived plans are excluded
        make_plan(archive_dir / "bad_archived.md", status="queued")

        violations = plans_lint.lint_corpus(self.plans_dir)

        self.assertEqual(violations, [])

    def test_active_directory_plans_are_discovered_and_linted(self):
        """Plans under docs/plans/active/ are discovered and checked."""
        active_dir = self.plans_dir / "active"
        active_dir.mkdir()
        make_plan(active_dir / "good_active.md")
        make_plan(active_dir / "bad_active.md", status="in_progress")

        violations = plans_lint.lint_corpus(self.plans_dir)

        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0][0].name, "bad_active.md")
        self.assertIn("live status field is present", violations[0][1])


class TestFloorLint(unittest.TestCase):
    """Direct tests of ``plans_lint.lint_floor``."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plans_dir = self.root / "docs" / "plans"
        self.plans_dir.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _warning_ids(self, warnings):
        return sorted(path.stem for path, _ in warnings)

    def test_overlap_with_linearly_ordered_sibling_is_flagged(self):
        """A plan blocked by a sibling with >50% file overlap is a floor candidate."""
        make_plan_with_files(
            self.plans_dir / "parent.md",
            plan_id="parent",
            files=["src/aet/foo.py", "src/aet/bar.py", "src/aet/baz.py"],
        )
        make_plan_with_files(
            self.plans_dir / "child.md",
            plan_id="child",
            blocked_by=["parent"],
            files=["src/aet/foo.py", "src/aet/bar.py"],
        )

        warnings = plans_lint.lint_floor(self.plans_dir)

        self.assertEqual(self._warning_ids(warnings), ["child"])
        self.assertIn("overlap parent", warnings[0][1])

    def test_exact_half_overlap_is_not_flagged(self):
        """A 50% overlap is not *more than* 50%, so it is not flagged."""
        make_plan_with_files(
            self.plans_dir / "parent.md",
            plan_id="parent",
            files=[
                "src/aet/foo.py",
                "src/aet/bar.py",
                "src/aet/baz.py",
                "src/aet/qux.py",
            ],
        )
        make_plan_with_files(
            self.plans_dir / "child.md",
            plan_id="child",
            blocked_by=["parent"],
            files=[
                "src/aet/foo.py",
                "src/aet/bar.py",
                "src/aet/alpha.py",
                "src/aet/beta.py",
            ],
        )

        warnings = plans_lint.lint_floor(self.plans_dir)

        self.assertEqual(warnings, [])

    def test_independent_sibling_with_shared_file_is_not_flagged(self):
        """A single shared file is not a substantial overlap."""
        make_plan_with_files(
            self.plans_dir / "parent.md",
            plan_id="parent",
            files=["src/aet/foo.py", "src/aet/bar.py", "src/aet/baz.py"],
        )
        make_plan_with_files(
            self.plans_dir / "child.md",
            plan_id="child",
            blocked_by=["parent"],
            files=["src/aet/foo.py", "src/aet/qux.py"],
        )

        warnings = plans_lint.lint_floor(self.plans_dir)

        self.assertEqual(warnings, [])

    def test_docs_only_plan_with_single_consumer_is_flagged(self):
        """A docs-only plan consumed by exactly one sibling is a floor candidate."""
        make_plan_with_files(
            self.plans_dir / "docs-plan.md",
            plan_id="docs-plan",
            files=["docs/adr/001-rule.md"],
        )
        make_plan_with_files(
            self.plans_dir / "consumer.md",
            plan_id="consumer",
            blocked_by=["docs-plan"],
            files=["src/aet/thing.py"],
        )

        warnings = plans_lint.lint_floor(self.plans_dir)

        self.assertEqual(self._warning_ids(warnings), ["docs-plan"])
        self.assertIn("consumed only by consumer", warnings[0][1])

    def test_docs_only_plan_with_multiple_consumers_is_not_flagged(self):
        """A docs-only plan consumed by many siblings is independent."""
        make_plan_with_files(
            self.plans_dir / "docs-plan.md",
            plan_id="docs-plan",
            files=["docs/adr/001-rule.md"],
        )
        make_plan_with_files(
            self.plans_dir / "consumer-one.md",
            plan_id="consumer-one",
            blocked_by=["docs-plan"],
            files=["src/aet/one.py"],
        )
        make_plan_with_files(
            self.plans_dir / "consumer-two.md",
            plan_id="consumer-two",
            blocked_by=["docs-plan"],
            files=["src/aet/two.py"],
        )

        warnings = plans_lint.lint_floor(self.plans_dir)

        self.assertEqual(warnings, [])

    def test_docs_only_plan_with_no_consumers_is_not_flagged(self):
        """A standalone docs-only plan has no consumer to merge into."""
        make_plan_with_files(
            self.plans_dir / "docs-plan.md",
            plan_id="docs-plan",
            files=["docs/adr/001-rule.md"],
        )

        warnings = plans_lint.lint_floor(self.plans_dir)

        self.assertEqual(warnings, [])

    def test_plan_without_files_to_modify_is_not_flagged(self):
        """A plan with no parseable Files to Modify cannot trigger floor signals."""
        make_plan(self.plans_dir / "bare.md", plan_id="bare")

        warnings = plans_lint.lint_floor(self.plans_dir)

        self.assertEqual(warnings, [])


class TestOwbCalibrationCorpus(unittest.TestCase):
    """The floor lint separates the consolidated owb splits from independent S plans."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plans_dir = self.root / "docs" / "plans"
        self.plans_dir.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _warning_ids(self, warnings):
        return sorted(path.stem for path, _ in warnings)

    def test_calibration_corpus(self):
        """Positives are flagged; owb-03, owb-08 and owb-13 are not."""
        # owb-01 (consolidated parent) — large M plan.
        make_plan_with_files(
            self.plans_dir / "owb-01-spec-travels-in-task-record.md",
            plan_id="owb-01-spec-travels-in-task-record",
            files=[
                "src/aet/plan_parser.py",
                "src/aet/worktree.py",
                "src/aet/cli/orchestrator.py",
                "src/aet/gate.py",
                "src/aet/queue.py",
                "src/aet/cli/aet_state.py",
                "tests/plan/",
                "tests/worktree/",
                "tests/orchestrator/",
                "tests/queue/",
            ],
        )
        # owb-02 (split from owb-01) — most files overlap owb-01.
        make_plan_with_files(
            self.plans_dir / "owb-02-keep-rendered-plan-on-branch.md",
            plan_id="owb-02-keep-rendered-plan-on-branch",
            blocked_by=["owb-01-spec-travels-in-task-record"],
            files=[
                "src/aet/plan_parser.py",
                "src/aet/worktree.py",
                "src/aet/cli/orchestrator.py",
            ],
        )
        # owb-03 — independent S plan (archive relocation).
        make_plan_with_files(
            self.plans_dir / "owb-03-relocate-settled-plan-archive.md",
            plan_id="owb-03-relocate-settled-plan-archive",
            files=[
                "src/aet/queue.py",
                "src/aet/metrics.py",
                "src/aet/telemetry.py",
                "tests/metrics/",
                "tests/migration/",
            ],
        )
        # owb-05 (consolidated parent) — board-is-open-work.
        make_plan_with_files(
            self.plans_dir / "owb-05-board-is-open-work.md",
            plan_id="owb-05-board-is-open-work",
            blocked_by=["owb-01-spec-travels-in-task-record"],
            files=[
                "src/aet/cli/sync.py",
                "src/aet/cli/aet_state.py",
                "src/aet/cli/next.py",
                "src/aet/cli/status.py",
                "src/aet/queue.py",
                "tests/queue/",
                "tests/state/",
            ],
        )
        # owb-06 (split from owb-05) — overlaps substantially.
        make_plan_with_files(
            self.plans_dir / "owb-06-board-list-is-query.md",
            plan_id="owb-06-board-list-is-query",
            blocked_by=["owb-05-board-is-open-work"],
            files=[
                "src/aet/queue.py",
                "src/aet/cli/sync.py",
            ],
        )
        # owb-08 — independent S plan (single ledger path).
        make_plan_with_files(
            self.plans_dir / "owb-08-single-source-ledger-path.md",
            plan_id="owb-08-single-source-ledger-path",
            files=[
                "src/aet/ledger.py",
                "src/aet/cli/gate.py",
                "src/aet/cli/aet_state.py",
                "src/aet/cli/sprint.py",
                "src/aet/cli/ship.py",
                "tests/ledger/",
            ],
        )
        # owb-10 (consolidated parent) — sprint label intake.
        make_plan_with_files(
            self.plans_dir / "owb-10-sprint-label-intake.md",
            plan_id="owb-10-sprint-label-intake",
            blocked_by=["owb-05-board-is-open-work", "owb-09-work-state-as-crdt"],
            files=[
                "src/aet/cli/sprint.py",
                "src/aet/backends/github_backend.py",
                "src/aet/projections/dispatcher.py",
                "docs/adr/032-github-issues-projection-not-backend.md",
                "docs/adr/033-projections-fail-open-storage-fail-closed.md",
                "tests/backends/",
                "tests/queue/",
            ],
        )
        # owb-09 (split from owb-10) — docs-only ADR narrowing consumed only by owb-10.
        make_plan_with_files(
            self.plans_dir / "owb-09-work-state-as-crdt.md",
            plan_id="owb-09-work-state-as-crdt",
            files=[
                "docs/adr/032-github-issues-projection-not-backend.md",
                "docs/adr/033-projections-fail-open-storage-fail-closed.md",
            ],
        )
        # owb-13 — independent S plan, blocked by owb-01, but only 50% overlap.
        make_plan_with_files(
            self.plans_dir / "owb-13-prd-integration-branch.md",
            plan_id="owb-13-prd-integration-branch",
            blocked_by=["owb-01-spec-travels-in-task-record"],
            files=[
                "src/aet/backends/factory.py",
                "src/aet/cli/orchestrator.py",
                "src/aet/cli/ship.py",
                "tests/orchestrator/",
            ],
        )

        warnings = plans_lint.lint_floor(self.plans_dir)

        self.assertEqual(
            self._warning_ids(warnings),
            [
                "owb-02-keep-rendered-plan-on-branch",
                "owb-06-board-list-is-query",
                "owb-09-work-state-as-crdt",
            ],
        )


class TestPlansLintCli(unittest.TestCase):
    """``aet plans lint`` reaches the new binary through the dispatcher."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _run_aet(self, cwd: Path, *args: str) -> subprocess.CompletedProcess:
        env = {**os.environ, "AET_BIN_DIR": str(self.bin_dir)}
        cmd = [sys.executable, str(REPO_ROOT / "src" / "aet" / "cli" / "main.py"), *args]
        return subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
        )

    def test_plans_lint_routed_through_aet_dispatcher(self):
        """``aet plans lint`` runs the corpus linter and exits 0."""
        repo = self.root / "repo"
        plans_dir = repo / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
        make_plan(plans_dir / "clean.md")

        result = self._run_aet(repo, "plans", "lint")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("all 1 plans passed lint", result.stdout)

    def test_plans_lint_reports_status_field(self):
        """``aet plans lint`` names the plan file with the live status field."""
        repo = self.root / "repo"
        plans_dir = repo / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
        make_plan(plans_dir / "clean.md")
        make_plan(plans_dir / "bad.md", status="queued")

        result = self._run_aet(repo, "plans", "lint")

        self.assertEqual(result.returncode, 1)
        self.assertIn("bad.md", result.stderr)
        self.assertIn("live status field is present", result.stderr)

    def test_plans_lint_reports_floor_warnings_without_failing(self):
        """Floor warnings are printed but the command still exits 0."""
        repo = self.root / "repo"
        plans_dir = repo / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
        make_plan_with_files(
            plans_dir / "parent.md",
            plan_id="parent",
            files=["src/aet/foo.py", "src/aet/bar.py", "src/aet/baz.py"],
        )
        make_plan_with_files(
            plans_dir / "child.md",
            plan_id="child",
            blocked_by=["parent"],
            files=["src/aet/foo.py", "src/aet/bar.py"],
        )

        result = self._run_aet(repo, "plans", "lint")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("child.md", result.stdout)
        self.assertIn("floor:", result.stdout)
        self.assertIn("floor warning", result.stdout)

    def test_plans_lint_discovers_active_plans_cli(self):
        """``aet plans lint`` finds plans under docs/plans/active/."""
        repo = self.root / "repo"
        plans_dir = repo / "docs" / "plans"
        active_dir = plans_dir / "active"
        active_dir.mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
        make_plan(active_dir / "active_one.md")

        result = self._run_aet(repo, "plans", "lint")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("all 1 plans passed lint", result.stdout)


if __name__ == "__main__":
    unittest.main()
