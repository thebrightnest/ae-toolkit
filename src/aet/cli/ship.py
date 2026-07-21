#!/usr/bin/env python3
"""aet-ship — Pre-merge gate, PR creation, and post-merge closure for AE Toolkit tasks.

Usage:
  aet ship <plan_file>                Run the gate, then open a PR.
  aet ship gate <plan_file>           Run the pre-merge gate (steps 1-9).
  aet ship open <plan_file>           Run the gate and open a PR.
  aet ship close <task_id> <plan_file> [queue_file]
                                      Record post-merge closure.
  aet ship record-merge <task_id> <plan_file> [queue_file]
                                      Hidden alias for ``close``.

The pre-merge gate, PR creation, and merge closure are all implemented in code.
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
import tempfile
from pathlib import Path
from typing import Optional

import typer
from typer.core import TyperGroup

_SCRIPT_DIR = Path(__file__).resolve().parent
from aet import plan_parser  # noqa: E402

# Load aet-state as a module so we can reuse its merge-resolution and
# queue-mutation logic rather than duplicating it.
_AET_STATE_PY = Path(__file__).resolve().parent / "aet_state.py"
_spec = importlib.util.spec_from_loader(
    "aet_state",
    importlib.machinery.SourceFileLoader("aet_state", str(_AET_STATE_PY)),
)
aet_state = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aet_state)


class GateResult:
    """Structured result of the pre-merge gate for reuse by ``ship open``."""

    def __init__(
        self,
        ok: bool,
        pr_base: str,
        rebased: bool,
        scope_audit: list[str],
        dry_run: bool,
        message: str = "",
    ):
        self.ok = ok
        self.pr_base = pr_base
        self.rebased = rebased
        self.scope_audit = scope_audit
        self.dry_run = dry_run
        self.message = message


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


def cmd_default(args: argparse.Namespace) -> int:
    """Run the gate and, if it passes, open a PR for a plan."""
    plan_path = Path(args.plan)
    if not plan_path.is_file():
        return _fail(f"Plan file not found: {plan_path}")

    print(f"Running aet ship for {plan_path}")
    gate_rc = cmd_gate(args)
    if gate_rc != 0:
        return gate_rc
    return cmd_open(args)


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


def _rebase_independent_branch(pr_base: str, dry_run: bool) -> tuple[bool, str, bool]:
    """Rebase independent branches onto origin/main; return (ok, message, rebased)."""
    if pr_base != "origin/main":
        return True, "Stacked branch; keeping parent base.", False
    merge_base = _run_git("merge-base", "HEAD", "origin/main").stdout.strip()
    origin_main = _run_git("rev-parse", "origin/main").stdout.strip()
    if merge_base == origin_main:
        return True, "Already based on origin/main.", False
    branch = _run_git("branch", "--show-current").stdout.strip()
    if dry_run:
        return True, f"Would rebase --onto origin/main {merge_base} {branch}", False
    result = _run_git("rebase", "--onto", "origin/main", merge_base, branch, check=False)
    if result.returncode != 0:
        return False, (
            "⛔ Rebase onto origin/main produced conflicts.\n"
            "   Resolve them manually, then run aet-ship again."
        ), False
    return True, "Rebased onto origin/main.", True


def _is_working_tree_clean() -> bool:
    result = _run_git("status", "--short", check=False)
    return result.returncode == 0 and not result.stdout.strip()


def _run_gate(args: argparse.Namespace) -> GateResult:
    """Execute gate checks and return a structured result for reuse."""
    plan_path = Path(args.plan)
    if not plan_path.is_file():
        return GateResult(
            ok=False,
            pr_base="",
            rebased=False,
            scope_audit=[],
            dry_run=args.dry_run,
            message=f"Plan file not found: {plan_path}",
        )

    _fetch_origin()
    pr_base = args.base or _determine_pr_base()

    ok, message, rebased = _rebase_independent_branch(pr_base, args.dry_run)
    if not ok:
        return GateResult(
            ok=False,
            pr_base=pr_base,
            rebased=False,
            scope_audit=[],
            dry_run=args.dry_run,
            message=message,
        )

    if not _is_working_tree_clean():
        return GateResult(
            ok=False,
            pr_base=pr_base,
            rebased=rebased,
            scope_audit=[],
            dry_run=args.dry_run,
            message="Working tree is dirty. Stash, commit, or abort before shipping.",
        )

    test_cmd = os.environ.get("AET_SHIP_TEST_CMD", "make validate")
    test_result = subprocess.run(shlex.split(test_cmd), capture_output=True, text=True)
    if test_result.returncode != 0:
        return GateResult(
            ok=False,
            pr_base=pr_base,
            rebased=rebased,
            scope_audit=[],
            dry_run=args.dry_run,
            message=f"Test suite failed:\n{test_result.stdout}\n{test_result.stderr}",
        )

    coverage_cmd = os.environ.get("AET_SHIP_COVERAGE_CMD")
    if coverage_cmd:
        subprocess.run(shlex.split(coverage_cmd), capture_output=True, text=True)

    work_class = _work_class_from_plan(plan_path)
    if work_class == "critical":
        task_id = plan_parser.parse_frontmatter(plan_path).get("id", plan_path.stem)
        evidence_paths = [
            Path(".agents/verify") / f"{task_id}-evidence.md",
            Path(".agents/verify") / f"{task_id}-evidence",
        ]
        if not any(p.exists() for p in evidence_paths):
            return GateResult(
                ok=False,
                pr_base=pr_base,
                rebased=rebased,
                scope_audit=[],
                dry_run=args.dry_run,
                message=(
                    "⛔ Pipeline paused at aet-ship.\n"
                    "Critical-class task requires aet-verify evidence.\n"
                    f"Attach evidence at .agents/verify/{task_id}-evidence.md before shipping."
                ),
            )

    flagged = _scope_audit(plan_path, pr_base)
    return GateResult(
        ok=True,
        pr_base=pr_base,
        rebased=rebased,
        scope_audit=flagged,
        dry_run=args.dry_run,
        message="Pre-merge gate passed.",
    )


def cmd_gate(args: argparse.Namespace) -> int:
    """Run the pre-merge gate for a plan."""
    plan_path = Path(args.plan)
    if not plan_path.is_file():
        return _fail(f"Plan file not found: {plan_path}")

    print(f"Running pre-merge gate for {plan_path}")
    result = _run_gate(args)
    if result.ok:
        print("✅ Pre-merge gate passed.")
        return 0
    return _fail(result.message)


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


def _plan_task_count(plan_path: Path) -> int:
    """Count checked/unchecked tasks under the plan's Task List section."""
    content = plan_path.read_text(errors="ignore")
    count = 0
    in_tasks = False
    for line in content.splitlines():
        if line.strip().lower() in ("## task list", "### task list"):
            in_tasks = True
            continue
        if in_tasks:
            if line.startswith("##"):
                break
            stripped = line.strip()
            if stripped.startswith("- [ ]") or stripped.startswith("- [x]"):
                count += 1
    return count


