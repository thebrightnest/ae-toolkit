#!/usr/bin/env python3
"""aet-ship — Pre-merge gate, PR creation, and post-merge closure for AE Toolkit tasks.

Usage:
  aet ship <plan_file|task_id>        Run the gate, then open a PR.
  aet ship gate <plan_file|task_id>   Run the pre-merge gate (steps 1-9).
  aet ship open <plan_file|task_id>   Run the gate and open a PR.
  aet ship merge <plan_file|task_id> --branch <target>
                                      Run the gate, detect conflicts against the target branch,
                                      merge directly into it, and record closure.
  aet ship close <plan_file>          Record post-merge closure (task id derived from plan frontmatter).
  aet ship close <task_id>            Record post-merge closure (plan derived from queue task).
  aet ship close <task_id> <plan_file> [queue_file]
                                      Record post-merge closure (explicit identifiers).
  aet ship record-merge <task_id> <plan_file> [queue_file]
                                      Hidden alias for ``close``.

A bare task id given to ``gate``, ``open``, ``merge``, or the default command resolves to
the conventional ``docs/plans/<task_id>.md`` path. The pre-merge gate, PR
creation, direct merge, and merge closure are all implemented in code.
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


def _task_id_from_plan(plan_path: str | Path) -> str:
    """Return the task id from a plan file's YAML frontmatter, falling back to the filename stem."""
    path = Path(plan_path)
    if not path.is_file():
        raise ValueError(f"Plan file not found: {path}")
    task_id = plan_parser.parse_frontmatter(path).get("id")
    if not task_id:
        return path.stem
    return task_id


def _resolve_feature_branch(task_id: str) -> Optional[str]:
    """Resolve a task's feature branch by name.

    The orchestrator names each task's branch after its task id (it sets
    ``qt["branch"] = task_id`` when recording a task in-progress), so the merge
    source is the ``task_id`` ref — never whatever branch happens to be checked
    out. Prefer the local branch; fall back to the remote-tracking ref. Return
    ``None`` when neither exists so callers fail closed instead of merging a
    branch into itself and recording a merge that never happened.
    """
    for ref in (task_id, f"origin/{task_id}"):
        if _run_git("rev-parse", "--verify", "--quiet", ref, check=False).returncode == 0:
            return ref
    return None


def _normalize_close_args(
    task_id: str,
    plan: Optional[str],
    queue: str,
) -> tuple[str, Optional[str], str]:
    """Resolve flexible ``aet ship close`` argument forms to (task_id, plan, queue).

    Supported forms:
      - ``close <plan_file>`` — derive task id from plan frontmatter.
      - ``close <plan_file> <queue_file>`` — derive task id; explicit queue.
      - ``close <task_id>`` — plan is read from the queue task's ``plan_file``.
      - ``close <task_id> <plan_file>`` — explicit task id and plan.
      - ``close <task_id> <plan_file> <queue_file>`` — explicit identifiers.

    The second positional is constrained to avoid silent misinterpretation:
    when the first argument is a plan file, the second must not also be a
    ``.md`` path (that would be two plans); when the first argument is a task
    id, the second must be a ``.md`` plan path (use the third positional for
    the queue).
    """

    def _is_plan_path(value: str) -> bool:
        return value.lower().endswith(".md")

    if _is_plan_path(task_id):
        resolved_plan = task_id
        resolved_task_id = _task_id_from_plan(resolved_plan)
        if plan and _is_plan_path(plan):
            raise ValueError(
                f"Ambiguous closure arguments: both '{task_id}' and '{plan}' "
                "look like plan files. Pass the queue path as the second "
                "argument or omit it."
            )
        resolved_queue = plan if plan else queue
        return resolved_task_id, resolved_plan, resolved_queue

    resolved_task_id = task_id
    if plan:
        if not _is_plan_path(plan):
            raise ValueError(
                f"Expected a plan markdown path (.md) as the second argument, "
                f"got: {plan}. Use the third positional for the queue file."
            )
        resolved_plan = plan
        resolved_queue = queue
    else:
        resolved_plan = None
        resolved_queue = queue

    return resolved_task_id, resolved_plan, resolved_queue


