"""Corpus-level lint for ``docs/plans/``.

The corpus is the non-recursive set of ``*.md`` files directly under
``docs/plans/``. Settled-ness is recorded in the provenance ledger (ADR-055),
not by plan location, so there is no separate archive directory to exclude.

Plan frontmatter ``status`` left the contract with ADR-055. This linter flags
any plan that still carries a live (non-terminal) ``status`` field so the
field is removed rather than allowed to drift back into authority. Terminal
statuses (``merged``/``abandoned``) are historical breadcrumbs and are allowed
to remain until the legacy corpus is cleaned up separately.

Floor signals are reported separately from errors: they are judgment-shaped
consistency checks, not hard violations. The two mechanically decidable
signals are:

- a ``Files to Modify`` set that substantially overlaps a sibling the plan is
  linearly ordered against;
- a docs-only plan whose sole consumer is a single sibling.
"""

from __future__ import annotations

import re
from pathlib import Path

from aet import plan_parser

# Terminal statuses end the lifecycle; they are not "live" and may remain as
# historical breadcrumbs in the legacy corpus.
_TERMINAL_STATUSES = {"merged", "abandoned"}

# A ``Files to Modify`` overlap is substantial when it covers more than this
# share of the smaller plan's file set. The threshold is chosen to flag plans
# that are mostly a subset of a sibling's work while not flagging independent
# plans that happen to touch one or two shared files.
_FLOOR_OVERLAP_THRESHOLD = 0.5


def _section_body(text: str, heading: str) -> str | None:
    """Return the body under a ``## Heading`` if present."""
    pattern = (
        r"(?m)^##\s+"
        + re.escape(heading)
        + r"\s*\n(.*?)"
        + r"(?=\n## |\n---|\Z)"
    )
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1) if match else None


def _list_items(section: str) -> list[str]:
    """Return list-item text stripped of bullets/numbers/checkboxes."""
    items: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not re.match(r"^[\-\*\d]+\.?\s+", stripped):
            continue
        item = re.sub(r"^[\-\*\d]+\.?\s+", "", stripped)
        item = re.sub(r"^\[\s*[xX ]\s*\]\s*", "", item)
        if item:
            items.append(item)
    return items


def _files_to_modify(path: Path) -> set[str]:
    """Return the file paths listed under ``Files to Modify``.

    Paths are returned as written, stripped of surrounding backticks and the
    ``(new)`` marker. Directory entries (trailing ``/``) and empty sections
    produce an empty set.
    """
    text = path.read_text(errors="ignore")
    section = _section_body(text, "Files to Modify") or ""
    files: set[str] = set()
    for item in _list_items(section):
        item = item.strip()
        if item.endswith("/"):
            continue
        item = re.sub(r"`([^`]+)`", r"\1", item)
        item = re.sub(r"\s*\(new\)\s*$", "", item, flags=re.IGNORECASE)
        item = item.strip("- ")
        if item:
            files.add(item)
    return files


def _is_docs_only(files: set[str]) -> bool:
    """Return True when every file path is under ``docs/`` or is a ``.md`` file."""
    if not files:
        return False
    return all(
        path.startswith("docs/") or path.endswith(".md") for path in files
    )


def _linearly_ordered_pairs(
    data_by_id: dict[str, dict[str, object]],
) -> set[tuple[str, str]]:
    """Return ordered plan-id pairs (a, b) where ``a`` is blocked by ``b``.

    The relation is the transitive closure of ``blocked_by``. A pair is
    included only when both ids are present in the corpus.
    """
    ids = set(data_by_id.keys())

    def transitive(blocked_by: list[str]) -> set[str]:
        seen: set[str] = set()
        stack = [b for b in blocked_by if b in ids]
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            current_blocked = data_by_id.get(current, {}).get("blocked_by", [])
            if isinstance(current_blocked, list):
                stack.extend(b for b in current_blocked if b in ids)
        return seen

    pairs: set[tuple[str, str]] = set()
    for plan_id, data in data_by_id.items():
        blocked_by = data.get("blocked_by", [])
        if not isinstance(blocked_by, list):
            blocked_by = []
        for blocker in transitive(blocked_by):
            pairs.add((plan_id, blocker))
    return pairs


