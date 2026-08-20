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

from aet.validation_cache import ValidationCache

# Files that, when changed, can affect any test outcome. The safe fallback is
# the full suite.
_SHARED_PATHS: frozenset[str] = frozenset(
    {
        "pyproject.toml",
        "Makefile",
        "tests/conftest.py",
    }
)


def _is_shared(path: str) -> bool:
    """Return True when ``path`` is shared test infrastructure or root config."""
    p = path.strip()
    if not p:
        return False
    if p in _SHARED_PATHS:
        return True
    if p.startswith("tests/fixtures/"):
        return True
    if p.startswith("tests/conftest"):
        return True
    return False


def _module_targets(path: str, repo_root: Path) -> list[str]:
    """Return test-file paths that correspond to ``path`` by name or directory.

    For ``src/aet/<module>.py`` the floor is ``tests/test_<module>.py`` plus any
    ``tests/**/test_<module>.py`` that already exists. For
    ``src/aet/<dir>/<module>.py`` the floor is ``tests/<dir>/test_<module>.py``
    plus matching-name tests under ``tests/<dir>``.
    """
    p = Path(path)
    parts = p.parts
    if len(parts) < 2 or parts[0] != "src":
        return []

    # Drop the leading ``src`` and the file name; ``rel_dir`` is the package
    # path under ``src`` (e.g. ``("aet",)`` or ``("aet", "cli")``).
    rel_dir = parts[1:-1]
    if rel_dir and rel_dir[0] == "aet":
        rel_dir = rel_dir[1:]

    module_name = p.stem
    base_dir = repo_root / "tests" / Path(*rel_dir) if rel_dir else repo_root / "tests"

    targets: list[str] = []
    # Same-directory floor.
    same_dir_test = base_dir / f"test_{module_name}.py"
    targets.append(str(same_dir_test.relative_to(repo_root)))

    # Matching-name tests anywhere under the corresponding test directory.
    if base_dir.exists():
        for match in base_dir.rglob(f"test_{module_name}.py"):
            rel = str(match.relative_to(repo_root))
            if rel not in targets:
                targets.append(rel)

    return targets


def select_targeted_tests(
    changed_files: list[str],
    *,
    repo_root: str | Path | None = None,
) -> list[str]:
    """Return the path-based floor of pytest targets for ``changed_files``.

    - Shared infrastructure or an empty change set returns ``["tests/"]``.
    - Changed test files are included as-is.
    - Changed source files under ``src/`` map to same-directory and matching-name
      test files under ``tests/``.
    - When no specific target can be derived, the full suite is returned.

    Results are deduplicated and sorted.
    """
    root = Path(repo_root).resolve() if repo_root else Path.cwd()

    if not changed_files:
        return ["tests/"]
    if any(_is_shared(p) for p in changed_files):
        return ["tests/"]

    targets: set[str] = set()
    for path in changed_files:
        if path.startswith("tests/"):
            targets.add(path)
            continue
        derived = _module_targets(path, root)
        if derived:
            targets.update(derived)

    if not targets:
        return ["tests/"]
    return sorted(targets)


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