def cmd_ship(args):
    """Run the post-merge closure for a task or epic."""
    try:
        task_id, plan, queue = _normalize_close_args(
            args.task_id,
            getattr(args, "plan", None),
            getattr(args, "queue", ".agents/work-queue.json"),
        )
    except ValueError as exc:
        return _fail(str(exc))

    target_branch = getattr(args, "target_branch", None)
    branch = getattr(args, "branch", None)

    # No-self-merge guard: closing a branch against itself is never valid.
    if target_branch and branch and target_branch == branch:
        return _fail(
            f"Self-merge refused: branch '{branch}' cannot be closed against target '{target_branch}'."
        )

    ns = aet_state.argparse.Namespace(
        command="record-merge",
        task_id=task_id,
        queue=queue,
        dry_run=args.dry_run,
        plan=plan,
        branch=branch,
        merge_commit=getattr(args, "merge_commit", None),
        target_branch=target_branch,
    )
    return aet_state.cmd_record_merge(ns)


def cmd_default(args: argparse.Namespace) -> int:
    """Run the gate and, if it passes, open a PR for a plan."""
    try:
        args.plan = plan_parser.resolve_plan_arg(args.plan)
    except ValueError as exc:
        return _fail(str(exc))
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
            if r.startswith("HEAD -> "):
                continue  # current branch — the one being shipped, never its own parent
            r = r.strip()
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
    try:
        args.plan = plan_parser.resolve_plan_arg(args.plan)
    except ValueError as exc:
        return _fail(str(exc))
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
    """Push the current branch to a same-named remote branch.

    Worktree branches are often tracked against ``origin/main``, so a bare
    ``git push`` is rejected. Always push ``HEAD:<branch>`` explicitly.
    """
    branch_result = _run_git("branch", "--show-current", check=False)
    branch = branch_result.stdout.strip()
    if not branch:
        return False, "Cannot push: HEAD is detached."

    push_spec = f"HEAD:{branch}"
    if rebased:
        cmd = ["git", "push", "--force-with-lease", "origin", push_spec]
    else:
        cmd = ["git", "push", "-u", "origin", push_spec]
    if dry_run:
        return True, f"Would run: {' '.join(cmd)}"
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0, result.stdout + result.stderr


def _create_pr(pr_base: str, title: str, body: str, dry_run: bool) -> tuple[bool, str]:
    """Create a GitHub PR using ``gh pr create``."""
    # ``gh`` expects a branch name, not a remote tracking ref.
    gh_base = pr_base.removeprefix("origin/")
    if dry_run:
        return True, f"Would create PR against `{gh_base}` with title: {title}"
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
                gh_base,
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
    try:
        args.plan = plan_parser.resolve_plan_arg(args.plan)
    except ValueError as exc:
        return _fail(str(exc))
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


def _has_merge_conflicts(target_branch: str) -> tuple[bool, str]:
    """Return (has_conflicts, message) for merging HEAD into origin/<target_branch>."""
    target_ref = f"origin/{target_branch}"
    base_result = _run_git("merge-base", "HEAD", target_ref, check=False)
    if base_result.returncode != 0:
        return True, f"Could not find merge base between HEAD and {target_ref}."
    merge_base = base_result.stdout.strip()
    tree_result = _run_git("merge-tree", merge_base, "HEAD", target_ref, check=False)
    if tree_result.returncode != 0:
        return True, f"Merge-tree failed for {target_ref}: {tree_result.stderr}"
    if any(line.startswith("<<<<<<< ") for line in tree_result.stdout.splitlines()):
        return (
            True,
            f"Merging HEAD into {target_ref} would produce conflicts. "
            "Rebase onto the target branch or resolve the conflicts first.",
        )
    return False, ""


