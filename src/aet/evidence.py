"""Structured gate evidence contract.

Checking skills (aet-qa, aet-review, aet-cso, aet-sync-docs) write validated
JSON verdicts to a project-namespaced archive. The orchestrator consumes these
verdicts for stage gating rather than parsing the human-readable plan footer.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from aet import telemetry, user_paths, verifier

SCHEMAS: dict[str, dict[str, type]] = {
    "qa": {
        "task_id": str,
        "stage": str,
        "skill": str,
        "verdict": str,
        "summary": str,
        "generated_at": str,
        "tree_hash": str,
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
        "tree_hash": str,
        "findings": list,
    },
    "cso": {
        "task_id": str,
        "stage": str,
        "skill": str,
        "verdict": str,
        "summary": str,
        "generated_at": str,
        "tree_hash": str,
        "findings": list,
    },
    "sync-docs": {
        "task_id": str,
        "stage": str,
        "skill": str,
        "verdict": str,
        "summary": str,
        "generated_at": str,
        "tree_hash": str,
        "divergences": list,
    },
    "verify": {
        "task_id": str,
        "stage": str,
        "skill": str,
        "verdict": str,
        "summary": str,
        "generated_at": str,
        "tree_hash": str,
    },
    "batch": {
        "branch": str,
        "verdict": str,
        "summary": str,
        "generated_at": str,
        "tree_hash": str,
        "task_ids": list,
    },
}

VALID_VERDICTS = {"pass", "fail"}

PLACEHOLDER_SUMMARIES: frozenset[str] = frozenset(
    {
        "pending",
        "todo",
        "tbd",
        "placeholder",
        "n/a",
        "na",
        "none",
        "null",
        "wip",
        "...",
        "<one-line>",
        "<one line>",
        "<summary>",
    }
)


class VerdictValidationError(ValueError):
    """Raised when a verdict record does not match its schema."""


class VerdictValueError(ValueError):
    """Raised when a verdict field contains an invalid value."""


def reports_dir() -> Path:
    """Return the reports archive root, respecting ``AET_REPORTS_DIR``."""
    return user_paths.reports_dir()


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
    if kind == "batch":
        return root / slug / "_train" / task_id / "batch.json"
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


# Per-kind builder flags for `aet gate submit`. Builder mode constructs the
# payload in code, so a writer supplies a verdict and its judgment inputs and
# never restates the schema. Keeping the invocation here means prompts and
# docs derive it instead of each carrying its own copy to drift (the defect
# behind the omitted-tree_hash and hand-rolled-payload failures).
BUILDER_FLAGS: dict[str, str] = {
    "qa": "--from-pytest <report.json> --summary <one-line>",
    "review": "--summary <one-line>",
    "cso": "--summary <one-line>",
    "sync-docs": "--summary <one-line> --divergence <item-or-file>",
    "verify": "--summary <one-line>",
    "batch": "--summary <one-line>",
}

# What the qa builder reads when no pytest-json-report file is available.
QA_REPORT_MINIMAL_KEYS = ("test_command", "tests_total", "tests_passed", "tests_failed")


def submit_command(kind: str, verdict: str = "<pass|fail>") -> str:
    """Return the sanctioned ``aet gate submit`` invocation for ``kind``.

    Builder mode (no ``--evidence``) is the documented path: it needs
    ``AET_TASK_ID``, which every orchestrated session already has, and it
    stamps the schema-owned fields itself.
    """
    if kind not in SCHEMAS:
        raise VerdictValidationError(f"Unknown verdict kind: {kind!r}")
    return f"aet gate submit --stage {kind} --verdict {verdict} {BUILDER_FLAGS[kind]}"


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

    summary = record.get("summary")
    if isinstance(summary, str):
        cleaned = summary.strip()
        if not cleaned:
            raise VerdictValueError("summary must not be empty or whitespace-only")
        if cleaned.lower() in PLACEHOLDER_SUMMARIES:
            raise VerdictValueError(
                f"summary must be a real attestation, got placeholder {summary!r}"
            )


def write_verdict(
    task_id: str,
    kind: str,
    record: dict[str, Any],
    project_slug: str | None = None,
    reports_root: str | Path | None = None,
    path: str | Path | None = None,
    worktree_dir: str | Path | None = None,
) -> Path:
    """Validate and write a verdict record to the archive.

    Stamps the record with ``tree_hash`` — a fingerprint of the working tree
    the verdict attests to — unless the caller supplied one. The code stamps
    it, not the skill: provenance is recorded, never remembered. ``worktree_dir``
    overrides the tree that gets hashed (defaults to the resolved repo root).

    ``path`` overrides the computed destination; callers that need the
    canonical env-aware precedence (ADR-023) resolve it via
    :func:`resolve_verdict_path` and pass the result here.

    Returns:
        The path to the written verdict file.
    """
    if "tree_hash" not in record:
        root = worktree_dir if worktree_dir is not None else telemetry.resolve_repo_root()
        record = {**record, "tree_hash": verifier.working_tree_hash(str(root))}
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
    if kind == "batch":
        existing: list[Any] = []
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    existing = loaded
                elif isinstance(loaded, dict):
                    existing = [loaded]
            except Exception:
                existing = []
        existing.append(record)
        path.write_text(json.dumps(existing, indent=2, default=str) + "\n", encoding="utf-8")
    else:
        path.write_text(json.dumps(record, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def read_verdict(path: str | Path) -> dict[str, Any]:
    """Read and parse a verdict JSON file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Verdict not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


