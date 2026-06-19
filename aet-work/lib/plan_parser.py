"""Shared plan-file parsing utilities for aet-work commands."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from queue import append_history  # noqa: E402


def _unquote_scalar(value: str) -> str:
    """Strip matching surrounding quotes from a YAML scalar value."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def parse_frontmatter(path: Path) -> dict[str, Any]:
    """Parse the YAML frontmatter contract for a plan file.

    Supported subset: top-level scalar keys and block-style string lists.
    Returns an empty dict when no frontmatter is present.
    """
    content = path.read_text(errors="ignore")
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}

    data: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in parts[1].splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("- "):
            if current_key is None:
                continue
            item = _unquote_scalar(line[2:])
            if not isinstance(data.get(current_key), list):
                data[current_key] = []
            data[current_key].append(item)
            continue

        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        current_key = key
        if value:
            data[key] = _unquote_scalar(value)
        else:
            data[key] = []

    if "blocked_by" not in data:
        data["blocked_by"] = []

    return data


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


def has_legacy_dependency_section(path: Path) -> bool:
    """Return True if the plan body contains a legacy dependency heading."""
    content = path.read_text(errors="ignore")
    return bool(re.search(r"(?mi)^##\s+(Blocked by|Dependencies)\b", content))


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
    has_warning = "\u26a0\ufe0f ATOMIC OVERSIZED" in path.read_text(errors="ignore")
    if oversized and not has_warning:
        return False, f"files={files}, task_list_lines={lines}", has_warning
    return True, None, has_warning


def most_recent_prd(prds_dir: Path) -> Path | None:
    """Return the most recently modified PRD file, or None."""
    if not prds_dir.exists():
        return None
    prds = sorted(prds_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return prds[0] if prds else None


def new_task_from_plan(
    path: Path,
    status: str = "planned",
) -> dict[str, Any]:
    """Create a fresh queue task dict from a plan file using the frontmatter contract."""
    data = parse_frontmatter(path)
    blocked_by = data.get("blocked_by", [])
    if not isinstance(blocked_by, list):
        blocked_by = []
    blocked_by = [b for b in blocked_by if isinstance(b, str)]

    state = "ready" if not blocked_by else "blocked"
    task: dict[str, Any] = {
        "id": data.get("id", path.stem),
        "title": title_from_plan(path),
        "plan_file": str(path),
        "blocked_by": blocked_by,
        "blocks": [],
        "status": status,
        "state": state,
        "pending_blockers": len(blocked_by),
        "merge_commit": None,
        "completed_at": None,
        "merged_at": None,
        "worktree": None,
        "branch": None,
    }
    append_history(task, None, "planned", "sync")
    return task


def intake_validation_errors(
    plan_files: list[Path],
) -> list[tuple[Path, str]]:
    """Validate every plan file for intake and return a list of fatal errors.

    Checks the frontmatter contract (id, size, blocked_by), cross-plan blocker
    references, multi-unit plan markers, atomic-complexity limits, and legacy
    dependency sections that would silently drop blockers.
    """
    parsed: dict[Path, dict[str, Any]] = {}
    ids: list[str] = []
    for pf in plan_files:
        data = parse_frontmatter(pf)
        parsed[pf] = data
        task_id = data.get("id")
        if task_id:
            ids.append(task_id)

    duplicate_ids = {task_id for task_id in ids if ids.count(task_id) > 1}
    known_ids = set(ids)

    errors: list[tuple[Path, str]] = []
    for pf in plan_files:
        data = parsed[pf]
        task_id = data.get("id")

        if not task_id:
            errors.append((pf, "missing id"))
            continue
        if task_id in duplicate_ids:
            errors.append((pf, f"duplicate id: {task_id}"))
            continue
        if task_id != pf.stem:
            errors.append((pf, f"id mismatch: {task_id} != {pf.stem}"))
            continue

        size = data.get("size")
        if size not in {"S", "M", "L"}:
            errors.append((pf, f"invalid size: {size}"))
            continue

        blocked_by = data.get("blocked_by", [])
        if not isinstance(blocked_by, list) or not all(
            isinstance(b, str) for b in blocked_by
        ):
            errors.append((pf, "blocked_by must be a list of ids"))
            continue

        unknown = [b for b in blocked_by if b not in known_ids]
        if unknown:
            errors.append((pf, f"unknown blockers: {', '.join(unknown)}"))
            continue

        if has_legacy_dependency_section(pf):
            errors.append(
                (pf, "legacy dependency section found; move blocked_by to frontmatter")
            )
            continue

        if references_other_plans(pf):
            errors.append((pf, "references other plan files"))
            continue

        if has_multiple_phase_sections(pf):
            errors.append((pf, "contains multiple Phase sections"))
            continue

        ok, reason, has_warning = validate_size(pf)
        if not ok and not has_warning:
            errors.append((pf, f"exceeds complexity limit ({reason})"))
            continue

    return errors
