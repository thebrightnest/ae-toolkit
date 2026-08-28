"""aet context — emit session workflow context.

Implements the canonical battery of Shared Preamble values as a read-only
JSON-plus-banner command.  Every collector fails open: missing files,
malformed lines, or non-git directories yield ``None`` rather than raising.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer

from aet import context_digest
from aet.plan_parser import (
    build_ticket_map,
    most_recent_plan,
    most_recent_prd,
    stage_from_plan,
)

app = typer.Typer(invoke_without_command=True)

SCHEMA_VERSION = 1
BANNER = "📍 Current stage: {stage}."
PLANS_GLOB = "docs/plans/*.md"
PRDS_GLOB = "docs/prds/*.md"
LEARNINGS_FILE = ".agents/learnings.jsonl"
PRIME_FILE = "PRIME.md"
AGENTS_FILE = "AGENTS.md"
LAST_PIV_MAX_COMMITS = 200
LAST_PIV_LOOKBACK_DAYS = 365
ACTIVE_PLAN_DAYS = 7

BUDGET_CHOICES = ("auto", "cli", "mcp")
HOOK_CHOICES = ("claude-code", "codex", "gemini")
MCP_ENV_MARKERS = (
    "AET_MCP_SESSION",
    "MCP_SESSION_ID",
    "KIMI_CODE_MCP",
    "CLAUDE_MCP",
    "CODEX_MCP",
)


def _run_git(
    args: list[str], cwd: Path, check: bool = False
) -> subprocess.CompletedProcess[str]:
    """Run a git command, returning a CompletedProcess with captured output."""
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=check
    )


def _is_git_repo(cwd: Path) -> bool:
    """Return True if ``cwd`` is inside a git repository."""
    return _run_git(["rev-parse", "--git-dir"], cwd).returncode == 0


def _git_root(cwd: Path) -> Path | None:
    """Return the git repository root, or None when not in a repo."""
    result = _run_git(["rev-parse", "--show-toplevel"], cwd)
    if result.returncode != 0:
        return None
    path = result.stdout.strip()
    if path:
        return Path(path)
    return None


def _to_iso_mtime(path: Path) -> str | None:
    """Return an ISO-8601 UTC mtime string for ``path``, or None."""
    try:
        mtime = path.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    except OSError:
        return None


def _parse_iso_timestamp(value: str) -> datetime | None:
    """Parse an ISO-8601 timestamp, including legacy ``date`` shapes."""
    value = value.strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def _repo_relative(path: Path, repo_root: Path) -> str:
    """Return a repo-relative path string for ``path``.

    Both sides are resolved before comparing: ``_git_root`` returns git's own
    answer, which has symlinks resolved, while collected paths are built from
    the working directory as given. Under a symlinked root — macOS `/var`, a
    home directory on another volume — the two spellings differ and
    ``relative_to`` raises, which used to fail open to an absolute path in the
    digest (docs/bugs/20260828-context-digest-absolute-paths-under-symlink.md).
    """
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except (ValueError, OSError):
        return str(path)


# ---------------------------------------------------------------------------
# Collectors
# ---------------------------------------------------------------------------


def collect_branch(cwd: Path) -> str | None:
    """Return the current git branch name, or None."""
    if not _is_git_repo(cwd):
        return None
    result = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
    if result.returncode != 0:
        return None
    branch = result.stdout.strip()
    return branch or None


def collect_repo_state(cwd: Path) -> str | None:
    """Classify the working tree as clean, dirty, or merge-conflict."""
    if not _is_git_repo(cwd):
        return None

    root = _git_root(cwd)
    if root is None:
        return None

    # MERGE_HEAD is the strongest signal of an in-progress merge.
    if (root / ".git" / "MERGE_HEAD").exists():
        return "merge-conflict"

    result = _run_git(["status", "--porcelain"], cwd)
    if result.returncode != 0:
        return None

    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        return "clean"

    # Unmerged entries are reported with two-letter codes in the first column.
    unmerged_codes = {"UU", "DD", "AU", "UA", "DU", "UD", "AA"}
    for line in lines:
        if len(line) >= 2 and line[:2] in unmerged_codes:
            return "merge-conflict"

    return "dirty"


def collect_agents_md(cwd: Path) -> dict[str, Any] | None:
    """Return AGENTS.md presence and mtime."""
    path = cwd / AGENTS_FILE
    if not path.is_file():
        return None
    mtime = _to_iso_mtime(path)
    if mtime is None:
        return None
    return {"path": _repo_relative(path, cwd), "mtime": mtime}


def _parse_learnings_line(line: str) -> dict[str, Any] | None:
    """Parse one learnings.jsonl entry, returning None for malformed lines."""
    line = line.strip()
    if not line:
        return None
    try:
        entry = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(entry, dict):
        return None
    raw_ts = entry.get("timestamp") or entry.get("date")
    if not isinstance(raw_ts, str):
        return None
    dt = _parse_iso_timestamp(raw_ts)
    if dt is None:
        return None
    return {"entry": entry, "dt": dt}


def collect_learnings(cwd: Path, limit: int = 3) -> list[dict[str, Any]]:
    """Return the top-``limit`` most recent learnings entries."""
    path = cwd / LEARNINGS_FILE
    if not path.is_file():
        return []

    parsed: list[tuple[datetime, dict[str, Any]]] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                parsed_entry = _parse_learnings_line(line)
                if parsed_entry is None:
                    continue
                parsed.append((parsed_entry["dt"], parsed_entry["entry"]))
    except OSError:
        return []

    parsed.sort(key=lambda item: item[0], reverse=True)
    return [entry for _, entry in parsed[:limit]]


def _plan_files(plans_dir: Path) -> list[Path]:
    """Return all plan files in ``plans_dir``."""
    if not plans_dir.exists():
        return []
    return list(plans_dir.glob("*.md"))


def _recent_plan(plans_dir: Path, days: int) -> Path | None:
    """Return the most recently modified plan newer than ``days`` days, or None."""
    if not plans_dir.exists():
        return None
    cutoff = datetime.now(tz=timezone.utc).timestamp() - (days * 86400)
    candidates = [p for p in plans_dir.glob("*.md") if p.stat().st_mtime >= cutoff]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def collect_active_plan(cwd: Path, plans_dir: Path) -> str | None:
    """Return the most recently modified plan edited in the last ``days`` days."""
    recent = _recent_plan(plans_dir, ACTIVE_PLAN_DAYS)
    if recent is None:
        return None
    return _repo_relative(recent, cwd)


def collect_last_piv(cwd: Path) -> str | None:
    """Return the most recent commit date touching both plans and src/tests.

    Scans up to ``LAST_PIV_MAX_COMMITS`` commits.  A commit counts when it
    touches ``docs/plans/*.md`` and either ``src/`` or ``tests/``.
    """
    if not _is_git_repo(cwd):
        return None

    result = _run_git(
        ["log", f"-{LAST_PIV_MAX_COMMITS}", "--format=%H", "--", "docs/plans/"],
        cwd,
    )
    if result.returncode != 0:
        return None

    candidates = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not candidates:
        return None

    # The newest commit that also touches src/ or tests/ is the last PIV.
    for commit in candidates:
        files_result = _run_git(
            ["diff-tree", "--no-commit-id", "--name-only", "-r", "--root", commit], cwd
        )
        if files_result.returncode != 0:
            continue
        files = files_result.stdout.splitlines()
        has_src_or_tests = any(f.startswith("src/") or f.startswith("tests/") for f in files)
        if not has_src_or_tests:
            continue

        date_result = _run_git(["log", "-1", "--format=%cI", commit], cwd)
        if date_result.returncode != 0:
            continue
        date = date_result.stdout.strip()
        if date:
            return date

    return None


def collect_active_prd_stage(cwd: Path) -> str | None:
    """Return the stage of the most recently modified PRD."""
    prd = most_recent_prd(cwd / "docs" / "prds")
    if prd is None:
        return None
    return stage_from_plan(prd)


def collect_active_plan_stage(cwd: Path, plans_dir: Path) -> str | None:
    """Return the stage of the most recently modified plan."""
    plan = most_recent_plan(plans_dir)
    if plan is None:
        return None
    return stage_from_plan(plan)


# ---------------------------------------------------------------------------
# Context assembly
# ---------------------------------------------------------------------------


def _resolve_target(
    target: str | None, cwd: Path, plans_dir: Path
) -> tuple[Path | None, str | None]:
    """Resolve a TARGET argument to a plan path and its stage.

    Returns ``(path, stage)``.  Raises ``ValueError`` when the target cannot be
    resolved to an existing plan.
    """
    if target is None:
        return None, None

    # Plan paths are passed through unchanged.
    if target.lower().endswith(".md"):
        candidate = cwd / target
        if not candidate.is_file():
            candidate = Path(target)
        if not candidate.is_file():
            raise ValueError(f"Plan not found: {target}")
        return candidate, stage_from_plan(candidate)

    # Ticket numbers resolve through the title map.
    if target.isdigit():
        plans = _plan_files(plans_dir)
        ticket_map = build_ticket_map(plans)
        task_id = ticket_map.get(target.lstrip("0") or "0")
        if task_id is not None:
            candidate = plans_dir / f"{task_id}.md"
            if candidate.is_file():
                return candidate, stage_from_plan(candidate)

    # Bare task id.
    candidate = plans_dir / f"{target}.md"
    if candidate.is_file():
        return candidate, stage_from_plan(candidate)

    raise ValueError(f"Plan not found: '{target}'")


def build_context(
    cwd: Path,
    target: str | None = None,
) -> tuple[dict[str, Any], Path | None]:
    """Build the JSON battery and optional pinned plan path.

    Returns ``(battery, pinned_plan)``.  Collector failures are represented as
    ``None`` values in the battery; the function itself never raises.
    """
    plans_dir = cwd / "docs" / "plans"

    pinned_plan: Path | None = None
    pinned_stage: str | None = None
    try:
        pinned_plan, pinned_stage = _resolve_target(target, cwd, plans_dir)
    except ValueError:
        pinned_plan = None
        pinned_stage = None

    battery: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "branch": collect_branch(cwd),
        "repo_state": collect_repo_state(cwd),
        "agents_md": collect_agents_md(cwd),
        "learnings": collect_learnings(cwd, limit=3),
        "active_plan": (
            _repo_relative(pinned_plan, cwd) if pinned_plan else collect_active_plan(cwd, plans_dir)
        ),
        "last_piv": collect_last_piv(cwd),
        "active_prd_stage": collect_active_prd_stage(cwd),
        "active_plan_stage": pinned_stage or collect_active_plan_stage(cwd, plans_dir),
        "rules_digest": context_digest.build_rules_digest(cwd / "docs" / "adr"),
        "durable_insights": context_digest.select_durable_insights(cwd / LEARNINGS_FILE),
    }

    prime_path = cwd / PRIME_FILE
    if prime_path.is_file():
        battery["prime_md_override"] = True

    return battery, pinned_plan


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _resolve_budget(budget_arg: str | None, env: dict[str, str | None]) -> str:
    """Resolve the effective budget from flag → env → MCP markers → cli."""
    if budget_arg is not None and budget_arg != "auto":
        return budget_arg
    env_client = env.get("AET_CONTEXT_CLIENT")
    if env_client in BUDGET_CHOICES and env_client != "auto":
        return env_client
    if budget_arg == "auto" and env_client in BUDGET_CHOICES and env_client != "auto":
        return env_client
    for marker in MCP_ENV_MARKERS:
        if env.get(marker):
            return "mcp"
    return "cli"


def _compact_learnings(learnings: list[dict[str, Any]]) -> str:
    """Render learnings as single-line compact entries."""
    if not learnings:
        return "No recent learnings."
    lines = []
    for entry in learnings:
        ts = entry.get("timestamp") or entry.get("date", "unknown")
        triggers = entry.get("trigger", [])
        if isinstance(triggers, list):
            trigger_str = ",".join(str(t) for t in triggers)
        else:
            trigger_str = str(triggers)
        problem = entry.get("problem", "")
        summary = problem.splitlines()[0] if problem else ""
        lines.append(f"[{ts}] {trigger_str}: {summary}")
    return "\n".join(lines)


def _human_render(
    battery: dict[str, Any],
    budget: str,
    max_lines: int | None,
    memories_only: bool,
    stage: str | None,
) -> str:
    """Render the human-facing output block."""
    lines: list[str] = []
    if stage:
        lines.append(BANNER.format(stage=stage))

    if memories_only:
        lines.append(_compact_learnings(battery.get("learnings", [])))
    elif budget == "mcp":
        # Compact: rules digest, top-1 learning, minimal key/value pairs.
        lines.append(context_digest.render_digest_section(battery.get("rules_digest", [])))
        learnings = battery.get("learnings", [])
        if learnings:
            lines.append(_compact_learnings(learnings[:1]))
        else:
            lines.append("No recent learnings.")
        for key in ("branch", "repo_state", "active_plan", "active_plan_stage"):
            value = battery.get(key)
            if value is not None:
                lines.append(f"{key}: {value}")
    else:
        lines.append(context_digest.render_digest_section(battery.get("rules_digest", [])))
        lines.append(json.dumps(battery, indent=2, ensure_ascii=False))

    output = "\n".join(lines)
    if max_lines is not None and max_lines >= 0:
        output_lines = output.splitlines()
        output = "\n".join(output_lines[:max_lines])

    return output


def _hook_envelope(content: str, harness: str) -> dict[str, Any]:
    """Wrap rendered content in the SessionStart envelope."""
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": content,
            "harness": harness,
        }
    }


def _render_output(
    battery: dict[str, Any],
    *,
    json_only: bool,
    hook_harness: str | None,
    budget: str,
    max_lines: int | None,
    memories_only: bool,
    prime_override: str | None,
    stage: str | None,
) -> str:
    """Render the final output string."""
    if json_only:
        return json.dumps(battery, indent=2, ensure_ascii=False)

    if hook_harness is not None:
        if prime_override is not None:
            content = prime_override
        else:
            content = _human_render(
                battery, budget=budget, max_lines=max_lines, memories_only=memories_only, stage=stage
            )
        return json.dumps(_hook_envelope(content, hook_harness), indent=2, ensure_ascii=False)

    if prime_override is not None:
        return prime_override

    return _human_render(
        battery, budget=budget, max_lines=max_lines, memories_only=memories_only, stage=stage
    )


# ---------------------------------------------------------------------------
# Typer command
# ---------------------------------------------------------------------------


@app.callback()
def context_cmd(
    target: str | None = typer.Argument(
        None,
        help="Optional ticket number, task id, or plan path to pin active_plan.",
    ),
    json_only: bool = typer.Option(
        False,
        "--json",
        help="Emit the JSON battery only.",
    ),
    budget_arg: str | None = typer.Option(
        None,
        "--budget",
        help="Rendering budget: auto, cli, or mcp.",
    ),
    max_lines: int | None = typer.Option(
        None,
        "--max-lines",
        help="Cap the number of rendered lines (human/hook modes).",
    ),
    memories_only: bool = typer.Option(
        False,
        "--memories-only",
        help="Emit only the stage line and compact learnings.",
    ),
    hook_harness: str | None = typer.Option(
        None,
        "--hook-json",
        help="Wrap output in a SessionStart envelope for the named harness.",
    ),
) -> None:
    """Emit session workflow context as JSON plus a stage banner."""
    if json_only and hook_harness is not None:
        typer.echo(
            "⛔ --json and --hook-json are mutually exclusive.", err=True
        )
        raise typer.Exit(1)

    if budget_arg is not None and budget_arg not in BUDGET_CHOICES:
        typer.echo(
            f"⛔ Invalid budget '{budget_arg}'. Choose from {', '.join(BUDGET_CHOICES)}.",
            err=True,
        )
        raise typer.Exit(1)

    if hook_harness is not None and hook_harness not in HOOK_CHOICES:
        typer.echo(
            f"⛔ Invalid harness '{hook_harness}'. Choose from {', '.join(HOOK_CHOICES)}.",
            err=True,
        )
        raise typer.Exit(1)

    cwd = Path.cwd()
    plans_dir = cwd / "docs" / "plans"

    try:
        pinned_plan, pinned_stage = _resolve_target(target, cwd, plans_dir)
    except ValueError as exc:
        typer.echo(f"⛔ {exc}", err=True)
        raise typer.Exit(1) from exc

    battery, _ = build_context(cwd, target=target)

    # Recompute active fields when a target was pinned; build_context already
    # did this, but we need the resolved stage for the banner.
    stage = pinned_stage or battery.get("active_plan_stage") or battery.get("active_prd_stage")

    budget = _resolve_budget(budget_arg, os.environ)

    prime_path = cwd / PRIME_FILE
    prime_override = prime_path.read_text(encoding="utf-8") if prime_path.is_file() else None

    output = _render_output(
        battery,
        json_only=json_only,
        hook_harness=hook_harness,
        budget=budget,
        max_lines=max_lines,
        memories_only=memories_only,
        prime_override=prime_override,
        stage=stage,
    )
    typer.echo(output)


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    try:
        return app(argv, standalone_mode=False)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0


if __name__ == "__main__":
    app()
