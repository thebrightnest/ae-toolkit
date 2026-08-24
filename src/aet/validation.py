"""Validation helpers for stage-scoped test selection.

``aet-implement`` uses :func:`select_targeted_tests` as a path-based floor for
the tests it must run, and records the actual commands it executed so
``aet-qa`` can perform gap analysis if the full suite later fails on a test
that implementation should have caught.

Single-run file-hash caching is provided through :class:`aet.validation_cache.ValidationCache`
and the convenience functions below so ``aet-implement`` can skip re-running a
targeted validation when tracked files have not changed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aet import change_scope, test_runners
from aet.validation_cache import ValidationCache


def select_targeted_tests(
    changed_files: list[str],
    *,
    repo_root: str | Path | None = None,
) -> list[str]:
    """Return the pytest targets that cover ``changed_files``.

    Delegates to :func:`aet.change_scope.targets`, the single authority for
    validation scope (ADR-049), so a stage session and ``make validate`` cannot
    disagree about what covers a module.

    This used to derive targets from filenames — ``src/aet/x.py`` implies
    ``tests/test_x.py`` — and appended that floor whether or not the file
    existed. For 69 of 82 modules it named a path pytest exits 4 on, and
    because the phantom kept the list non-empty it never fell back to the full
    suite. Every test for it built a synthetic repo in which the matching file
    did exist, which is why the suite never saw it.

    A prose-only change set returns ``[]``: nothing to run, rather than
    everything. An *empty* list is the fail-safe instead — from this caller it
    means the change set could not be determined, not that nothing changed.
    """
    if not changed_files:
        return ["tests/"]
    return change_scope.targets(
        list(changed_files), repo_root=repo_root or Path.cwd()
    )


def targeted_tests_path(repo_root: str | Path, run_id: str) -> Path:
    """Return the run-scoped file where implement records its targeted tests."""
    return Path(repo_root) / ".agents" / "runs" / run_id / "implement-targeted-tests.json"


def read_targeted_tests(path: str | Path) -> list[str]:
    """Read the JSON list of targeted-test commands, returning ``[]`` on any error."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if isinstance(data, list) and all(isinstance(item, str) for item in data):
        return data
    return []


def write_targeted_tests(
    path: str | Path, commands: list[str], *, indent: int | None = 2
) -> Path:
    """Write the list of targeted-test commands to ``path`` as JSON.

    Returns the written path.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(list(commands), indent=indent, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return p


def validation_cache_path(repo_root: str | Path, run_id: str) -> Path:
    """Return the run-scoped file where implement stores validation cache entries."""
    return Path(repo_root) / ".agents" / "runs" / run_id / "validation-cache.json"


def get_validation_cache(repo_root: str | Path, run_id: str) -> ValidationCache:
    """Return a :class:`ValidationCache` for ``run_id`` under ``repo_root``."""
    return ValidationCache.for_run(repo_root, run_id)


def cached_result(
    command: str,
    repo_root: str | Path,
    run_id: str,
    file_hash: str | None = None,
) -> dict[str, object] | None:
    """Return the cached result for ``command`` in ``run_id``, or ``None``.

    If ``file_hash`` is omitted, the current repository hash snapshot is
    computed automatically so the lookup matches the entry written by
    :func:`record_result` for the same file state.
    """
    cache = get_validation_cache(repo_root, run_id)
    if file_hash is None:
        file_hash = cache.compute_hash()
    return cache.get(command, file_hash)


def record_result(
    command: str,
    result: dict[str, object],
    repo_root: str | Path,
    run_id: str,
    file_hash: str | None = None,
) -> None:
    """Store ``result`` for ``command`` in the run-scoped validation cache.

    If ``file_hash`` is omitted, the current repository hash snapshot is
    computed automatically.
    """
    cache = get_validation_cache(repo_root, run_id)
    if file_hash is None:
        file_hash = cache.compute_hash()
    cache.set(command, file_hash, result)


# --- Gap analysis helpers --------------------------------------------------
#
# When QA fails on tests that implement did not run, the orchestrator records
# a gap analysis: which tests were missed and why they fell outside the
# path-based targeted-test floor.


def extract_test_targets(commands: list[str]) -> set[str]:
    """Extract path-based test targets from pytest commands.

    Returns normalized file/directory targets (e.g. ``tests/test_foo.py`` or
    ``tests/cli``). A bare ``pytest`` invocation or a target that names the
    whole suite is represented as ``tests/``. Non-pytest commands are ignored.
    """
    targets: set[str] = set()
    for command in commands:
        resolved = test_runners.resolve_test_command(command)
        if resolved is None:
            continue
        runner, args = resolved
        if runner not in ("pytest", "python -m pytest"):
            continue
        positional = [a for a in args if not a.startswith("-")]
        if not positional:
            targets.add("tests/")
            continue
        for arg in positional:
            normalized = arg.rstrip("/")
            if normalized in (".", "test", "tests", "./..."):
                targets.add("tests/")
            elif normalized.endswith(".py") or "/" in normalized:
                # Nodeids like ``tests/test_foo.py::test_x`` are reduced to the
                # file path so coverage compares at file granularity.
                targets.add(normalized.split("::")[0])
    return targets


def covers_test(targets: set[str], test_nodeid: str) -> bool:
    """Return True when ``test_nodeid`` is covered by any path-based target.

    A target ending in ``.py`` covers that file and any nodeid inside it. A
    directory target covers nodeids under that directory. The sentinel
    ``tests/`` covers every test under ``tests/``.
    """
    for target in targets:
        if target == "tests/" and test_nodeid.startswith("tests/"):
            return True
        if target.endswith(".py"):
            if test_nodeid == target or test_nodeid.startswith(target + "::"):
                return True
        else:
            if test_nodeid == target or test_nodeid.startswith(target + "/"):
                return True
    return False


def gap_analysis(
    failed_tests: list[str], implement_commands: list[str]
) -> dict[str, Any]:
    """Compare QA failures against the implement test set.

    Returns a dict with ``missed_tests`` (the subset of ``failed_tests`` not
    covered by the implement commands) and ``reason`` (a human-readable
    explanation when tests were missed, empty otherwise).
    """
    targets = extract_test_targets(implement_commands)
    missed = [t for t in failed_tests if not covers_test(targets, t)]
    return {
        "missed_tests": missed,
        "reason": "not in implement targeted tests" if missed else "",
    }
