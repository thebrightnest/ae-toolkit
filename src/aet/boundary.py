"""Boundary-contract lens — mechanical gate off the changed-file set.

When a diff touches both a response-shape file (serializer, controller, schema,
resource, DTO) and a client-consumer file (component, repository, api-client,
hook, store), the lens requires an agreement test that asserts the two sides
match.  The check is fail-closed: a tripped lens blocks the review verdict.

Pattern tables and the marker vocabulary are overridable via a
``boundary_contract`` key in ``.agents/aet-config.json`` (ADR-048 two-layer
config model).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aet import telemetry

DEFAULT_SHAPE_PATTERNS: list[str] = [
    "serializer",
    "serializers",
    "controller",
    "controllers",
    "schema",
    "schemas",
    "resource",
    "resources",
    "dto",
    "dtos",
]

DEFAULT_CONSUMER_PATTERNS: list[str] = [
    "component",
    "components",
    "repository",
    "repositories",
    "api-client",
    "api_client",
    "api-clients",
    "api_clients",
    "hook",
    "hooks",
    "store",
    "stores",
]

DEFAULT_MARKER_VOCABULARY: list[str] = [
    "msw",
    "nock",
    "Http::fake",
    "mirage",
]

CONFIG_PATH = ".agents/aet-config.json"


@dataclass
class BoundaryResult:
    """Outcome of a boundary-contract check."""

    tripped: bool
    reason: str
    shape_paths: list[str] = field(default_factory=list)
    consumer_paths: list[str] = field(default_factory=list)
    agreement_tests: list[str] = field(default_factory=list)
    pairs: list[tuple[str, str]] = field(default_factory=list)


def _load_config(repo_root: Path | None = None) -> dict[str, Any]:
    """Read the optional ``boundary_contract`` section from AET config.

    The config is resolved at ``.agents/aet-config.json`` relative to the repo
    root.  Missing files and malformed JSON are treated as empty configs, which
    keeps the lens usable in any checkout and biases toward the safe default
    tables.
    """
    try:
        root = Path(repo_root) if repo_root is not None else telemetry.resolve_repo_root()
    except Exception:
        return {}
    path = root / CONFIG_PATH
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data.get("boundary_contract") or {}


def _is_shape(path: str, patterns: list[str]) -> bool:
    """Whether ``path`` matches a response-shape pattern."""
    return _matches_any(path, patterns)


def _is_consumer(path: str, patterns: list[str]) -> bool:
    """Whether ``path`` matches a client-consumer pattern."""
    return _matches_any(path, patterns)


def _matches_any(path: str, patterns: list[str]) -> bool:
    lowered = path.lower()
    for pat in patterns:
        if pat.lower() in lowered:
            return True
        # Path-segment match catches directory names like ``serializers/``
        # even when the file name itself does not contain the pattern.
        if f"/{pat.lower()}/" in lowered or lowered.startswith(f"{pat.lower()}/"):
            return True
    return False


def _find_agreement_tests(
    repo_root: Path,
    shape_paths: list[str],
    consumer_paths: list[str],
    marker_vocabulary: list[str],
) -> list[str]:
    """Search ``tests/`` for files that reference both sides or use markers."""
    tests_dir = repo_root / "tests"
    if not tests_dir.is_dir():
        return []

    shape_names = [Path(p).stem for p in shape_paths]
    consumer_names = [Path(p).stem for p in consumer_paths]

    agreement_tests: list[str] = []
    for test_file in tests_dir.rglob("test_*.py"):
        try:
            text = test_file.read_text(encoding="utf-8")
        except OSError:
            continue

        has_marker = any(marker in text for marker in marker_vocabulary)
        has_shape = any(name in text for name in shape_names)
        has_consumer = any(name in text for name in consumer_names)

        if has_marker or (has_shape and has_consumer):
            agreement_tests.append(str(test_file.relative_to(repo_root)))

    return sorted(set(agreement_tests))


def check(
    paths: list[str] | None,
    repo_root: Path | str | None = None,
    config: dict[str, Any] | None = None,
) -> BoundaryResult:
    """Run the boundary-contract lens over the supplied changed paths.

    Args:
        paths: Changed paths, typically from ``change_scope.changed_paths()``.
            ``None`` or empty means the lens does not trip.
        repo_root: Repository root used to locate ``.agents/aet-config.json``
            and the ``tests/`` directory.  Defaults to the resolved repo root.
        config: Optional pre-loaded ``boundary_contract`` config dict.  When
            supplied, the on-disk config is not read.

    Returns:
        A :class:`BoundaryResult` describing whether the lens tripped and which
        agreement tests were found.
    """
    if not paths:
        return BoundaryResult(
            tripped=False,
            reason="no changed paths to analyze",
            shape_paths=[],
            consumer_paths=[],
            agreement_tests=[],
            pairs=[],
        )

    if config is None:
        config = _load_config(repo_root)

    shape_patterns = config.get("shape_patterns", DEFAULT_SHAPE_PATTERNS)
    consumer_patterns = config.get("consumer_patterns", DEFAULT_CONSUMER_PATTERNS)
    marker_vocabulary = config.get("marker_vocabulary", DEFAULT_MARKER_VOCABULARY)

    shape_paths = [p for p in paths if _is_shape(p, shape_patterns)]
    consumer_paths = [p for p in paths if _is_consumer(p, consumer_patterns)]

    if not shape_paths or not consumer_paths:
        return BoundaryResult(
            tripped=False,
            reason="change set does not touch both shape and consumer sides",
            shape_paths=shape_paths,
            consumer_paths=consumer_paths,
            agreement_tests=[],
            pairs=[],
        )

    pairs = [(s, c) for s in shape_paths for c in consumer_paths]

    root: Path | None = None
    if repo_root is not None:
        root = Path(repo_root)
    else:
        try:
            root = telemetry.resolve_repo_root()
        except Exception:
            root = None

    agreement_tests: list[str] = []
    if root is not None:
        agreement_tests = _find_agreement_tests(
            root, shape_paths, consumer_paths, marker_vocabulary
        )

    if agreement_tests:
        return BoundaryResult(
            tripped=False,
            reason="agreement test(s) found",
            shape_paths=shape_paths,
            consumer_paths=consumer_paths,
            agreement_tests=agreement_tests,
            pairs=pairs,
        )

    return BoundaryResult(
        tripped=True,
        reason="shape-consumer pair(s) changed without agreement test",
        shape_paths=shape_paths,
        consumer_paths=consumer_paths,
        agreement_tests=[],
        pairs=pairs,
    )