def _find_target_worktree(branch: str) -> Optional[Path]:
    """Return the path of an existing worktree for *branch*, or None."""
    result = _run_git("worktree", "list", "--porcelain", check=False)
    if result.returncode != 0:
        return None
    current_path: Optional[Path] = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current_path = Path(line[len("worktree "):])
        elif line.startswith("branch ") and current_path is not None:
            ref = line[len("branch "):]
            if ref == f"refs/heads/{branch}":
                return current_path
    return None


def _create_temp_worktree(target_branch: str) -> Path:
    """Create a temporary worktree for origin/<target_branch> and return its path."""
    repo_root = Path(_run_git("rev-parse", "--show-toplevel").stdout.strip())
    worktree_dir = repo_root / ".worktrees" / f".merge-{target_branch}-{os.getpid()}"
    result = _run_git(
        "worktree", "add", "--checkout", str(worktree_dir), f"origin/{target_branch}",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Could not create worktree for {target_branch}: {result.stderr}"
        )
    return worktree_dir


def _remove_worktree(path: Path) -> None:
    """Remove a temporary worktree, ignoring errors."""
    _run_git("worktree", "remove", "--force", str(path), check=False)


def _merge_into_target(
    target_branch: str, feature_branch: str, dry_run: bool
) -> tuple[bool, str, Optional[str]]:
    """Merge *feature_branch* into *target_branch* and push.

    Returns (ok, message, merge_commit). *merge_commit* is None on failure or
    dry-run. Existing worktrees for the target branch are reused; otherwise a
    temporary worktree is created and removed.
    """
    target_ref = f"origin/{target_branch}"
    worktree = _find_target_worktree(target_branch)
    created = False
    if worktree is None:
        if dry_run:
            return (
                True,
                f"Would create a worktree for {target_ref}, merge {feature_branch} into "
                f"{target_branch}, and push {target_branch}.",
                None,
            )
        try:
            worktree = _create_temp_worktree(target_branch)
            created = True
        except RuntimeError as exc:
            return False, str(exc), None

    try:
        if dry_run:
            return (
                True,
                f"Would merge {feature_branch} into {target_branch} and push {target_branch}.",
                None,
            )

        checkout_result = _run_git(
            "-C", str(worktree), "checkout", target_branch, check=False
        )
        if checkout_result.returncode != 0:
            return False, f"Could not checkout {target_branch}: {checkout_result.stderr}", None

        pull_result = _run_git(
            "-C", str(worktree), "pull", "origin", target_branch, check=False
        )
        if pull_result.returncode != 0:
            return False, f"Could not pull {target_ref}: {pull_result.stderr}", None

        merge_message = f"Merge {feature_branch} into {target_branch}"
        merge_result = _run_git(
            "-C",
            str(worktree),
            "merge",
            "--no-ff",
            "-m",
            merge_message,
            feature_branch,
            check=False,
        )
        if merge_result.returncode != 0:
            _run_git("-C", str(worktree), "merge", "--abort", check=False)
            return (
                False,
                f"Merge into {target_branch} failed:\n{merge_result.stdout}\n{merge_result.stderr}",
                None,
            )

        sha_result = _run_git("-C", str(worktree), "rev-parse", "HEAD", check=False)
        if sha_result.returncode != 0:
            return False, f"Could not read merge commit SHA: {sha_result.stderr}", None
        merge_commit = sha_result.stdout.strip()

        push_result = _run_git(
            "-C", str(worktree), "push", "origin", target_branch, check=False
        )
        if push_result.returncode != 0:
            return (
                False,
                f"Push of {target_branch} failed:\n{push_result.stdout}\n{push_result.stderr}",
                None,
            )

        # Fail-closed post-condition: the feature branch must be an ancestor of the
        # target after the merge. Catches silent no-op merges (e.g. an already-merged
        # or misresolved source) that would otherwise report success while leaving the
        # branch's commits behind.
        ancestry = _run_git(
            "-C", str(worktree), "merge-base", "--is-ancestor",
            feature_branch, target_branch, check=False,
        )
        if ancestry.returncode != 0:
            return (
                False,
                f"Post-merge verification failed: {feature_branch} is not an ancestor "
                f"of {target_branch} after the merge. The branch was not incorporated; "
                "refusing to report success.",
                None,
            )

        return (
            True,
            f"Merged {feature_branch} into {target_branch} ({merge_commit}).",
            merge_commit,
        )
    finally:
        if created:
            _remove_worktree(worktree)


