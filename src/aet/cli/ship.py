#!/usr/bin/env python3
"""aet-ship — Pre-merge gate and post-merge closure for AE Toolkit tasks.

Usage:
  ship gate <plan_file>               Run the pre-merge gate (steps 1-9).
  ship record-merge <task_id> <plan_file> [queue_file]
  ship <task_id> <plan_file> [queue_file]   Legacy alias for record-merge.

The pre-merge gate is implemented in code; the PR creation and merge closure
steps still follow aet-ship/SKILL.md.
"""

from __future__ import annotations

import argparse
import importlib.machinery
import importlib.util
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
from aet import plan_parser  # noqa: E402

# Load aet-state as a module so we can reuse its merge-resolution and
# queue-mutation logic rather than duplicating it.
_AET_STATE_PY = Path(__file__).resolve().parent / "aet-state.py"
_spec = importlib.util.spec_from_loader(
    "aet_state",
    importlib.machinery.SourceFileLoader("aet_state", str(_AET_STATE_PY)),
)
aet_state = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aet_state)


def cmd_ship(args):
    """Run the post-merge closure for a task."""
    ns = aet_state.argparse.Namespace(
        command="record-merge",
        task_id=args.task_id,
        queue=args.queue,
        dry_run=args.dry_run,
        plan=args.plan,
        branch=getattr(args, "branch", None),
        merge_commit=getattr(args, "merge_commit", None),
    )
    return aet_state.cmd_record_merge(ns)


def _fail(message: str) -> int:
    print(f"⛔ {message}", file=sys.stderr)
    return 1


def _run_git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command and return the completed process."""
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=check
    )


def _fetch_origin() -> None:
    _run_git("fetch", "origin")


def _determine_pr_base() -> str:
    """Return the PR base ref: origin/main for independent branches, else the stacked parent."""
    merge_base = _run_git("merge-base", "HEAD", "origin/main").stdout.strip()
    origin_main = _run_git("rev-parse", "origin/main").stdout.strip()
    if merge_base == origin_main:
        return "origin/main"

    log = _run_git(
        "log", "--oneline", "--decorate", "--ancestry-path", f"{merge_base}..HEAD"
    ).stdout
    for line in log.splitlines():
        match = re.match(r"^[0-9a-f]+ \((.*?)\) ", line)
        if not match:
            continue
        refs = [r.strip() for r in match.group(1).split(",")]
        for r in refs:
            r = r.replace("HEAD -> ", "").strip()
            if r in ("HEAD",) or r.startswith("origin/") or r.startswith("tag:"):
                continue
            return r
    return "origin/main"


def _rebase_independent_branch(pr_base: str, dry_run: bool) -> tuple[bool, str]:
    """Rebase independent branches onto origin/main; return (ok, message)."""
    if pr_base != "origin/main":
        return True, "Stacked branch; keeping parent base."
    merge_base = _run_git("merge-base", "HEAD", "origin/main").stdout.strip()
    origin_main = _run_git("rev-parse", "origin/main").stdout.strip()
    if merge_base == origin_main:
        return True, "Already based on origin/main."
    branch = _run_git("branch", "--show-current").stdout.strip()
    if dry_run:
        return True, f"Would rebase --onto origin/main {merge_base} {branch}"
    result = _run_git("rebase", "--onto", "origin/main", merge_base, branch, check=False)
    if result.returncode != 0:
        return False, (
            "⛔ Rebase onto origin/main produced conflicts.\n"
            "   Resolve them manually, then run aet-ship again."
        )
    return True, "Rebased onto origin/main."


def _is_working_tree_clean() -> bool:
    result = _run_git("status", "--short", check=False)
    return result.returncode == 0 and not result.stdout.strip()


def cmd_gate(args: argparse.Namespace) -> int:
    """Run the pre-merge gate for a plan."""
    plan_path = Path(args.plan)
    if not plan_path.is_file():
        return _fail(f"Plan file not found: {plan_path}")

    print(f"Running pre-merge gate for {plan_path}")

    print("1. Fetching origin and determining PR base...")
    _fetch_origin()
    pr_base = args.base or _determine_pr_base()
    print(f"   PR base: {pr_base}")

    print("2. Rebasing independent branches onto origin/main...")
    ok, message = _rebase_independent_branch(pr_base, args.dry_run)
    print(f"   {message}")
    if not ok:
        return 1

    print("3. Ensuring clean working tree...")
    if not _is_working_tree_clean():
        return _fail(
            "Working tree is dirty. Stash, commit, or abort before shipping."
        )

    print("4. Running test suite...")
    test_cmd = os.environ.get("AET_SHIP_TEST_CMD", "make validate")
    test_result = subprocess.run(
        shlex.split(test_cmd), capture_output=True, text=True
    )
    if test_result.returncode != 0:
        return _fail(
            f"Test suite failed:\n{test_result.stdout}\n{test_result.stderr}"
        )
    print("   Test suite passed.")

    print("5. Coverage audit...")
    coverage_cmd = os.environ.get("AET_SHIP_COVERAGE_CMD")
    if coverage_cmd:
        coverage_result = subprocess.run(
            shlex.split(coverage_cmd), capture_output=True, text=True
        )
        if coverage_result.returncode != 0:
            print(
                f"   ⚠️ Coverage dropped:\n{coverage_result.stdout}\n{coverage_result.stderr}"
            )
        else:
            print(f"   Coverage audit passed:\n{coverage_result.stdout}")
    else:
        print("   ⚠️ No coverage command configured (set AET_SHIP_COVERAGE_CMD).")

    print("6. Checking plan completion...")
    unchecked = _unchecked_tasks(plan_path)
    if unchecked:
        print(f"   ⚠️ Plan has unchecked tasks: {', '.join(unchecked)}")
    else:
        print("   All plan tasks are addressed.")

    print("7. Stage-aware review/CSO gate...")
    stage = plan_parser.stage_from_plan(plan_path) or ""
    _print_stage_skips(stage)

    print("8. Checking critical-class verify evidence...")
    work_class = _work_class_from_plan(plan_path)
    if work_class == "critical":
        task_id = plan_parser.parse_frontmatter(plan_path).get("id", plan_path.stem)
        evidence_paths = [
            Path(".agents/verify") / f"{task_id}-evidence.md",
            Path(".agents/verify") / f"{task_id}-evidence",
        ]
        if not any(p.exists() for p in evidence_paths):
            return _fail(
                "⛔ Pipeline paused at aet-ship.\n"
                "Critical-class task requires aet-verify evidence.\n"
                f"Attach evidence at .agents/verify/{task_id}-evidence.md before shipping."
            )
        print("   Verify evidence found.")
    else:
        print("   Not a critical-class task; skipping verify evidence gate.")

    print("9. Running scope audit...")
    flagged = _scope_audit(plan_path, pr_base)
    if flagged:
        print("   ## Scope audit")
        print("")
        print("   Files changed outside this task's expected scope:")
        print("")
        for path in flagged:
            print(f"   - {path}")
    else:
        print("   ✅ Scope audit: no unexpected files detected.")

    print("✅ Pre-merge gate passed.")
    return 0


def _work_class_from_plan(plan_path: Path) -> str:
    """Return the work class from the plan footer, defaulting to normal."""
    content = plan_path.read_text(errors="ignore")
    match = re.search(r"(?im)^[_*]Work class:\s*(.+?)[_*]$", content)
    if match:
        return match.group(1).strip().lower()
    return "normal"


def _scope_audit(plan_path: Path, pr_base: str) -> list[str]:
    """Return a list of out-of-scope files changed against pr_base."""
    result = _run_git("diff", pr_base, "--name-only", check=False)
    if result.returncode != 0:
        return []
    changed = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    associated_prd = None
    # Look for an associated PRD link in the plan body.
    content = plan_path.read_text(errors="ignore")
    for match in re.finditer(r"Source:\s*`?([^`\n]+?)`?", content):
        candidate = match.group(1).strip()
        if candidate.startswith("docs/prds/") and candidate.endswith(".md"):
            associated_prd = candidate
            break
    flagged: list[str] = []
    for path in changed:
        if path.startswith("docs/plans/") and path.endswith(".md"):
            if path != str(plan_path):
                flagged.append(path)
        elif path.startswith("docs/prds/") and path.endswith(".md"):
            if associated_prd and path != associated_prd:
                flagged.append(path)
    return flagged


def _unchecked_tasks(plan_path: Path) -> list[str]:
    """Return the text of unchecked tasks in the plan's task list."""
    content = plan_path.read_text(errors="ignore")
    unchecked: list[str] = []
    in_tasks = False
    for line in content.splitlines():
        if line.strip().lower() in ("## task list", "### task list"):
            in_tasks = True
            continue
        if in_tasks:
            if line.startswith("##"):
                break
            stripped = line.strip()
            if stripped.startswith("- [ ]"):
                unchecked.append(stripped[5:].strip())
    return unchecked


