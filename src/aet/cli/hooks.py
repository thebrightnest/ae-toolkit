#!/usr/bin/env python3
"""aet hooks — generate the pre-push gate shim and check gate evidence.

Subcommands:

  install   Write a self-contained ``.git/hooks/pre-push`` shim. Idempotent:
            rewrites a prior AET shim in place and leaves a pre-existing
            non-AET hook untouched with a warning rather than clobbering it.
  check     Read pushed refs from stdin (git's pre-push protocol) and refuse
            the push when a task branch is missing required gate evidence.

Standard-library only. The gate logic is not reinvented here: the check reuses
the shared evidence / plan / workflow contract from the installed ``aet`` package
so task-branch detection, required-stage resolution, and verdict paths stay
consistent with the orchestrator. The shim's ``aet hooks check`` call works in any
repo where ``aet`` is on PATH — including a Mode-1 client repo that commits
nothing about AET (R-9/R-10).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer

from aet import gate, plan_parser  # noqa: E402

# Marker embedded in every shim this tool generates. ``install`` rewrites a
# hook only when this marker is present; a hook without it is left untouched.
SHIM_MARKER = "aet:generated pre-push shim"

ZERO_SHA = "0" * 40

# The generated shim is self-contained: it embeds the deletion short-circuit,
# delegates the gate-evidence check to the globally-installed `aet` binary, and
# chains to an optional repo-local companion. It never depends on a committed
# AET file in the repo. ``__AET_MARKER__``/``__AET_ZERO__`` are substituted at
# write time so no format-brace escaping fights the bash ``${...}`` syntax.
_SHIM_TEMPLATE = """#!/usr/bin/env bash
# __AET_MARKER__ — regenerate with `aet hooks install`; do not edit by hand.
set -euo pipefail

remote="${1:-}"
url="${2:-}"

# Capture the ref list git sends on stdin so both checks below can read it.
refs="$(cat)"

# (1) Short-circuit when every pushed ref is a branch deletion.
all_deletions=true
while read -r local_ref local_sha remote_ref remote_sha; do
  if [ "$local_sha" != "__AET_ZERO__" ]; then
    all_deletions=false
    break
  fi
done <<< "$refs"

if [ "$all_deletions" = true ]; then
  exit 0
fi

# (2) AET gate-evidence check. Refuses the push when a task branch is missing
# a required gate verdict. Delegated to the globally-installed `aet` binary so
# the logic evolves with the toolkit rather than freezing at install time.
printf '%s\\n' "$refs" | aet hooks check

# (3) Chain to an optional repo-local companion (e.g. a coverage gate) when the
# repo provides one. Absent in Mode-1 installs; never required by AET.
if [ -x "scripts/hooks/pre-push" ]; then
  printf '%s\\n' "$refs" | "scripts/hooks/pre-push" "$remote" "$url"
fi

exit 0
"""


def _shim_body() -> str:
    return _SHIM_TEMPLATE.replace("__AET_MARKER__", SHIM_MARKER).replace(
        "__AET_ZERO__", ZERO_SHA
    )


def _resolve_repo_root(repo_arg: str | None) -> Path:
    if repo_arg:
        return Path(repo_arg).resolve()
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        print("error: not inside a git repository", file=sys.stderr)
        sys.exit(2)
    return Path(out.stdout.strip())


def _hooks_dir(repo_root: Path) -> Path:
    """Resolve the effective hooks dir (handles worktrees via --git-path)."""
    out = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--git-path", "hooks"],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        print(f"error: cannot resolve git hooks dir in {repo_root}", file=sys.stderr)
        sys.exit(2)
    path = Path(out.stdout.strip())
    if not path.is_absolute():
        path = repo_root / path
    return path


def cmd_install(args: argparse.Namespace) -> int:
    """Generate the self-contained pre-push shim; idempotent, non-clobbering."""
    repo_root = _resolve_repo_root(args.repo)
    hooks_dir = _hooks_dir(repo_root)
    target = hooks_dir / "pre-push"

    if target.exists():
        existing = target.read_text(encoding="utf-8", errors="ignore")
        if SHIM_MARKER not in existing:
            print(
                f"warning: an existing non-AET pre-push hook is present at {target}; "
                "leaving it in place. Move it aside (or merge its logic into "
                "scripts/hooks/pre-push, which the shim chains to) and re-run "
                "`aet hooks install` to enable the gate.",
                file=sys.stderr,
            )
            return 0
        # Prior AET shim: rewrite in place (idempotent).

    hooks_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(_shim_body(), encoding="utf-8")
    target.chmod(0o755)
    print(f"installed pre-push gate shim -> {target}")
    return 0


def _parse_refs(text: str) -> list[tuple[str, str, str, str]]:
    """Parse git pre-push stdin lines: <local_ref> <local_sha> <remote_ref> <remote_sha>."""
    refs = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 4:
            refs.append((parts[0], parts[1], parts[2], parts[3]))
    return refs


def _branch_from_ref(ref: str) -> str | None:
    """Return the branch name for a heads ref, else None (tags, notes, etc.)."""
    prefix = "refs/heads/"
    return ref[len(prefix) :] if ref.startswith(prefix) else None


def cmd_check(args: argparse.Namespace) -> int:
    """Refuse the push when a task branch is missing required gate evidence."""
    repo_root = _resolve_repo_root(args.repo)
    refs = _parse_refs(sys.stdin.read())
    failures: list[str] = []

    for local_ref, local_sha, _remote_ref, _remote_sha in refs:
        if local_sha == ZERO_SHA:
            continue  # branch deletion — nothing to gate
        branch = _branch_from_ref(local_ref)
        if branch is None:
            continue
        plan = gate.plan_for_branch(repo_root, branch)
        if plan is None:
            continue  # non-task branch — no gate imposed
        plan_fm = plan_parser.parse_frontmatter(plan)
        _ok, task_failures = gate.check_task_evidence(branch, plan_fm, repo_root)
        failures.extend(task_failures)

    if failures:
        print(
            "pre-push gate: refusing push — missing required gate evidence:",
            file=sys.stderr,
        )
        for line in failures:
            print(line, file=sys.stderr)
        print(
            "Run the missing stages so each records a passing verdict "
            "(e.g. `aet run-one <plan>`), then push again.",
            file=sys.stderr,
        )
        return 1
    return 0


app = typer.Typer()


@app.command("install")
def install(
    repo: Optional[str] = typer.Option(None, "--repo", help="Repo root (default: current git toplevel)."),
) -> None:
    """Generate the self-contained .git/hooks/pre-push shim."""
    args = argparse.Namespace(repo=repo)
    rc = cmd_install(args)
    raise typer.Exit(rc)


@app.command("check")
def check(
    repo: Optional[str] = typer.Option(None, "--repo", help="Repo root (default: current git toplevel)."),
) -> None:
    """Check gate evidence for pushed refs read from stdin."""
    args = argparse.Namespace(repo=repo)
    rc = cmd_check(args)
    raise typer.Exit(rc)


if __name__ == "__main__":
    app()
