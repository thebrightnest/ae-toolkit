"""Shared plan-file parsing utilities for aet-work commands."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def title_from_plan(path: Path) -> str:
    """Extract a plan's title from YAML frontmatter or the first H1."""
    content = path.read_text(errors="ignore")
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 2:
            match = re.search(r"^title:\s*(.+)$", parts[1], re.M)
            if match:
                return match.group(1).strip()
    match = re.search(r"^#\s+(.+)$", content, re.M)
    if match:
        return match.group(1).strip()
    return path.stem


def stage_from_plan(path: Path) -> str | None:
    """Extract the *Stage:* footer value from a plan file."""
    content = path.read_text(errors="ignore")
    match = re.search(r"(?im)^[_\*]Stage:\s*(.+?)[_\*]$", content)
    if match:
        return match.group(1).strip()
    return None


def blocked_by_from_plan(path: Path, ticket_map: dict[str, str] | None = None) -> list[str]:
    """Parse the ## Blocked by section into a list of blocker task IDs."""
    content = path.read_text(errors="ignore")
    match = re.search(r"(?m)^##\s+Blocked by\s*\n(.*?)(?=\n## |\n---|\Z)", content, re.S)
    if not match:
        return []
    section = match.group(1).strip()
    if not section or re.search(r"(?im)^\s*none\b", section):
        return []

    ids: list[str] = []
    for line in section.splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^[\s\-\*\d\.\[\]xX]+", "", line).strip()
        if not line:
            continue

        # Markdown link to another plan.
        link_match = re.search(r"\[([^\]]*)\]\(([^)]+)\)", line)
        if link_match:
            target = link_match.group(2)
            if target.endswith(".md"):
                ids.append(Path(target).stem)
            continue

        # Plain filename reference.
        if line.endswith(".md"):
            ids.append(Path(line).stem)
            continue

        # Plain task ID.
        if re.match(r"^[a-zA-Z0-9_-]+$", line):
            ids.append(line)
            continue

        # "Ticket N" reference.
        ticket_match = re.search(r"(?i)ticket\s+(\d+)", line)
        if ticket_match and ticket_map is not None:
            key = ticket_match.group(1).lstrip("0") or "0"
            if key in ticket_map:
                ids.append(ticket_map[key])
            continue

    return list(dict.fromkeys(ids))


def references_other_plans(path: Path) -> bool:
    """Return True if the plan links to other plan files."""
    content = path.read_text(errors="ignore")
    for match in re.finditer(r"\[([^\]]*)\]\(([^)]+)\)", content):
        target = match.group(2)
        if target.startswith("docs/plans/") or target.startswith("../plans/"):
            return True
        if "/plans/" in target and target.endswith(".md"):
            return True
    return False


def has_multiple_phase_sections(path: Path) -> bool:
    """Return True if the plan contains more than one Phase heading."""
    content = path.read_text(errors="ignore")
    return len(re.findall(r"(?m)^#{1,3}\s+Phase", content)) > 1


def count_files_to_modify(path: Path) -> int:
    """Count list items under ## Files to Modify or ## Files."""
    content = path.read_text(errors="ignore")
    match = re.search(
        r"(?m)^##\s+(Files to Modify|Files)\s*\n(.*?)(?=\n## |\n---|\Z)",
        content,
        re.S,
    )
    if not match:
        return 0
    return len(
        [l for l in match.group(2).splitlines() if re.match(r"^\s*[\-\*\d]", l.strip())]
    )


def task_list_line_count(path: Path) -> int:
    """Count non-empty lines under ## Task List."""
    content = path.read_text(errors="ignore")
    match = re.search(
        r"(?m)^##\s+Task List\s*\n(.*?)(?=\n## |\n---|\Z)",
        content,
        re.S,
    )
    if not match:
        return 0
    return len([l for l in match.group(1).splitlines() if l.strip()])


def validate_size(path: Path) -> tuple[bool, str | None, bool]:
    """Check that a plan is within atomic-complexity limits.

    Returns (ok, reason, has_oversized_warning).
    """
    files = count_files_to_modify(path)
    lines = task_list_line_count(path)
    oversized = files > 8 or lines > 300
    has_warning = "⚠️ ATOMIC OVERSIZED" in path.read_text(errors="ignore")
    if oversized and not has_warning:
        return False, f"files={files}, task_list_lines={lines}", has_warning
    return True, None, has_warning


def build_ticket_map(plan_files: list[Path]) -> dict[str, str]:
    """Build a ticket-number -> task-id map from plan titles."""
    ticket_map: dict[str, str] = {}
    for pf in plan_files:
        title = title_from_plan(pf)
        for pattern in (r"(?i)ticket\s+(\d+)", r"(?i)#\s*(\d+)"):
            match = re.search(pattern, title)
            if match:
                key = match.group(1).lstrip("0") or "0"
                ticket_map[key] = pf.stem
    return ticket_map


def most_recent_prd(prds_dir: Path) -> Path | None:
    """Return the most recently modified PRD file, or None."""
    if not prds_dir.exists():
        return None
    prds = sorted(prds_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return prds[0] if prds else None


def new_task_from_plan(
    path: Path,
    ticket_map: dict[str, str] | None = None,
    status: str = "planned",
) -> dict[str, Any]:
    """Create a fresh queue task dict from a plan file."""
    task: dict[str, Any] = {
        "id": path.stem,
        "title": title_from_plan(path),
        "plan_file": str(path),
        "blocked_by": blocked_by_from_plan(path, ticket_map),
        "blocks": [],
        "status": status,
        "merge_commit": None,
        "completed_at": None,
        "merged_at": None,
        "worktree": None,
        "branch": None,
    }
    return task