def _print_stage_skips(stage: str) -> None:
    """Print stage-aware skip messages for review and CSO skills."""
    skip_both = {"synced", "secure"}
    if stage in skip_both:
        print(f"   ⏭️ Skipping aet-review: plan stage is already {stage}.")
        print(f"   ⏭️ Skipping aet-cso: plan stage is already {stage}.")
        return
    if stage == "reviewed":
        print("   ⏭️ Skipping aet-review: plan stage is already reviewed.")
        return
    # qa-complete or earlier: run review, then conditional CSO.


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ship",
        description="Pre-merge gate and post-merge closure for AE Toolkit tasks.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gate_parser = sub.add_parser(
        "gate",
        help="Run the pre-merge validation gate.",
    )
    gate_parser.add_argument(
        "plan",
        help="Path to the plan markdown file.",
    )
    gate_parser.add_argument(
        "--base",
        help="Override the PR base branch/ref (default: origin/main or stacked parent).",
    )
    gate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes.",
    )

    close_parser = sub.add_parser(
        "record-merge",
        help="Record post-merge closure for a task.",
    )
    close_parser.add_argument("task_id", help="Task ID to close.")
    close_parser.add_argument("plan", help="Path to the plan markdown file.")
    close_parser.add_argument(
        "queue",
        nargs="?",
        default=".agents/work-queue.json",
        help="Path to the work queue JSON file.",
    )
    close_parser.add_argument(
        "--branch",
        help="Branch name to use for merge verification. Overrides the task's branch field.",
    )
    close_parser.add_argument(
        "--merge-commit",
        help="Merge commit SHA to record directly. Must be an ancestor of origin/main.",
    )
    close_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes.",
    )

    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse arguments, mapping the legacy closure syntax to record-merge."""
    argv = list(argv or sys.argv[1:])
    # Backward compatibility: ship <task_id> <plan> [queue] => ship record-merge ...
    if argv and argv[0] not in ("gate", "record-merge", "--help", "-h"):
        argv.insert(0, "record-merge")
    return build_parser().parse_args(argv)


def main(argv: list[str] | None = None):
    args = parse_args(argv)
    if args.command == "gate":
        return cmd_gate(args)
    if args.command == "record-merge":
        return cmd_ship(args)
    return _fail(f"Unknown command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