def _commit_count(pr_base: str) -> int:
    """Return the number of commits between pr_base and HEAD."""
    result = _run_git("rev-list", "--count", f"{pr_base}..HEAD", check=False)
    if result.returncode != 0:
        return 0
    try:
        return int(result.stdout.strip())
    except ValueError:
        return 0


def _commit_subjects(pr_base: str) -> list[str]:
    """Return commit subjects in the pr_base..HEAD range."""
    result = _run_git(
        "log", f"{pr_base}..HEAD", "--pretty=format:%s", check=False
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _is_monolithic_commit(pr_base: str, plan_path: Path) -> bool:
    """True when one commit covers the whole range while the plan has >1 task."""
    return _commit_count(pr_base) == 1 and _plan_task_count(plan_path) > 1


def _extract_prd_link(plan_path: Path) -> str | None:
    """Return the PRD path referenced in the plan's Source line, if any."""
    content = plan_path.read_text(errors="ignore")
    for match in re.finditer(r"Source:\s*`?([^`\n]+?)`?", content):
        candidate = match.group(1).strip()
        if candidate.startswith("docs/prds/") and candidate.endswith(".md"):
            return candidate
    return None


def _generate_changelog_entry(subjects: list[str], plan_path: Path) -> str:
    """Build a PR/commit-trail changelog entry; never writes CHANGELOG.md."""
    plan_id = plan_parser.parse_frontmatter(plan_path).get("id", plan_path.stem)
    title = plan_parser.title_from_plan(plan_path)
    lines = ["## CHANGELOG entry", ""]
    lines.append(
        f"Derived from [{plan_path.name}]({plan_path}) — **{plan_id}**: {title}."
    )
    lines.append("")
    if subjects:
        lines.append("Commits in this PR:")
        for subject in subjects:
            lines.append(f"- {subject}")
    else:
        lines.append("(no commits in the PR range)")
    lines.append("")
    return "\n".join(lines)


def _build_pr_body(
    plan_path: Path,
    pr_base: str,
    scope_audit: list[str],
    changelog_entry: str,
) -> str:
    """Assemble the PR body with links, scope audit, and stacked-PR warnings."""
    parts: list[str] = []
    prd = _extract_prd_link(plan_path)
    parts.append(f"Plan: [{plan_path.name}]({plan_path})")
    if prd:
        parts.append(f"PRD: [{prd}]({prd})")
    parts.append("")
    parts.append(changelog_entry)

    if scope_audit:
        parts.append("## Scope audit")
        parts.append("")
        parts.append("Files changed outside this task's expected scope:")
        for path in scope_audit:
            parts.append(f"- {path}")
        parts.append("")

    if pr_base != "origin/main":
        parts.append(f"⚠️ STACKED PR — base is `{pr_base}`, not main.")
        parts.append("")
        parts.append(f"After `{pr_base}` merges to main, run:")
        parts.append(
            "  git rebase main && git push --force-with-lease && gh pr edit --base main"
        )
        parts.append("before merging this PR.")
        parts.append("")

    return "\n".join(parts)


def _push_branch(rebased: bool, dry_run: bool) -> tuple[bool, str]:
    """Push the branch, using force-with-lease when the gate performed a rebase."""
    if rebased:
        cmd = ["git", "push", "--force-with-lease"]
    else:
        cmd = ["git", "push"]
    if dry_run:
        return True, f"Would run: {' '.join(cmd)}"
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0, result.stdout + result.stderr


def _create_pr(pr_base: str, title: str, body: str, dry_run: bool) -> tuple[bool, str]:
    """Create a GitHub PR using ``gh pr create``."""
    if dry_run:
        return True, f"Would create PR against `{pr_base}` with title: {title}"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as body_file:
        body_file.write(body)
        body_path = body_file.name
    try:
        result = subprocess.run(
            [
                "gh",
                "pr",
                "create",
                "--base",
                pr_base,
                "--title",
                title,
                "--body-file",
                body_path,
            ],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0, result.stdout + result.stderr
    finally:
        os.unlink(body_path)


def _check_release_guard(pr_base: str) -> str | None:
    """Block ``chore(release)`` commits and VERSION changes on feature branches."""
    for subject in _commit_subjects(pr_base):
        if re.match(r"^chore\(release\)", subject):
            return (
                f"Release guard: commit '{subject}' is a chore(release) on a feature branch."
            )
    diff = _run_git("diff", pr_base, "--name-only", check=False)
    if diff.returncode == 0:
        for line in diff.stdout.splitlines():
            if line.strip() == "VERSION":
                return "Release guard: VERSION file changed on a feature branch."
    return None


def cmd_open(args: argparse.Namespace) -> int:
    """Run the gate and open a PR for a plan."""
    plan_path = Path(args.plan)
    if not plan_path.is_file():
        return _fail(f"Plan file not found: {plan_path}")

    print(f"Running aet ship open for {plan_path}")

    result = _run_gate(args)
    if not result.ok:
        return _fail(f"Gate failed: {result.message}")
    print("   Gate passed.")

    guard_error = _check_release_guard(result.pr_base)
    if guard_error:
        return _fail(guard_error)

    if _is_monolithic_commit(result.pr_base, plan_path):
        return _fail(
            "Monolithic commit detected: one commit spans the entire PR range "
            "while the plan lists multiple tasks.\n"
            "STOP and split the commit manually into logical pieces before opening the PR."
        )

    changelog_entry = _generate_changelog_entry(
        _commit_subjects(result.pr_base), plan_path
    )

    print("Pushing branch...")
    ok, output = _push_branch(result.rebased, args.dry_run)
    if not ok:
        return _fail(f"Push failed:\n{output}")
    if output.strip():
        print(f"   {output.strip()}")

    plan_id = plan_parser.parse_frontmatter(plan_path).get("id", plan_path.stem)
    title = f"{plan_id}: {plan_parser.title_from_plan(plan_path)}"
    body = _build_pr_body(plan_path, result.pr_base, result.scope_audit, changelog_entry)

    print("Creating PR...")
    ok, output = _create_pr(result.pr_base, title, body, args.dry_run)
    if not ok:
        return _fail(f"PR creation failed:\n{output}")
    if output.strip():
        print(f"   {output.strip()}")

    if result.pr_base != "origin/main":
        print(
            f"⚠️  STACKED PR: this PR targets {result.pr_base}, not main.\n"
            f"     After {result.pr_base} merges, rebase onto main and update the base before merging."
        )

    print("✅ aet ship open complete.")
    return 0


def _add_close_args(parser: argparse.ArgumentParser) -> None:
    """Add the post-merge closure arguments to *parser*."""
    parser.add_argument("task_id", help="Task ID to close.")
    parser.add_argument("plan", help="Path to the plan markdown file.")
    parser.add_argument(
        "queue",
        nargs="?",
        default=".agents/work-queue.json",
        help="Path to the work queue JSON file.",
    )
    parser.add_argument(
        "--branch",
        help="Branch name to use for merge verification. Overrides the task's branch field.",
    )
    parser.add_argument(
        "--merge-commit",
        help="Merge commit SHA to record directly. Must be an ancestor of origin/main.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aet ship",
        description="Pre-merge gate, PR creation, and post-merge closure for AE Toolkit tasks.",
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

    open_parser = sub.add_parser(
        "open",
        help="Run the gate and open a PR for the plan.",
    )
    open_parser.add_argument(
        "plan",
        help="Path to the plan markdown file.",
    )
    open_parser.add_argument(
        "--base",
        help="Override the PR base branch/ref (default: origin/main or stacked parent).",
    )
    open_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes.",
    )

    close_parser = sub.add_parser(
        "close",
        help="Record post-merge closure for a task.",
    )
    _add_close_args(close_parser)

    # Hidden alias kept for backward compatibility during the transition.
    record_merge_parser = sub.add_parser(
        "record-merge",
        help=argparse.SUPPRESS,
    )
    _add_close_args(record_merge_parser)

    # Default behavior when the first positional argument is a plan file.
    default_parser = sub.add_parser(
        "default",
        help=argparse.SUPPRESS,
    )
    default_parser.add_argument(
        "plan",
        help="Path to the plan markdown file.",
    )
    default_parser.add_argument(
        "--base",
        help="Override the PR base branch/ref (default: origin/main or stacked parent).",
    )
    default_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes.",
    )

    return parser


_KNOWN_SUBCOMMANDS = {"gate", "open", "close", "record-merge"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse arguments.

    A bare ``aet ship <plan_file>`` is treated as the default subcommand, which
    runs the gate and then opens a PR. Explicit subcommands are dispatched
    unchanged.
    """
    argv = list(argv or sys.argv[1:])
    if not argv:
        parser = build_parser()
        parser.print_help(sys.stderr)
        parser.exit(2)
    if argv[0] not in _KNOWN_SUBCOMMANDS and argv[0] not in ("--help", "-h"):
        argv.insert(0, "default")
    return build_parser().parse_args(argv)


def main(argv: list[str] | None = None):
    args = parse_args(argv)
    if args.command == "gate":
        return cmd_gate(args)
    if args.command == "open":
        return cmd_open(args)
    if args.command in ("close", "record-merge"):
        return cmd_ship(args)
    if args.command == "default":
        return cmd_default(args)
    return _fail(f"Unknown command: {args.command}")


class _ShipGroup(TyperGroup):
    """Click group that routes bare ``ship <plan>`` to a hidden default command.

    A callback with a positional ``plan`` argument cannot coexist with
    subcommands because Click consumes the first token for the callback before
    checking for a subcommand name. Inserting a hidden ``default`` command when
    the first positional is not a known subcommand preserves the legacy argparse
    routing exactly.
    """

    default_command_name = "default"

    def resolve_command(self, ctx, args):
        if args and not args[0].startswith("-"):
            if args[0] not in self.commands:
                args = [self.default_command_name, *args]
        return super().resolve_command(ctx, args)


app = typer.Typer(
    name="ship",
    help="Pre-merge gate, PR creation, and post-merge closure for AE Toolkit tasks.",
    cls=_ShipGroup,
)


@app.command(name="default", hidden=True)
def ship_default(
    plan: str = typer.Argument(..., help="Path to the plan markdown file."),
    base: Optional[str] = typer.Option(
        None,
        "--base",
        help="Override the PR base branch/ref (default: origin/main or stacked parent).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be done without making changes.",
    ),
) -> None:
    """Run the gate and, if it passes, open a PR (default behavior)."""
    rc = cmd_default(argparse.Namespace(plan=plan, base=base, dry_run=dry_run))
    raise typer.Exit(rc)


@app.command(name="gate")
def ship_gate(
    plan: str = typer.Argument(..., help="Path to the plan markdown file."),
    base: Optional[str] = typer.Option(
        None,
        "--base",
        help="Override the PR base branch/ref (default: origin/main or stacked parent).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be done without making changes.",
    ),
) -> None:
    """Run the pre-merge validation gate."""
    rc = cmd_gate(argparse.Namespace(plan=plan, base=base, dry_run=dry_run))
    raise typer.Exit(rc)


@app.command(name="open")
def ship_open(
    plan: str = typer.Argument(..., help="Path to the plan markdown file."),
    base: Optional[str] = typer.Option(
        None,
        "--base",
        help="Override the PR base branch/ref (default: origin/main or stacked parent).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be done without making changes.",
    ),
) -> None:
    """Run the gate and open a PR for the plan."""
    rc = cmd_open(argparse.Namespace(plan=plan, base=base, dry_run=dry_run))
    raise typer.Exit(rc)


def _run_ship_close(
    task_id: str,
    plan: str,
    queue: str,
    branch: Optional[str],
    merge_commit: Optional[str],
    dry_run: bool,
) -> int:
    return cmd_ship(
        argparse.Namespace(
            command="record-merge",
            task_id=task_id,
            plan=plan,
            queue=queue,
            dry_run=dry_run,
            branch=branch,
            merge_commit=merge_commit,
        )
    )


@app.command(name="close")
def ship_close(
    task_id: str = typer.Argument(..., help="Task ID to close."),
    plan: str = typer.Argument(..., help="Path to the plan markdown file."),
    queue: str = typer.Argument(
        ".agents/work-queue.json",
        help="Path to the work queue JSON file.",
    ),
    branch: Optional[str] = typer.Option(
        None,
        "--branch",
        help="Branch name to use for merge verification. Overrides the task's branch field.",
    ),
    merge_commit: Optional[str] = typer.Option(
        None,
        "--merge-commit",
        help="Merge commit SHA to record directly. Must be an ancestor of origin/main.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be done without making changes.",
    ),
) -> None:
    """Record post-merge closure for a task."""
    raise typer.Exit(
        _run_ship_close(task_id, plan, queue, branch, merge_commit, dry_run)
    )


@app.command(name="record-merge")
def ship_record_merge(
    task_id: str = typer.Argument(..., help="Task ID to close."),
    plan: str = typer.Argument(..., help="Path to the plan markdown file."),
    queue: str = typer.Argument(
        ".agents/work-queue.json",
        help="Path to the work queue JSON file.",
    ),
    branch: Optional[str] = typer.Option(
        None,
        "--branch",
        help="Branch name to use for merge verification. Overrides the task's branch field.",
    ),
    merge_commit: Optional[str] = typer.Option(
        None,
        "--merge-commit",
        help="Merge commit SHA to record directly. Must be an ancestor of origin/main.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be done without making changes.",
    ),
) -> None:
    """Hidden alias for close."""
    raise typer.Exit(
        _run_ship_close(task_id, plan, queue, branch, merge_commit, dry_run)
    )


if __name__ == "__main__":
    app()
