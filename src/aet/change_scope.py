"""Decide how much of the validate gate the current change set requires.

``make validate`` is this repo's only safety net — there is no CI — so the
default is always the full suite. This module maps a change set to the smallest
safe set of pytest targets, falling back to the full suite whenever the diff
cannot be narrowed reliably.
"""

from __future__ import annotations

import subprocess
import sys

from aet import evidence, telemetry

FULL = "full"
DOCS = "docs"

BASE_REF = "origin/main"

# Path-prefix → pytest target table. Longest prefix wins.
_PATH_TARGETS: list[tuple[str, str]] = [
    ("src/aet/backends/", "tests/backends"),
    ("src/aet/cli/", "tests/cli"),
    ("src/aet/panel/", "tests/panel"),
    ("src/aet/projections/", "tests/projections"),
    ("src/aet/failure.py", "tests/failure"),
    ("src/aet/gate.py", "tests/gate"),
    ("src/aet/evidence.py", "tests/gate"),
    ("src/aet/ledger.py", "tests/ledger"),
    ("src/aet/metrics.py", "tests/metrics"),
    ("src/aet/queue.py", "tests/queue"),
    ("src/aet/telemetry.py", "tests/telemetry"),
    ("src/aet/usage.py", "tests/usage"),
    ("src/aet/workflow.py", "tests/workflow"),
    ("src/aet/worktree.py", "tests/worktree"),
    ("src/aet/wirelog.py", "tests/wirelog"),
    ("src/aet/plan_parser.py", "tests/plan"),
    ("src/aet/plan_size.py", "tests/plan"),
    ("src/aet/plan_validate.py", "tests/plan"),
    ("src/aet/plans_lint.py", "tests/plan"),
    ("src/aet/verifier.py", "tests/plan"),
    ("src/aet/boundary.py", "tests/test_boundary.py"),
    ("src/aet/identity.py", "tests/test_identity.py"),
    ("src/aet/branch_ref.py", "tests/test_branch_ref.py"),
    ("src/aet/change_scope.py", "tests/test_change_scope.py"),
    ("src/aet/liveness.py", "tests/orchestrator/test_liveness.py"),
    ("src/aet/validation.py", "tests/test_validation.py"),
    ("src/aet/validation_cache.py", "tests/test_validation_cache.py"),
    ("src/aet/cli/release_prep.py", "tests/test_release_prep.py"),
    ("src/aet/cli/ship.py", "tests/ship"),
    ("src/aet/cli/orchestrator.py", "tests/orchestrator"),
    ("src/aet/integration_lock.py", "tests/orchestrator"),
    ("scripts/install.sh", "tests/installer/test_installer.py"),
    ("src/aet/cli/setup.py", "tests/installer/test_installer.py"),
    ("scripts/", "tests/scripts"),
]

# Path prefixes that exercise the single-pr / non-trunk integration surface.
# When the change set touches any of them, the rehearsal is added to the target
# list so the production-shaped config path is exercised (ADR-049).
REHEARSAL_TRIGGER_PREFIXES: frozenset[str] = frozenset(
    {
        "src/aet/cli/orchestrator.py",
        "src/aet/integration_lock.py",
        "src/aet/worktree.py",
        "src/aet/backends/factory.py",
    }
)
REHEARSAL_TARGET = "tests/orchestrator/test_single_pr_rehearsal.py"


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


def _target_for(path: str) -> str | None:
    """Return the pytest target for a single changed path, or ``None`` if unmapped."""
    matches = [(prefix, target) for prefix, target in _PATH_TARGETS if path.startswith(prefix)]
    if not matches:
        return None
    # Longest prefix wins.
    matches.sort(key=lambda pair: len(pair[0]), reverse=True)
    return matches[0][1]


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


def targets(paths: list[str] | None) -> list[str]:
    """Map a change set to the smallest safe set of pytest targets.

    - ``None`` or an empty diff → ``["tests/"]`` (fail-safe).
    - Prose-only change → ``[]`` (the Makefile skips pytest).
    - ``conftest.py``, shared fixtures, or an unmapped code path → ``["tests/"]``.
    - Otherwise, the deduplicated, sorted target list from :data:`_PATH_TARGETS`,
      plus the single-pr rehearsal when the change touches that surface.
    """
    if paths is None:
        return ["tests/"]
    code_paths = [p for p in paths if is_code_path(p)]
    if not code_paths:
        return []
    rehearsal_triggered = any(
        p.startswith(prefix)
        for p in code_paths
        for prefix in REHEARSAL_TRIGGER_PREFIXES
    )
    if any(_is_shared_fixture(p) for p in code_paths):
        return ["tests/"]
    mapped = [_target_for(p) for p in code_paths]
    if None in mapped:
        return ["tests/"]
    result = sorted(set(mapped))
    if rehearsal_triggered and REHEARSAL_TARGET not in result:
        result.append(REHEARSAL_TARGET)
        result.sort()
    return result


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
