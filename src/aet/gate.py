"""Shared gate evidence helpers.

Single-sources task-branch detection, required-stage resolution, and verdict
path derivation for the pre-push hook and the single-pr integration gate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aet import evidence, plan_parser, telemetry
from aet.workflow import load_workflow


def required_evidence(repo_root: str | Path, plan_fm: dict[str, Any]) -> list[tuple[str, str]]:
    """Resolve required (stage_name, evidence_kind) pairs from the workflow.

    Mirrors the orchestrator's ``stage_enabled`` gate: a gated stage is required
    unless the plan frontmatter marks its gate key ``skipped`` (a missing key
    fails safe to required). Ungated evidence stages (qa, review) always run.
    """
    workflow_name = plan_fm.get("workflow") or "software"
    try:
        workflow = load_workflow(repo_root, workflow_name)
    except Exception:
        return []
    required = []
    for stage in workflow.stages:
        if not stage.evidence:
            continue
        if stage.gate_key and plan_fm.get(stage.gate_key) == "skipped":
            continue
        required.append((stage.name, stage.evidence))
    return required


def verdict_status(task_id: str, kind: str, repo_root: str | Path) -> tuple[bool, str]:
    """Return (passed, detail) for one required gate kind.

    Reads the canonical project-namespaced verdict path — the same derivation
    the orchestrator's gate uses — and passes only on ``verdict: "pass"``.
    """
    slug = telemetry.derive_project_slug(repo_root)
    path = evidence.evidence_path(task_id=task_id, kind=kind, project_slug=slug)
    try:
        record = evidence.read_verdict(path)
    except FileNotFoundError:
        return False, f"no verdict recorded at {path}"
    except (json.JSONDecodeError, OSError) as exc:
        return False, f"unreadable verdict at {path}: {exc}"
    verdict = record.get("verdict")
    if verdict != "pass":
        return False, f"verdict is {verdict!r} at {path}"
    return True, ""


def check_task_evidence(
    task_id: str,
    plan_fm: dict[str, Any],
    repo_root: str | Path,
) -> tuple[bool, list[str]]:
    """Check all required gate evidence for a task.

    Returns ``(ok, failures)`` where ``failures`` lists every required stage
    whose verdict is missing, unreadable, or not ``pass``.
    """
    failures: list[str] = []
    for stage_name, kind in required_evidence(repo_root, plan_fm):
        passed, detail = verdict_status(task_id, kind, repo_root)
        if not passed:
            failures.append(
                f"  task '{task_id}': required gate '{kind}' "
                f"(stage '{stage_name}') — {detail}"
            )
    return not failures, failures


def plan_for_branch(repo_root: str | Path, branch: str) -> Path | None:
    """Task-branch convention: branch name == task id == plan file stem.

    This mirrors aet-work's worktree naming (``branch_name = task_id``); a
    branch is a task branch only when a matching plan file exists.
    """
    plan = Path(repo_root) / "docs" / "plans" / f"{branch}.md"
    return plan if plan.is_file() else None


def is_task_branch(repo_root: str | Path, branch: str) -> bool:
    """Return True when a local plan file exists for ``branch``."""
    return plan_for_branch(repo_root, branch) is not None


def parse_frontmatter(plan_path: Path) -> dict[str, Any]:
    """Best-effort plan frontmatter parser for gate checks."""
    try:
        return plan_parser.parse_frontmatter(plan_path)
    except Exception:
        return {}
