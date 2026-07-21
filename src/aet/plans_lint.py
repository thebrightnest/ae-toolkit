"""Corpus-level lint for ``docs/plans/``.

This is the doc-coupled check relocated from pytest (R-5). It classifies every
plan in the corpus as settled or live based on committed frontmatter and reports
any plan whose classification disagrees with its ``status`` value.
"""

from __future__ import annotations

from pathlib import Path

from aet import plan_parser, plan_validate


def lint_corpus(plans_dir: Path) -> list[tuple[Path, str]]:
    """Return violations for the plan corpus under ``plans_dir``.

    Each violation is a ``(plan_path, message)`` tuple naming the offending
    file and why it failed classification. An empty list means every plan in
    the corpus is correctly classified.
    """
    violations: list[tuple[Path, str]] = []
    if not plans_dir.exists():
        return violations

    for plan in sorted(plans_dir.glob("*.md")):
        data = plan_parser.parse_frontmatter(plan)
        status = data.get("status")

        if status is not None and (
            not isinstance(status, str)
            or status not in plan_validate.PLAN_LIFECYCLE_STATUSES
        ):
            violations.append((plan, f"invalid status: {status}"))
            continue

        is_settled = plan_validate.is_settled_plan(plan)
        expected_settled = status is None or status in plan_validate.TERMINAL_PLAN_STATUSES

        if is_settled != expected_settled:
            if is_settled:
                violations.append(
                    (plan, f"status={status} classified as settled but is live")
                )
            else:
                violations.append(
                    (plan, f"status={status} classified as live but is settled")
                )

    return violations