def cmd_merge(args: argparse.Namespace) -> int:
    """Run the gate, detect conflicts, merge directly into a target branch, and close."""
    try:
        args.plan = plan_parser.resolve_plan_arg(args.plan)
    except ValueError as exc:
        return _fail(str(exc))
    plan_path = Path(args.plan)
    if not plan_path.is_file():
        return _fail(f"Plan file not found: {plan_path}")

    target_branch = args.branch
    task_id = _task_id_from_plan(plan_path)
    feature_branch = _resolve_feature_branch(task_id)
    if not feature_branch:
        return _fail(
            f"Cannot resolve a feature branch for task {task_id!r}: neither "
            f"{task_id!r} nor origin/{task_id} exists. Refusing to record a merge "
            "that did not happen."
        )
    if feature_branch == target_branch:
        return _fail(
            f"Refusing to merge {feature_branch!r} into itself: the resolved feature "
            f"branch equals the target branch ({target_branch!r})."
        )

    print(f"Running aet ship merge for {plan_path} into {target_branch}")

    # The gate should treat the target branch as the merge base so tests and
    # checks run against the same integration point we will merge into.
    args.base = f"origin/{target_branch}"
    result = _run_gate(args)
    if not result.ok:
        return _fail(f"Gate failed: {result.message}")
    print("   Gate passed.")

    guard_error = _check_release_guard(result.pr_base)
    if guard_error:
        return _fail(guard_error)

    if _is_monolithic_commit(result.pr_base, plan_path):
        return _fail(
            "Monolithic commit detected: one commit spans the entire merge range "
            "while the plan lists multiple tasks.\n"
            "STOP and split the commit manually into logical pieces before merging."
        )

    print(f"Checking for merge conflicts against origin/{target_branch}...")
    has_conflicts, conflict_msg = _has_merge_conflicts(target_branch)
    if has_conflicts:
        return _fail(conflict_msg)
    print("   No conflicts detected.")

    print(f"Merging {feature_branch} into {target_branch}...")
    ok, msg, merge_commit = _merge_into_target(target_branch, feature_branch, args.dry_run)
    if not ok:
        return _fail(msg)
    print(f"   {msg}")

    if args.dry_run:
        print("✅ aet ship merge complete (dry-run).")
        return 0

    rc = aet_state.cmd_record_merge(
        argparse.Namespace(
            command="record-merge",
            task_id=task_id,
            queue=".agents/work-queue.json",
            plan=str(plan_path),
            dry_run=False,
            branch=task_id,
            merge_commit=merge_commit,
            target_branch=target_branch,
        )
    )
    if rc != 0:
        return _fail(
            "Merge succeeded, but recording closure failed. "
            "Run `aet ship close` manually to finish."
        )

    print("✅ aet ship merge complete.")
    return 0