# --- Validation freshness -------------------------------------------------
#
# A prior passing verdict stamps the tree it attests to. Before a later stage
# re-runs the same validation, it can ask whether the tree has moved since —
# and skip, lint-only, or run accordingly. The bias is always toward RUN: a
# stale skip ships broken code; a needless run only costs minutes.

RUN = "run"
LINT_ONLY = "lint-only"
SKIP = "skip"

_DOCS_PREFIXES = ("docs/",)
_DOCS_SUFFIXES = (".md",)
_DOCS_EXACT = frozenset({".agents/learnings.jsonl"})


@dataclass
class FreshnessResult:
    """The freshness decision for one (task, kind) against the current tree."""

    decision: str  # RUN | LINT_ONLY | SKIP
    reason: str
    prior_hash: str = ""
    current_hash: str = ""
    changed_paths: list[str] = field(default_factory=list)

    @property
    def needs_full_run(self) -> bool:
        return self.decision == RUN


def default_is_code_path(path: str) -> bool:
    """Whether a changed path can alter test outcomes (bias: assume yes).

    Only clearly non-executable churn — Markdown, ``docs/``, and the appended
    learnings log — is treated as non-code. Everything else, config and
    fixtures included, forces a full run.
    """
    p = path.strip()
    if not p:
        return False
    if p in _DOCS_EXACT:
        return False
    if p.startswith(_DOCS_PREFIXES):
        return False
    if p.endswith(_DOCS_SUFFIXES):
        return False
    return True


