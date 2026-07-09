#!/usr/bin/env python3
"""One-time migration for docs/plans/*.md to the validated frontmatter contract.

Adds ``id``, ``size``, and ``blocked_by`` frontmatter to legacy plans, infers
``blocked_by`` only from unambiguous inter-plan references, and can rebuild the
work queue and backfill settled history.

Dry-run by default; use ``--apply`` to write plan-file changes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Load shared plan parsing helpers from aet-work/lib.
_SCRIPT_DIR = Path(__file__).resolve().parent
_LIB_DIR = _SCRIPT_DIR.parent / "aet-work" / "lib"
sys.path.insert(0, str(_LIB_DIR))

from plan_parser import build_ticket_map, title_from_plan  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KNOWN_SIZES = {"S", "M", "L"}
TERMINAL_STATES = {"merged", "abandoned"}
TERMINAL_STATUSES = {"merged", "done", "abandoned"}

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
SECTION_RE = re.compile(
    r"(?m)^##\s+(Blocked by|Dependencies|Depends on)\s*\n(.*?)" r"(?=\n## |\n---|\Z)",
    re.S,
)
LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
SIZE_RE = re.compile(r"(?i)(?:^|\s)[\[(]?([SML])[\])]?(?=\s|$)")


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------


def parse_frontmatter(path: Path) -> dict[str, Any] | None:
    """Return the parsed YAML frontmatter of a plan, or None if absent.

    Only the small subset used by the migration contract is parsed:
    ``id`` (string), ``size`` (string), and ``blocked_by`` (list of strings).
    """
    content = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(content)
    if not match:
        return None

    fm: dict[str, Any] = {}
    current_key: str | None = None
    list_mode = False

    for raw in match.group(1).splitlines():
        line = raw.rstrip()
        if not line:
            continue

        stripped = line.lstrip()
        if stripped.startswith("-"):
            if current_key is not None and list_mode:
                value = stripped[1:].strip()
                # strip quotes
                if (value.startswith('"') and value.endswith('"')) or (
                    value.startswith("'") and value.endswith("'")
                ):
                    value = value[1:-1]
                fm[current_key].append(value)
            continue

        list_mode = False
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()

        # inline empty list
        if value == "[]":
            fm[key] = []
            continue

        # explicit quoted scalar
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            fm[key] = value[1:-1]
            continue

        if value == "":
            current_key = key
            list_mode = True
            fm[key] = []
        else:
            fm[key] = value

    return fm


def has_frontmatter_contract(path: Path) -> bool:
    """True when a plan already carries the full frontmatter contract."""
    fm = parse_frontmatter(path)
    if not fm:
        return False
    return (
        "id" in fm
        and "size" in fm
        and "blocked_by" in fm
        and isinstance(fm.get("blocked_by"), list)
    )


def render_frontmatter(task_id: str, size: str, blocked_by: list[str]) -> str:
    """Render the frontmatter contract as markdown YAML."""
    lines = ["---", f"id: {task_id}", "blocked_by:"]
    if blocked_by:
        for blocker in blocked_by:
            lines.append(f"  - {blocker}")
    else:
        lines.append("  []")
    lines.extend([f"size: {size}", "---", ""])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Inference helpers
# ---------------------------------------------------------------------------


def extract_size(content: str) -> str:
    """Infer size from an explicit S/M/L label, defaulting to M."""
    match = SIZE_RE.search(content[:2000])
    if match:
        return match.group(1).upper()
    return "M"


def normalize_reference(text: str) -> str | None:
    """Strip decorative characters and return a reference string."""
    text = text.strip().strip("\"'").strip()
    if not text:
        return None
    if text.endswith(".md"):
        return Path(text).stem
    return text


def resolve_line_references(
    line: str, self_id: str, all_ids: set[str], ticket_map: dict[str, str]
) -> tuple[list[str], list[str]]:
    """Resolve concrete references in one dependency-section line.

    Returns ``(resolved_ids, flags)``. ``flags`` are human-readable markers for
    unresolved or ambiguous references.
    """
    resolved: set[str] = set()
    flags: list[str] = []

    # Markdown links to plan files.
    for _label, target in LINK_RE.findall(line):
        stem = normalize_reference(target)
        if stem and stem in all_ids:
            resolved.add(stem)
        elif stem:
            flags.append(f"link target `{target}` is not a known plan")

    # Plain filename references like ``docs/plans/other.md`` or ``other.md``.
    for token in re.findall(r"\b[\w/\-]+\.md\b", line):
        stem = Path(token).stem
        if stem in all_ids:
            resolved.add(stem)
        else:
            flags.append(f"file reference `{token}` is not a known plan")

    # ``Ticket N`` references mapped through plan titles.
    ticket_match = re.search(r"(?i)ticket\s+(\d+)", line)
    if ticket_match:
        key = ticket_match.group(1).lstrip("0") or "0"
        if key in ticket_map:
            resolved.add(ticket_map[key])
        else:
            flags.append(f"ticket `{key}` has no plan mapping")

    # Whole-word id matches as a fallback only when no concrete reference was
    # found. Multiple whole-word matches are ambiguous and flagged.
    if not resolved and not flags:
        whole_ids = {
            plan_id
            for plan_id in all_ids
            if plan_id != self_id
            and re.search(r"\b" + re.escape(plan_id) + r"\b", line)
        }
        if len(whole_ids) == 1:
            resolved = whole_ids
        elif len(whole_ids) > 1:
            flags.append(f"ambiguous whole-word ids: {sorted(whole_ids)}")

    resolved.discard(self_id)
    return sorted(resolved), flags


def infer_blocked_by(
    path: Path, all_ids: set[str], ticket_map: dict[str, str]
) -> dict[str, list[str]]:
    """Infer blocked_by from unambiguous inter-plan references.

    Reads ``## Blocked by``, ``## Dependencies``, and ``## Depends on`` sections
    only. Intra-plan task text (``## Tasks`` / ``## Task List``) is never
    promoted to an inter-plan edge.

    Returns a dict with ``recovered``, ``unresolved``, and ``flagged`` lists.
    """
    content = path.read_text(encoding="utf-8")
    self_id = path.stem

    recovered: list[str] = []
    unresolved: list[str] = []
    flagged: list[str] = []

    for _heading, section in SECTION_RE.findall(content):
        for raw_line in section.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            # Strip list-item markers so we can inspect the semantic content.
            line = re.sub(r"^[\s\-\*\d\.\[\]xX]+", "", line).strip()
            if not line:
                continue

            line_resolved, line_flags = resolve_line_references(
                line, self_id, all_ids, ticket_map
            )

            if line_resolved:
                recovered.extend(line_resolved)
            elif line_flags:
                flagged.extend(line_flags)
            else:
                unresolved.append(raw_line.strip())

    # Deduplicate while preserving order.
    return {
        "recovered": list(dict.fromkeys(recovered)),
        "unresolved": unresolved,
        "flagged": flagged,
    }


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


def migrate_plan(
    path: Path,
    all_ids: set[str],
    ticket_map: dict[str, str],
    apply: bool = False,
) -> dict[str, Any]:
    """Infer and optionally write frontmatter for a single plan.

    Returns a record describing what was inferred or skipped.
    """
    if has_frontmatter_contract(path):
        return {
            "path": str(path),
            "id": path.stem,
            "action": "skipped",
            "reason": "frontmatter contract already present",
        }

    content = path.read_text(encoding="utf-8")
    task_id = path.stem
    size = extract_size(content)
    inference = infer_blocked_by(path, all_ids, ticket_map)

    new_frontmatter = render_frontmatter(
        task_id, size, inference["recovered"]
    )

    if apply:
        # Remove any partial/trailing frontmatter block and prepend the new one.
        body = FRONTMATTER_RE.sub("", content, count=1).lstrip("\n")
        if not body.endswith("\n"):
            body += "\n"
        path.write_text(new_frontmatter + body, encoding="utf-8")

    return {
        "path": str(path),
        "id": task_id,
        "size": size,
        "action": "added" if apply else "dry-run",
        "recovered": inference["recovered"],
        "unresolved": inference["unresolved"],
        "flagged": inference["flagged"],
    }


def migrate_corpus(
    plans_dir: Path,
    apply: bool = False,
) -> list[dict[str, Any]]:
    """Migrate every plan in ``plans_dir`` and return inference records."""
    plan_files = sorted(plans_dir.glob("*.md"))
    all_ids = {pf.stem for pf in plan_files}
    ticket_map = build_ticket_map(plan_files)

    records: list[dict[str, Any]] = []
    for pf in plan_files:
        records.append(migrate_plan(pf, all_ids, ticket_map, apply=apply))
    return records


# ---------------------------------------------------------------------------
# Queue rebuild + backfill (driver mode)
# ---------------------------------------------------------------------------


def validate_frontmatter(
    path: Path, all_ids: set[str]
) -> tuple[bool, str | None]:
    """Fail-closed validation of the frontmatter contract.

    Returns ``(ok, reason)``. Rejects missing/mismatched ``id``, unknown
    blockers, and invalid ``size``.
    """
    fm = parse_frontmatter(path)
    if not fm:
        return False, "missing frontmatter"

    task_id = fm.get("id")
    if not task_id:
        return False, "missing id"
    if task_id != path.stem:
        return False, f"id mismatch: frontmatter says {task_id}, filename is {path.stem}"

    size = fm.get("size")
    if size not in KNOWN_SIZES:
        return False, f"invalid size: {size}"

    blocked_by = fm.get("blocked_by")
    if not isinstance(blocked_by, list):
        return False, "blocked_by must be a list"

    for blocker in blocked_by:
        if blocker not in all_ids:
            return False, f"unknown blocker: {blocker}"

    return True, None


def build_task_from_frontmatter(path: Path) -> dict[str, Any]:
    """Create a queue task from a plan that has valid frontmatter."""
    fm = parse_frontmatter(path)
    assert fm is not None
    blocked_by = list(fm.get("blocked_by", []))
    state = "ready" if not blocked_by else "blocked"
    status = "unblocked" if not blocked_by else "blocked"

    return {
        "id": fm["id"],
        "title": title_from_plan(path),
        "plan_file": str(path),
        "blocked_by": blocked_by,
        "blocks": [],
        "state": state,
        "status": status,
        "pending_blockers": len(blocked_by),
        "history": [
            {
                "from": None,
                "to": "planned",
                "at": datetime.now(timezone.utc).isoformat(),
                "by": "migration",
            }
        ],
        "merge_commit": None,
        "merge_strategy": None,
        "completed_at": None,
        "merged_at": None,
        "worktree": None,
        "branch": None,
    }


def build_blocks(queue: list[dict]) -> None:
    """Recompute ``blocks`` as the inverse of ``blocked_by``."""
    task_by_id = {t["id"]: t for t in queue if t.get("id")}
    for task in queue:
        task["blocks"] = []
    for task in queue:
        for blocker in task.get("blocked_by", []):
            if blocker in task_by_id:
                task_by_id[blocker].setdefault("blocks", []).append(task["id"])


def read_json_list(path: Path) -> list[dict]:
    """Read a JSON file that may be a plain list or a wrapped dict."""
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return data.get("tasks", [])
    return data


def write_queue(queue_file: Path, queue: list[dict]) -> None:
    """Write the live queue as a wrapped JSON object."""
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "queue_updated_at": datetime.now(timezone.utc).isoformat(),
        "tasks": queue,
    }
    with open(queue_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def append_history_record(history_file: Path, task: dict) -> None:
    """Append a terminal task record to the append-only JSONL history."""
    history_file.parent.mkdir(parents=True, exist_ok=True)
    sealed = dict(task)
    sealed["sealed_at"] = datetime.now(timezone.utc).isoformat()
    with open(history_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(sealed, separators=(",", ":")) + "\n")


def rebuild_queue(
    plans_dir: Path,
    queue_file: Path,
    history_file: Path,
    existing_queue_file: Path | None = None,
    dry_run: bool = True,
) -> tuple[bool, dict[str, Any]]:
    """Rebuild the queue from frontmatter and backfill settled history.

    Returns ``(ok, report)``. When ``dry_run`` is False, writes ``queue_file``,
    ``history_file``, and appends settled records.
    """
    plan_files = sorted(plans_dir.glob("*.md"))
    all_ids = {pf.stem for pf in plan_files}

    validation_errors: list[str] = []
    new_tasks: list[dict] = []

    for pf in plan_files:
        ok, reason = validate_frontmatter(pf, all_ids)
        if not ok:
            validation_errors.append(f"{pf.name}: {reason}")
            continue
        new_tasks.append(build_task_from_frontmatter(pf))

    if validation_errors:
        return False, {"errors": validation_errors}

    # Backfill terminal tasks from the existing live queue into history.
    existing_tasks = read_json_list(queue_file if existing_queue_file is None else existing_queue_file)
    terminal_to_seal: list[dict] = []
    live_carryover: list[dict] = []

    for task in existing_tasks:
        state = task.get("state")
        status = task.get("status", "")
        terminal = (
            state in TERMINAL_STATES
            or status in TERMINAL_STATUSES
            or status == "merge_verified"
        )
        if terminal:
            terminal_to_seal.append(task)
        else:
            live_carryover.append(task)

    sealed_ids = {t.get("id") for t in terminal_to_seal if t.get("id")}
    # Do not re-create live tasks for plan files whose existing record is already
    # terminal; they are sealed to history instead.
    new_tasks = [t for t in new_tasks if t.get("id") not in sealed_ids]

    # Preserve useful metadata from existing non-terminal tasks that match a
    # migrated plan file.
    new_by_file = {t["plan_file"]: t for t in new_tasks}
    carried_by_file: dict[str, dict] = {}
    for task in live_carryover:
        pf = task.get("plan_file")
        if pf and pf in new_by_file:
            carried_by_file[pf] = task

    merged_tasks: list[dict] = []
    for task in new_tasks:
        pf = task["plan_file"]
        if pf in carried_by_file:
            carried = carried_by_file[pf]
            for key in (
                "branch",
                "worktree",
                "merge_commit",
                "merge_strategy",
                "completed_at",
                "merged_at",
                "failed_stage",
            ):
                if carried.get(key) is not None:
                    task[key] = carried[key]
            # If the carried task already has a recorded state, trust it.
            if carried.get("state") in {
                "planned",
                "ready",
                "blocked",
                "in_progress",
                "awaiting_merge",
                "failed",
            }:
                task["state"] = carried["state"]
                task["status"] = carried.get("status", task["status"])
        merged_tasks.append(task)

    build_blocks(merged_tasks)

    report = {
        "plans": len(plan_files),
        "live_tasks": len(merged_tasks),
        "sealed_tasks": len(terminal_to_seal),
        "sealed_ids": [t.get("id") for t in terminal_to_seal],
    }

    if not dry_run:
        for task in terminal_to_seal:
            append_history_record(history_file, task)
        write_queue(queue_file, merged_tasks)

    return True, report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def cmd_migrate(args: argparse.Namespace) -> int:
    records = migrate_corpus(Path(args.plans_dir), apply=args.apply)

    recovered = sum(len(r.get("recovered", [])) for r in records)
    unresolved = sum(len(r.get("unresolved", [])) for r in records)
    flagged = sum(len(r.get("flagged", [])) for r in records)
    changed = sum(1 for r in records if r.get("action") in ("added", "dry-run"))

    if args.json:
        print(json.dumps(records, indent=2))
    else:
        for r in records:
            if r.get("action") == "skipped":
                continue
            print(f"{r['path']}: {r['action']}")
            print(f"  id={r['id']} size={r['size']} blocked_by={r.get('recovered', [])}")
            if r.get("unresolved"):
                print(f"  unresolved: {r['unresolved']}")
            if r.get("flagged"):
                print(f"  flagged: {r['flagged']}")

    print(
        f"\nMigration summary: {changed} plans processed, "
        f"{recovered} recovered edges, {unresolved} unresolved lines, "
        f"{flagged} flagged lines."
    )
    if not args.apply:
        print("Dry-run mode: no files were modified. Use --apply to write changes.")
    return 0


def cmd_rebuild(args: argparse.Namespace) -> int:
    ok, report = rebuild_queue(
        Path(args.plans_dir),
        Path(args.queue_file),
        Path(args.history_file),
        existing_queue_file=Path(args.existing_queue_file) if args.existing_queue_file else None,
        dry_run=args.dry_run,
    )
    if not ok:
        for err in report.get("errors", []):
            print(f"❌ {err}", file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2))
    if args.dry_run:
        print("Dry-run mode: queue and history were not written.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Migrate plan files to the frontmatter contract and rebuild the queue."
    )
    parser.add_argument(
        "--plans-dir",
        default="docs/plans",
        help="Directory containing plan markdown files",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit migration records as JSON",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write frontmatter changes (default is dry-run)",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Run the queue-rebuild driver after migrating",
    )
    parser.add_argument(
        "--queue-file",
        default=".agents/work-queue.json",
        help="Path to the live work queue",
    )
    parser.add_argument(
        "--history-file",
        default=".agents/work-history.jsonl",
        help="Path to the append-only settled history",
    )
    parser.add_argument(
        "--existing-queue-file",
        default=None,
        help="Queue to read for backfill (defaults to --queue-file)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show rebuild changes without writing them",
    )

    args = parser.parse_args(argv)

    if args.rebuild:
        return cmd_rebuild(args)
    return cmd_migrate(args)


if __name__ == "__main__":
    sys.exit(main())