def _add_close_args(parser: argparse.ArgumentParser) -> None:
    """Add the post-merge closure arguments to *parser*."""
    parser.add_argument(
        "task_id",
        help="Task ID to close, or path to the plan markdown file.",
    )
    parser.add_argument(
        "plan",
        nargs="?",
        default=None,
        help=(
            "Plan path (when first arg is a task ID) or queue path (when first arg is a plan). "
            "Must be a .md file unless the first arg is already a plan."
        ),
    )
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
        "--target-branch",
        help="Target branch the source branch merged into (default: configured integration branch). "
        "Use 'main' when closing an epic whose integration branch merged to trunk.",
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
        help="Path to the plan markdown file, or a task id (resolved to docs/plans/<id>.md).",
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
        help="Path to the plan markdown file, or a task id (resolved to docs/plans/<id>.md).",
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

    merge_parser = sub.add_parser(
        "merge",
        help="Run the gate, detect conflicts, merge directly into a target branch, and close.",
    )
    merge_parser.add_argument(
        "plan",
        help="Path to the plan markdown file, or a task id (resolved to docs/plans/<id>.md).",
    )
    merge_parser.add_argument(
        "--branch",
        default="main",
        help="Target branch to merge into (default: main).",
    )
    merge_parser.add_argument(
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
        help="Path to the plan markdown file, or a task id (resolved to docs/plans/<id>.md).",
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


_KNOWN_SUBCOMMANDS = {"gate", "open", "merge", "close", "record-merge"}


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
    if args.command == "merge":
        return cmd_merge(args)
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
    plan: str = typer.Argument(
        ...,
        help="Path to the plan markdown file, or a task id (resolved to docs/plans/<id>.md).",
    ),
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
    plan: str = typer.Argument(
        ...,
        help="Path to the plan markdown file, or a task id (resolved to docs/plans/<id>.md).",
    ),
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
    plan: str = typer.Argument(
        ...,
        help="Path to the plan markdown file, or a task id (resolved to docs/plans/<id>.md).",
    ),
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


@app.command(name="merge")
def ship_merge(
    plan: str = typer.Argument(
        ...,
        help="Path to the plan markdown file, or a task id (resolved to docs/plans/<id>.md).",
    ),
    branch: str = typer.Option(
        "main",
        "--branch",
        help="Target branch to merge into (default: main).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be done without making changes.",
    ),
) -> None:
    """Run the gate, detect conflicts, merge directly into a target branch, and close."""
    rc = cmd_merge(argparse.Namespace(plan=plan, branch=branch, dry_run=dry_run))
    raise typer.Exit(rc)


def _run_ship_close(
    task_id: str,
    plan: Optional[str],
    queue: str,
    branch: Optional[str],
    merge_commit: Optional[str],
    target_branch: Optional[str],
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
            target_branch=target_branch,
        )
    )


@app.command(name="close")
def ship_close(
    task_id: str = typer.Argument(
        ...,
        help="Task ID to close, or path to the plan markdown file.",
    ),
    plan: Optional[str] = typer.Argument(
        None,
        help=(
            "Plan path (when first arg is a task ID) or queue path (when first arg is a plan). "
            "Must be a .md file unless the first arg is already a plan."
        ),
    ),
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
    target_branch: Optional[str] = typer.Option(
        None,
        "--target-branch",
        help="Target branch the source branch merged into (default: configured integration branch). "
        "Use 'main' when closing an epic whose integration branch merged to trunk.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be done without making changes.",
    ),
) -> None:
    """Record post-merge closure for a task."""
    resolved_task_id, resolved_plan, resolved_queue = _normalize_close_args(
        task_id, plan, queue
    )
    raise typer.Exit(
        _run_ship_close(
            resolved_task_id,
            resolved_plan,
            resolved_queue,
            branch,
            merge_commit,
            target_branch,
            dry_run,
        )
    )


@app.command(name="record-merge")
def ship_record_merge(
    task_id: str = typer.Argument(
        ...,
        help="Task ID to close, or path to the plan markdown file.",
    ),
    plan: Optional[str] = typer.Argument(
        None,
        help=(
            "Plan path (when first arg is a task ID) or queue path (when first arg is a plan). "
            "Must be a .md file unless the first arg is already a plan."
        ),
    ),
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
    target_branch: Optional[str] = typer.Option(
        None,
        "--target-branch",
        help="Target branch the source branch merged into (default: configured integration branch). "
        "Use 'main' when closing an epic whose integration branch merged to trunk.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be done without making changes.",
    ),
) -> None:
    """Hidden alias for close."""
    resolved_task_id, resolved_plan, resolved_queue = _normalize_close_args(
        task_id, plan, queue
    )
    raise typer.Exit(
        _run_ship_close(
            resolved_task_id,
            resolved_plan,
            resolved_queue,
            branch,
            merge_commit,
            target_branch,
            dry_run,
        )
    )


if __name__ == "__main__":
    app()
