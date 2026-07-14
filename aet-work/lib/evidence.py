"""Structured gate evidence contract.

Checking skills (aet-qa, aet-review, aet-cso, aet-sync-docs) write validated
JSON verdicts to a project-namespaced archive. The orchestrator consumes these
verdicts for stage gating rather than parsing the human-readable plan footer.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import telemetry

DEFAULT_REPORTS_DIR = Path.home() / ".aet" / "reports"

SCHEMAS: dict[str, dict[str, type]] = {
    "qa": {
        "task_id": str,
        "stage": str,
        "skill": str,
        "verdict": str,
        "summary": str,
        "generated_at": str,
        "test_command": str,
        "tests_total": int,
        "tests_passed": int,
        "tests_failed": int,
    },
    "review": {
        "task_id": str,
        "stage": str,
        "skill": str,
        "verdict": str,
        "summary": str,
        "generated_at": str,
        "findings": list,
    },
    "cso": {
        "task_id": str,
        "stage": str,
        "skill": str,
        "verdict": str,
        "summary": str,
        "generated_at": str,
        "findings": list,
    },
    "sync-docs": {
        "task_id": str,
        "stage": str,
        "skill": str,
        "verdict": str,
        "summary": str,
        "generated_at": str,
        "divergences": list,
    },
}

VALID_VERDICTS = {"pass", "fail"}


class VerdictValidationError(ValueError):
    """Raised when a verdict record does not match its schema."""


class VerdictValueError(ValueError):
    """Raised when a verdict field contains an invalid value."""


def reports_dir() -> Path:
    """Return the reports archive root, respecting ``AET_REPORTS_DIR``."""
    env = os.environ.get("AET_REPORTS_DIR")
    return Path(env).expanduser() if env else DEFAULT_REPORTS_DIR


def evidence_path(
    task_id: str,
    kind: str,
    project_slug: str | None = None,
    reports_root: str | Path | None = None,
) -> Path:
    """Return the filesystem path for a verdict file.

    Args:
        task_id: Identifier for the task/plan being evaluated.
        kind: Verdict kind — must be a key in ``SCHEMAS``.
        project_slug: Project namespace; derived from the current repo when omitted.
        reports_root: Override the reports archive root.
    """
    if kind not in SCHEMAS:
        raise VerdictValidationError(f"Unknown verdict kind: {kind!r}")

    root = Path(reports_root).expanduser() if reports_root else reports_dir()
    slug = project_slug if project_slug else telemetry.derive_project_slug()
    return root / slug / task_id / f"{kind}.json"


def evidence_path_env_var(kind: str) -> str:
    """Return the per-kind env var name: ``AET_EVIDENCE_PATH_<KIND>``.

    The kind is uppercased with non-alphanumeric characters replaced by
    ``_`` (e.g. ``sync-docs`` → ``AET_EVIDENCE_PATH_SYNC_DOCS``).
    """
    suffix = "".join(ch if ch.isalnum() else "_" for ch in kind.upper())
    return f"AET_EVIDENCE_PATH_{suffix}"


def resolve_verdict_path(
    task_id: str,
    kind: str,
    project_slug: str | None = None,
    reports_root: str | Path | None = None,
) -> Path:
    """Resolve the canonical verdict path with a three-step precedence.

    1. ``$AET_EVIDENCE_PATH`` — single-stage sessions (unchanged behavior).
    2. ``$AET_EVIDENCE_PATH_<KIND>`` — group sessions publish one per kind.
    3. Default: :func:`evidence_path` (project-namespaced archive).

    Writers and the gate must share this single derivation; hand-computing
    slugs from the worktree CWD is out of contract (ADR-023).
    """
    if kind not in SCHEMAS:
        raise VerdictValidationError(f"Unknown verdict kind: {kind!r}")

    single = os.environ.get("AET_EVIDENCE_PATH")
    if single:
        return Path(single).expanduser()
    per_kind = os.environ.get(evidence_path_env_var(kind))
    if per_kind:
        return Path(per_kind).expanduser()
    return evidence_path(
        task_id=task_id,
        kind=kind,
        project_slug=project_slug,
        reports_root=reports_root,
    )


def validate_verdict(record: dict[str, Any], kind: str) -> None:
    """Validate a verdict record against the schema for ``kind``.

    Raises:
        VerdictValidationError: If a required key is missing or has the wrong type.
        VerdictValueError: If a well-typed field contains an invalid value.
    """
    schema = SCHEMAS.get(kind)
    if schema is None:
        raise VerdictValidationError(f"Unknown verdict kind: {kind!r}")

    for key, expected_type in schema.items():
        if key not in record:
            raise VerdictValidationError(
                f"Missing required key {key!r} for {kind!r} verdict"
            )
        value = record[key]
        if not isinstance(value, expected_type):
            raise VerdictValidationError(
                f"Key {key!r} for {kind!r} verdict must be {expected_type.__name__}, "
                f"got {type(value).__name__}"
            )

    if record.get("verdict") not in VALID_VERDICTS:
        raise VerdictValueError(
            f"verdict must be one of {VALID_VERDICTS}, got {record.get('verdict')!r}"
        )


def write_verdict(
    task_id: str,
    kind: str,
    record: dict[str, Any],
    project_slug: str | None = None,
    reports_root: str | Path | None = None,
    path: str | Path | None = None,
) -> Path:
    """Validate and write a verdict record to the archive.

    ``path`` overrides the computed destination; callers that need the
    canonical env-aware precedence (ADR-023) resolve it via
    :func:`resolve_verdict_path` and pass the result here.

    Returns:
        The path to the written verdict file.
    """
    validate_verdict(record, kind)
    if path is None:
        path = evidence_path(
            task_id=task_id,
            kind=kind,
            project_slug=project_slug,
            reports_root=reports_root,
        )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def read_verdict(path: str | Path) -> dict[str, Any]:
    """Read and parse a verdict JSON file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Verdict not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))