def _substantial_overlap(
    plan_files: set[str], sibling_files: set[str]
) -> tuple[bool, set[str]]:
    """Return (True, overlap) if ``plan_files`` mostly overlaps a sibling's.

    The overlap is measured against the plan's own file set, not the sibling's.
    A plan is a floor candidate when its own ``Files to Modify`` is largely a
    subset of a sibling's. At least two files must overlap to avoid flagging a
    single coincidental shared path.
    """
    if not plan_files or not sibling_files:
        return False, set()
    overlap = plan_files & sibling_files
    if len(overlap) < 2:
        return False, overlap
    return (len(overlap) / len(plan_files)) > _FLOOR_OVERLAP_THRESHOLD, overlap


def _corpus_plan_files(plans_dir: Path) -> list[Path]:
    """Discover all candidate plan files under ``plans_dir``.

    Includes plans directly under ``plans_dir/active/`` and legacy plans
    directly under ``plans_dir/``, while explicitly excluding any plans
    under ``plans_dir/archive/``.
    """
    if not plans_dir.exists() or not plans_dir.is_dir():
        return []
    active_dir = plans_dir / "active"
    active_files = [p for p in active_dir.glob("*.md") if p.is_file()] if active_dir.is_dir() else []
    root_files = [p for p in plans_dir.glob("*.md") if p.is_file()]
    combined = [p for p in set(active_files + root_files) if p.parent.name != "archive"]
    return sorted(combined, key=lambda p: (p.name, str(p)))


def lint_floor(plans_dir: Path) -> list[tuple[Path, str]]:
    """Return floor-signal warnings for the plan corpus under ``plans_dir``.

    Warnings are advisory: they describe plans that may be better merged with
    a sibling, but coherence is judgment-shaped and the linter does not block.
    """
    warnings: list[tuple[Path, str]] = []
    if not plans_dir.exists():
        return warnings

    plan_files = sorted(
        p for p in _corpus_plan_files(plans_dir) if not plan_parser.is_settled_plan(p)
    )
    if not plan_files:
        return warnings

    data_by_id: dict[str, dict[str, object]] = {}
    files_by_id: dict[str, set[str]] = {}
    path_by_id: dict[str, Path] = {}

    for plan in plan_files:
        data = plan_parser.parse_frontmatter(plan)
        plan_id = data.get("id")
        if not isinstance(plan_id, str):
            continue
        data_by_id[plan_id] = data
        files_by_id[plan_id] = _files_to_modify(plan)
        path_by_id[plan_id] = plan

    ordered_pairs = _linearly_ordered_pairs(data_by_id)

    # Signal 3: substantial Files to Modify overlap with a linearly-ordered
    # sibling.
    for plan_id, blocker_id in ordered_pairs:
        overlap_files, overlap = _substantial_overlap(
            files_by_id.get(plan_id, set()),
            files_by_id.get(blocker_id, set()),
        )
        if overlap_files:
            warnings.append(
                (
                    path_by_id[plan_id],
                    f"floor: {len(overlap)} of {len(files_by_id[plan_id])} "
                    f"files overlap {blocker_id} "
                    f"({', '.join(sorted(overlap))})",
                )
            )

    # Signal 4: docs-only plan whose sole consumer is one sibling.
    consumers_by_id: dict[str, list[str]] = {plan_id: [] for plan_id in data_by_id}
    for plan_id, data in data_by_id.items():
        blocked_by = data.get("blocked_by", [])
        if not isinstance(blocked_by, list):
            continue
        for blocker in blocked_by:
            if blocker in consumers_by_id:
                consumers_by_id[blocker].append(plan_id)

    for plan_id, files in files_by_id.items():
        if not _is_docs_only(files):
            continue
        consumers = consumers_by_id.get(plan_id, [])
        if len(consumers) == 1:
            warnings.append(
                (
                    path_by_id[plan_id],
                    f"floor: docs-only plan is consumed only by {consumers[0]}",
                )
            )

    return warnings


def lint_corpus(plans_dir: Path) -> list[tuple[Path, str]]:
    """Return violations for the live plan corpus under ``plans_dir``.

    Settled plans (terminal ``status`` frontmatter or terminal footer stage)
    and plans under ``docs/plans/archive/`` are ignored so the linter does not
    degrade as finished work accumulates.

    Each violation is a ``(plan_path, message)`` tuple naming the offending
    file and why it failed. An empty list means no live plan in the corpus
    carries a live ``status`` frontmatter field.
    """
    violations: list[tuple[Path, str]] = []
    if not plans_dir.exists():
        return violations

    for plan in _corpus_plan_files(plans_dir):
        if plan_parser.is_settled_plan(plan):
            continue
        data = plan_parser.parse_frontmatter(plan)
        status = data.get("status")
        if status is not None and status not in _TERMINAL_STATUSES:
            violations.append((plan, f"live status field is present: {status}"))

    return violations
