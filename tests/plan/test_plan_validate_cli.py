"""Argument shapes and result reporting for ``aet plan validate``."""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from aet.cli import plan as plan_cli


def _write_plan(path: Path, plan_id: str, rid: str = "R-1") -> None:
    path.write_text(
        "\n".join(
            [
                "---",
                f"id: {plan_id}",
                "size: S",
                "---",
                "",
                f"# Plan {plan_id}",
                "",
                "## Context",
                "",
                "PRD: docs/prds/default-prd.md",
                "",
                "## Task List",
                "",
                f"1. Do something (traces: {rid}).",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_prd(path: Path, rids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# PRD {path.stem}", "## Requirements"]
    lines.extend(f"- **{rid}**: description" for rid in rids)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run(plans: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = plan_cli.cmd_validate(argparse.Namespace(plans=plans))
    return rc, out.getvalue(), err.getvalue()


class TestPlanValidateArgumentShapes(unittest.TestCase):
    """A directory, a file, and no argument all reach the same plan set."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.plans_dir = self.root / "docs" / "plans"
        self.plans_dir.mkdir(parents=True)
        _write_prd(self.root / "docs" / "prds" / "default-prd.md", ["R-1"])
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        _write_plan(self.plans_dir / "alpha.md", "alpha")

    def tearDown(self):
        self.tmp.cleanup()

    def test_directory_argument_expands_to_its_markdown_children(self):
        rc, out, _ = _run([str(self.plans_dir)])

        self.assertEqual(rc, 0)
        self.assertIn("1 plan passed validation", out)

    def test_directory_argument_with_trailing_slash(self):
        rc, out, _ = _run([f"{self.plans_dir}/"])

        self.assertEqual(rc, 0)
        self.assertIn("1 plan passed validation", out)

    def test_directory_and_file_arguments_do_not_double_count(self):
        rc, out, _ = _run([str(self.plans_dir), str(self.plans_dir / "alpha.md")])

        self.assertEqual(rc, 0)
        self.assertIn("1 plan passed validation", out)

    def test_no_argument_resolves_the_repository_it_runs_in(self):
        """The default invocation reads the repo's own plans, not its parent's."""
        _write_plan(self.plans_dir / "beta.md", "beta")
        cwd = os.getcwd()
        os.chdir(self.root)
        try:
            rc, out, _ = _run([])
        finally:
            os.chdir(cwd)

        self.assertEqual(rc, 0)
        self.assertIn("2 plans passed validation", out)


class TestPlanValidateNamesItsMode(unittest.TestCase):
    """Output states which r-trace mode ran, so counts are comparable."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.plans_dir = self.root / "docs" / "plans"
        self.plans_dir.mkdir(parents=True)
        _write_prd(self.root / "docs" / "prds" / "default-prd.md", ["R-1"])
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_success_names_the_plan_set_it_judged_against(self):
        _write_plan(self.plans_dir / "alpha.md", "alpha")

        rc, out, _ = _run([str(self.plans_dir / "alpha.md")])

        self.assertEqual(rc, 0)
        self.assertIn("plan set in docs/plans/", out)

    def test_success_counts_the_plans_it_checked(self):
        _write_plan(self.plans_dir / "alpha.md", "alpha")
        _write_plan(self.plans_dir / "beta.md", "beta")

        rc, out, _ = _run([str(self.plans_dir)])

        self.assertEqual(rc, 0)
        self.assertIn("2 plans passed validation", out)

    def test_own_traces_only_is_named_when_no_plan_set_is_reachable(self):
        with tempfile.TemporaryDirectory() as loose_tmp:
            loose = Path(loose_tmp).resolve() / "elsewhere"
            loose.mkdir()
            _write_plan(loose / "alpha.md", "alpha")

            rc, _, err = _run([str(loose / "alpha.md")])

        self.assertEqual(rc, 1)
        self.assertIn("own traces only", err)

    def test_failure_summarises_scope_and_names_the_ack_syntax(self):
        _write_prd(self.root / "docs" / "prds" / "default-prd.md", ["R-1", "R-2"])
        _write_plan(self.plans_dir / "alpha.md", "alpha")

        rc, _, err = _run([str(self.plans_dir)])

        self.assertEqual(rc, 1)
        self.assertIn("R-2 has no covering task", err)
        self.assertIn("of 1 plan(s)", err)
        self.assertIn("plan set in docs/plans/", err)
        self.assertIn("VALIDATE ACK: <check-id>", err)


if __name__ == "__main__":
    unittest.main()
