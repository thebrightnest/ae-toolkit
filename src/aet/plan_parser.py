"""Shared plan-file parsing utilities for aet-work commands."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from aet.queue import append_history  # noqa: E402

# Characters that make a plain YAML scalar invalid or ambiguous.  Values
# containing these must be quoted before PyYAML can parse them as strings.
_SCALAR_SPECIAL_RE = re.compile(r"[:>#`|%@!&*{}[\],]")


def _frontmatter_body(path: Path) -> str | None:
    """Return the raw text between the leading ``---`` fences, or None.

    Returns None when the file has no frontmatter or the fence is unclosed.
    """
    content = path.read_text(errors="ignore")
    if not content.startswith("---"):
        return None
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None
    return parts[1]


def _yaml_scalar_needs_quoting(value: str) -> bool:
    """Return True if ``value`` must be quoted to be a YAML string scalar."""
    value = value.strip()
    if not value or value == "[]":
        return False
    # Already quoted.
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return False
    # Inline flow collections are parsed by PyYAML directly.
    if (value.startswith("[") and value.endswith("]")) or (
        value.startswith("{") and value.endswith("}")
    ):
        return False
    # Plain scalars cannot contain or start with these characters.
    if _SCALAR_SPECIAL_RE.search(value):
        return True
    if value[0] in "|>%":
        return True
    return False


def _normalize_frontmatter_scalar(value: str) -> str:
    """Return a YAML-safe representation of a scalar frontmatter value.

    Quotes the value when PyYAML would otherwise misinterpret it as structure.
    Unquoted values keep their original spacing so ``key: value`` remains valid.
    """
    stripped = value.strip()
    if not stripped or stripped == "[]":
        return value
    if _yaml_scalar_needs_quoting(stripped):
        escaped = stripped.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _normalize_frontmatter_body(body: str) -> str:
    """Make a hand-rolled frontmatter body valid YAML for PyYAML.

    Quotes scalar values that contain characters which would otherwise be
    misinterpreted as YAML structure.  This preserves the existing plan
    corpus (which uses Markdown backticks and unquoted colons in prose
    fields) without re-implementing a YAML parser.
    """
    lines: list[str] = []
    for raw_line in body.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            lines.append(raw_line)
            continue
        if stripped.startswith("- "):
            indent = raw_line[: len(raw_line) - len(raw_line.lstrip())]
            item = stripped[2:]
            lines.append(f"{indent}- {_normalize_frontmatter_scalar(item)}")
            continue
        if ":" not in stripped:
            lines.append(raw_line)
            continue
        key_part, sep, value_part = raw_line.partition(":")
        normalized = _normalize_frontmatter_scalar(value_part)
        if normalized != value_part:
            # Ensure a single space separates the colon from the quoted value.
            lines.append(f"{key_part}{sep} {normalized.lstrip()}")
        else:
            lines.append(f"{key_part}{sep}{normalized}")
    return "\n".join(lines)


def parse_frontmatter(path: Path) -> dict[str, Any]:
    """Parse the YAML frontmatter of a plan file using PyYAML.

    Returns an empty dict when the file has no frontmatter, the fence is
    unclosed, the YAML is malformed, or the top-level value is not a mapping.

    The ``blocked_by`` key is defaulted to an empty list when absent so the
    rest of the intake contract can rely on its presence.
    """
    body = _frontmatter_body(path)
    if body is None:
        return {}

    normalized = _normalize_frontmatter_body(body)
    try:
        data = yaml.safe_load(normalized)
    except yaml.YAMLError:
        return {}

    if not isinstance(data, dict):
        return {}

    # The hand-rolled parser treated ``blocked_by:`` (empty scalar) as an
    # empty list.  PyYAML returns None for an empty scalar, so normalize it
    # back to the contract default (covers missing key too).
    if data.get("blocked_by") is None:
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


def stage_from_plan(path: Path) -> str | None:
    """Extract the *Stage:* footer value from a plan file.

    Body text may mention other stages (e.g. "set fods-06 footer to
    _Stage: superseded_"), so we take the last match rather than the first.
    A missing file fails open and returns ``None``.
    """
    if not path.exists():
        return None
    content = path.read_text(errors="ignore")
    matches = re.findall(r"[*_]Stage:\s*([\w-]+)[*_]", content)
    if matches:
        return matches[-1]
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


def has_explicit_frontmatter_blocked_by(path: Path) -> bool:
    """Return True when the frontmatter explicitly declares a blocked_by key."""
    body = _frontmatter_body(path)
    if body is None:
        return False
    return bool(re.search(r"^blocked_by\s*:", body, re.M))


def validate_size(path: Path) -> tuple[bool, str | None, bool]:
    """Check whether a plan carries the ATOMIC OVERSIZED assertion.

    Returns (ok, reason, has_oversized_warning).

    Plan size is measured after implementation, not gated at intake, so this
    function no longer rejects on task-list length.  The warning signal is
    preserved for downstream skills (e.g. ``aet-implement``) that refuse to
    start on plans marked atomic-oversized without explicit approval.
    """
    has_warning = "\u26a0\ufe0f ATOMIC OVERSIZED" in path.read_text(errors="ignore")
    return True, None, has_warning


def most_recent_prd(prds_dir: Path) -> Path | None:
    """Return the most recently modified PRD file, or None."""
    if not prds_dir.exists():
        return None
    prds = sorted(prds_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return prds[0] if prds else None


def most_recent_plan(plans_dir: Path) -> Path | None:
    """Return the most recently modified plan file, or None."""
    if not plans_dir.exists():
        return None
    plans = sorted(plans_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return plans[0] if plans else None


def new_task_from_plan(path: Path, settled_ids: set[str] | None = None) -> dict[str, Any]:
    """Create a fresh queue task dict from a plan file using the frontmatter contract.

    ``settled_ids`` carries task ids already terminal in the settled history
    log. A blocker that merged before this task was added already fired its
    decrement event and will not fire again, so it must not count toward
    ``pending_blockers`` — otherwise the task deadlocks on arrival.
    """
    data = parse_frontmatter(path)
    blocked_by = data.get("blocked_by", [])
    if not isinstance(blocked_by, list):
        blocked_by = []
    blocked_by = [b for b in blocked_by if isinstance(b, str)]

    settled = settled_ids or set()
    pending = [b for b in blocked_by if b not in settled]

    state = "ready" if not pending else "blocked"
    work_class = data.get("work_class")
    if isinstance(work_class, str) and work_class.lower() in {"trivial", "normal", "critical"}:
        work_class = work_class.lower()
    else:
        work_class = "unclassified"

    task: dict[str, Any] = {
        "id": data.get("id", path.stem),
        "title": title_from_plan(path),
        "plan_file": str(path),
        "blocked_by": blocked_by,
        "blocks": [],
        "state": state,
        "pending_blockers": len(pending),
        "merge_commit": None,
        "completed_at": None,
        "merged_at": None,
        "worktree": None,
        "branch": None,
        "work_class": work_class,
    }
    append_history(task, None, state, "sync")
    return task


# Frontmatter keys that route gated pipeline stages at plan time. Each key is
# optional (a missing key defaults to ``required`` at run time); when present
# it must be ``required`` or ``skipped``, and ``skipped`` must carry a
# non-empty ``<key>_reason`` recording the plan-time judgment.
ROUTING_GATE_KEYS = ("security_review", "docs_sync")

# Map from verdict kind to the plan-frontmatter routing key that controls it.
VERDICT_GATE_KEYS: dict[str, str] = {
    "cso": "security_review",
    "sync-docs": "docs_sync",
}


def required_verdict_kinds(plan_data: dict[str, Any]) -> list[str]:
    """Return the required verdict kinds for a task from its parsed frontmatter.

    ``qa`` and ``review`` are always required. A gated kind is required unless
    its routing key is explicitly set to ``skipped``. A missing routing key
    defaults to required — the standing fail-safe.
    """
    required = ["qa", "review"]
    for kind, key in VERDICT_GATE_KEYS.items():
        if plan_data.get(key) != "skipped":
            required.append(kind)
    return required


def _routing_key_error(data: dict[str, Any]) -> str | None:
    """Validate the gate-routing keys of one plan's frontmatter.

    Returns an error reason, or None when the keys satisfy the contract.
    """
    for key in ROUTING_GATE_KEYS:
        value = data.get(key)
        if value is None:
            continue
        if value not in ("required", "skipped"):
            return f"invalid {key}: {value} (must be required or skipped)"
        if value == "skipped":
            reason = data.get(f"{key}_reason")
            if not isinstance(reason, str) or not reason.strip():
                return f"{key}_reason is required when {key} is skipped"
    return None


def intake_validation_errors(
    plan_files: list[Path],
    limit_to: set[Path] | None = None,
    extra_known_ids: set[str] | None = None,
) -> list[tuple[Path, str]]:
    """Validate plan files for intake and return a list of fatal errors.

    Checks the frontmatter contract (id, size, blocked_by, work_class,
    gate-routing keys), cross-plan blocker references, multi-unit plan markers,
    atomic-complexity limits, and legacy dependency sections that would silently
    drop blockers.

    By default every file is validated. When ``limit_to`` is provided, only files
    in that set produce validation errors, but every file is still parsed so that
    cross-plan blocker references and duplicate-id detection remain accurate.

    ``extra_known_ids`` allows callers (e.g. ``aet-work add``) to include
    already-settled task ids that are valid blocker references even though the
    plan file may no longer be present.
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
    known_ids = set(ids) | (extra_known_ids or set())

    errors: list[tuple[Path, str]] = []
    for pf in plan_files:
        data = parsed[pf]
        task_id = data.get("id")

        if limit_to is not None and pf not in limit_to:
            continue

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

        work_class = data.get("work_class")
        if work_class is not None and (
            not isinstance(work_class, str)
            or work_class.lower() not in {"trivial", "normal", "critical"}
        ):
            errors.append(
                (pf, f"work_class must be one of trivial|normal|critical (got '{work_class}')")
            )
            continue

        routing_error = _routing_key_error(data)
        if routing_error:
            errors.append((pf, routing_error))
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

        if has_legacy_dependency_section(pf) and not has_explicit_frontmatter_blocked_by(pf):
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


def resolve_plan_arg(plan: str, plans_dir: Path = Path("docs/plans")) -> str:
    """Resolve a plan argument that may be a path or a bare task id.

    A value ending in ``.md`` is treated as a plan path and returned as-is.
    Anything else is treated as a task id and resolved to
    ``<plans_dir>/<id>.md``. Raises ``ValueError`` when the id does not
    resolve, so the error names both interpretations.
    """
    if plan.lower().endswith(".md"):
        return plan
    candidate = plans_dir / f"{plan}.md"
    if candidate.is_file():
        return str(candidate)
    raise ValueError(
        f"Plan not found: '{plan}' is not a .md path and "
        f"{candidate} does not exist. Pass the full plan path."
    )
