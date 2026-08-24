"""Decide how much of the validate gate the current change set requires.

``make validate`` is this repo's only safety net — there is no CI — so the
default is always the full suite. This module maps a change set to the smallest
safe set of pytest targets, falling back to the full suite whenever the diff
cannot be narrowed reliably.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from aet import evidence, telemetry, test_deps

FULL = "full"
DOCS = "docs"

BASE_REF = "origin/main"

# A change set that selects at least this share of the suite is reported as the
# full suite instead: the coverage is the same and the command line stays short.
FULL_SUITE_SHARE = 0.5


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


def _is_shared_fixture(path: str) -> bool:
    """Changes to shared test infrastructure force the full suite."""
    p = path.strip()
    if not p:
        return False
    if p == "tests/conftest.py":
        return True
    if p.startswith("tests/fixtures/"):
        return True
    return False


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


def tier(paths: list[str] | None) -> str:
    """Scope tier from the change set, reusing ADR-025 vocabulary.

    Never keyed on the plan's ``*Stage:*`` label.
    """
    if paths is None or not paths:
        return evidence.RUN
    if any(is_code_path(p) for p in paths):
        return evidence.RUN
    return evidence.LINT_ONLY


def targets(paths: list[str] | None, repo_root: str | Path | None = None) -> list[str]:
    """Map a change set to the smallest safe set of pytest targets.

    - ``None`` or an empty diff → ``["tests/"]`` (fail-safe).
    - Prose-only change → ``[]`` (the Makefile skips pytest).
    - ``conftest.py`` or a shared fixture → ``["tests/"]``.
    - A changed code path that no test reaches → ``["tests/"]``. Running
      nothing for it would be the one unsafe answer.
    - Otherwise the test files that reach the changed paths, collapsed to
      ``["tests/"]`` once they are most of the suite.

    Selection is derived from the source (:mod:`aet.test_deps`), not from a
    table: the fact "this test covers that module" is written in the test file,
    and a second copy of it in this module could only drift.

    ``repo_root`` defaults to the resolved repository root, which is what the
    ``make validate`` entry point wants; callers holding a root pass it.
    """
    if paths is None:
        return ["tests/"]
    code_paths = [p for p in paths if is_code_path(p)]
    if not code_paths:
        return []
    if any(_is_shared_fixture(p) for p in code_paths):
        return ["tests/"]

    root = str(Path(repo_root).resolve()) if repo_root else str(telemetry.resolve_repo_root())
    deps = test_deps.dependency_map(root)
    selected: set[str] = set()
    for path in code_paths:
        if path.startswith("tests/"):
            selected.add(path)
            continue
        reached = deps.tests_for(path)
        if not reached:
            return ["tests/"]
        selected.update(reached)

    if not selected:
        return ["tests/"]
    if len(selected) >= len(deps.test_files) * FULL_SUITE_SHARE:
        return ["tests/"]
    return sorted(selected)


def decide(paths: list[str] | None) -> str:
    """``DOCS`` only when the change set is known, non-empty, and all prose."""
    if not paths:
        return FULL
    if any(is_code_path(p) for p in paths):
        return FULL
    return DOCS


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    paths = changed_paths()
    decision = decide(paths)
    scope = targets(paths)

    if "--explain" in argv:
        if decision == DOCS:
            print(
                f"→ prose-only change ({len(paths)} paths): skipping pytest"
            )
        else:
            count = "undetermined" if paths is None else len(paths)
            if scope == ["tests/"]:
                print(f"→ full suite (changed paths: {count})")
            else:
                print(f"→ targeted tests: {' '.join(scope)} (changed paths: {count})")
            # The prose above is for operators and may be re-worded freely; the
            # marker below is the contract telemetry.classify_test_scope reads
            # to see how much of the suite a `make validate` actually ran.
            print(f"{telemetry.TEST_SCOPE_MARKER_PREFIX} {' '.join(scope)}")
        return 0

    # Empty output tells the Makefile to skip the pytest step.
    print(" ".join(scope))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
