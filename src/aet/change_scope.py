"""Decide how much of the validate gate the current change set requires.

``make validate`` is this repo's only safety net — there is no CI — so the
default is always the full suite. This module allows exactly one narrowing:
when a change touches nothing but prose, pytest runs the handful of test
modules that read the repo's own Markdown instead of all of ``tests/``.

Fail-safe by construction. An unreadable change set, an unrecognized path, and
an empty diff all resolve to :data:`FULL`.
"""

from __future__ import annotations

import subprocess
import sys

from aet import evidence

FULL = "full"
DOCS = "docs"

ALL_TESTS = ("tests/",)

# Test modules that assert against the repo's real Markdown rather than against
# fixtures, so a prose-only edit can genuinely break them. Kept honest by
# tests/test_change_scope.py, which fails when a module starts reading repo
# Markdown without being listed here.
DOC_COUPLED_TESTS = (
    "tests/ship/test_merge_governance.py",
    "tests/skills/test_aet_qa.py",
    "tests/skills/test_aet_review.py",
    "tests/test_scripts_layout.py",
)

BASE_REF = "origin/main"


def is_code_path(path: str) -> bool:
    """Whether a changed path can alter pytest outcomes (bias: assume yes).

    Stricter than :func:`evidence.default_is_code_path`, which counts every
    ``*.md`` as prose. That is the right call for per-task verdict freshness,
    but wrong for a repo-wide gate: ``tests/`` holds Markdown fixtures whose
    content decides test outcomes.
    """
    p = path.strip()
    if not p:
        return True
    if p.startswith("tests/"):
        return True
    return evidence.default_is_code_path(p)


def _git(*args: str) -> str | None:
    """Run a git command, returning stdout, or ``None`` if it failed at all."""
    try:
        proc = subprocess.run(
            ["git", *args], capture_output=True, text=True, check=False
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _parse_status(payload: str) -> set[str]:
    """Paths from ``git status --porcelain=v1 -z``; renames yield both sides."""
    fields = [f for f in payload.split("\0") if f]
    paths: set[str] = set()
    i = 0
    while i < len(fields):
        entry = fields[i]
        i += 1
        if len(entry) < 4:
            continue
        code, path = entry[:2], entry[3:]
        paths.add(path)
        if "R" in code or "C" in code:
            if i < len(fields):
                paths.add(fields[i])
                i += 1
    return paths


def changed_paths() -> list[str] | None:
    """Every path differing from ``origin/main``, plus uncommitted work.

    Returns ``None`` when the change set cannot be determined, which callers
    must treat as "run everything".
    """
    base = _git("merge-base", "HEAD", BASE_REF)
    if base is None:
        return None
    committed = _git("diff", "--name-only", "-z", f"{base.strip()}..HEAD")
    if committed is None:
        return None
    status = _git("status", "--porcelain=v1", "-z")
    if status is None:
        return None
    paths = {p for p in committed.split("\0") if p}
    paths.update(_parse_status(status))
    return sorted(paths)


def decide(paths: list[str] | None) -> str:
    """``DOCS`` only when the change set is known, non-empty, and all prose."""
    if not paths:
        return FULL
    if any(is_code_path(p) for p in paths):
        return FULL
    return DOCS


def pytest_targets(decision: str) -> tuple[str, ...]:
    return DOC_COUPLED_TESTS if decision == DOCS else ALL_TESTS


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    paths = changed_paths()
    decision = decide(paths)

    if "--explain" in argv:
        if decision == DOCS:
            print(
                f"→ prose-only change ({len(paths)} paths): running "
                f"{len(DOC_COUPLED_TESTS)} doc-coupled test modules"
            )
        else:
            count = "undetermined" if paths is None else len(paths)
            print(f"→ full suite (changed paths: {count})")
        return 0

    print(" ".join(pytest_targets(decision)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