def find_batch_verdicts(
    task_id: str,
    branch: str | None = None,
    project_slug: str | None = None,
    reports_root: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Find and return all batch verdict records applicable to task_id or branch."""
    paths_to_check: list[Path] = []
    p1 = None
    try:
        p1 = resolve_verdict_path(
            task_id=task_id,
            kind="batch",
            project_slug=project_slug,
            reports_root=reports_root,
        )
        paths_to_check.append(p1)
    except Exception:
        pass

    if branch and branch != task_id:
        try:
            p2 = resolve_verdict_path(
                task_id=branch,
                kind="batch",
                project_slug=project_slug,
                reports_root=reports_root,
            )
            paths_to_check.append(p2)
        except Exception:
            pass

    # Also search _train directory under reports root
    root = Path(reports_root).expanduser() if reports_root else reports_dir()
    slug = project_slug if project_slug else telemetry.derive_project_slug()
    train_dir = root / slug / "_train"
    if train_dir.is_dir():
        for f in train_dir.rglob("batch.json"):
            if f not in paths_to_check:
                paths_to_check.append(f)

    seen_records: list[dict[str, Any]] = []
    for p in paths_to_check:
        if not p.is_file():
            continue
        try:
            loaded = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        raw_list = loaded if isinstance(loaded, list) else [loaded] if isinstance(loaded, dict) else []
        for rec in raw_list:
            if not isinstance(rec, dict):
                continue
            is_match = False
            rec_branch = rec.get("branch")
            rec_task_id = rec.get("task_id")
            rec_task_ids = rec.get("task_ids") or []
            if rec_task_id == task_id:
                is_match = True
            elif rec_branch and (rec_branch == task_id or (branch and rec_branch == branch)):
                is_match = True
            elif task_id in rec_task_ids or (branch and branch in rec_task_ids):
                is_match = True
            elif p1 is not None and str(p) == str(p1):
                is_match = True

            if is_match and rec not in seen_records:
                seen_records.append(rec)

    return seen_records


def validation_freshness(
    task_id: str,
    kind: str,
    worktree_dir: str | Path | None = None,
    *,
    branch: str | None = None,
    is_code_path: Callable[[str], bool] = default_is_code_path,
    project_slug: str | None = None,
    reports_root: str | Path | None = None,
) -> FreshnessResult:
    """Decide whether the last passing verdict still covers the current tree.

    Compares the working tree's fingerprint against the ``tree_hash`` stamped
    on the last verdict of this ``kind``:

    - no prior verdict, a prior *fail*, or an unknown hash → ``RUN``
    - identical tree → ``SKIP`` (nothing changed since it last passed)
    - only non-code paths changed → ``LINT_ONLY``
    - any code path changed, or the diff can't be computed → ``RUN``
    """
    root = str(worktree_dir) if worktree_dir is not None else str(telemetry.resolve_repo_root())
    current = verifier.working_tree_hash(root)
    if not current:
        return FreshnessResult(RUN, "working tree hash unavailable", current_hash=current)

    if kind == "batch":
        prior_records = find_batch_verdicts(
            task_id=task_id,
            branch=branch,
            project_slug=project_slug,
            reports_root=reports_root,
        )
        if not prior_records:
            return FreshnessResult(RUN, "no prior verdict", current_hash=current)
        prior: Any = prior_records
    else:
        path = resolve_verdict_path(
            task_id=task_id,
            kind=kind,
            project_slug=project_slug,
            reports_root=reports_root,
        )
        try:
            prior = read_verdict(path)
        except FileNotFoundError:
            return FreshnessResult(RUN, "no prior verdict", current_hash=current)

    if isinstance(prior, list):
        if not prior:
            return FreshnessResult(RUN, "no prior verdict", current_hash=current)
        exact = next(
            (r for r in prior if r.get("verdict") == "pass" and r.get("tree_hash") == current),
            None,
        )
        if exact is not None:
            return FreshnessResult(SKIP, "tree unchanged since last pass", current, current)

        latest_pass = next(
            (r for r in reversed(prior) if r.get("verdict") == "pass" and r.get("tree_hash")),
            None,
        )
        if latest_pass is None:
            return FreshnessResult(RUN, "prior verdict did not pass", current_hash=current)
        prior_hash = latest_pass.get("tree_hash") or ""
    else:
        if prior.get("verdict") != "pass":
            return FreshnessResult(RUN, "prior verdict did not pass", current_hash=current)

        prior_hash = prior.get("tree_hash") or ""
        if not prior_hash:
            return FreshnessResult(RUN, "prior verdict has no tree hash", current_hash=current)
        if prior_hash == current:
            return FreshnessResult(SKIP, "tree unchanged since last pass", prior_hash, current)

    paths = verifier.changed_paths(root, prior_hash, current)
    if paths is None:
        return FreshnessResult(RUN, "cannot diff against prior tree", prior_hash, current)
    code = [p for p in paths if is_code_path(p)]
    if not code:
        return FreshnessResult(
            LINT_ONLY, "only non-code paths changed", prior_hash, current, paths
        )
    return FreshnessResult(
        RUN, f"{len(code)} code path(s) changed", prior_hash, current, paths
    )
