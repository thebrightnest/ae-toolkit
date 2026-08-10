"""Corpus-level lint for ``docs/plans/``.

Plan frontmatter ``status`` left the contract with ADR-055. This linter flags
any plan that still carries a live (non-terminal) ``status`` field so the
field is removed rather than allowed to drift back into authority. Terminal
statuses (``merged``/``abandoned``) are historical breadcrumbs and are allowed
to remain until the legacy corpus is cleaned up separately.
"""

from __future__ import annotations

from pathlib import Path

from aet import plan_parser

# Terminal statuses end the lifecycle; they are not "live" and may remain as
# historical breadcrumbs in the legacy corpus.
_TERMINAL_STATUSES = {"merged", "abandoned"}


def lint_corpus(plans_dir: Path) -> list[tuple[Path, str]]:
    """Return violations for the plan corpus under ``plans_dir``.

    Each violation is a ``(plan_path, message)`` tuple naming the offending
    file and why it failed. An empty list means no plan in the corpus carries
    a live ``status`` frontmatter field.
    """
    violations: list[tuple[Path, str]] = []
    if not plans_dir.exists():
        return violations

    for plan in sorted(plans_dir.glob("*.md")):
        data = plan_parser.parse_frontmatter(plan)
        status = data.get("status")
        if status is not None and status not in _TERMINAL_STATUSES:
            violations.append((plan, f"live status field is present: {status}"))

    return violations
