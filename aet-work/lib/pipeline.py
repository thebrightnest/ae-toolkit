"""Pipeline stage state machine."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import evidence
import telemetry


@dataclass(frozen=True)
class Stage:
    """A pipeline stage definition."""

    name: str
    skills: list[str]
    next_stage: str | None
    session_group: int | None = None
    conditional: Callable[[str, str], bool] | None = None


STAGES: list[Stage] = [
    Stage(
        name="plan-approved",
        skills=["aet-tdd", "aet-implement"],
        next_stage="implemented",
        session_group=1,
    ),
    Stage(
        name="implemented",
        skills=["aet-qa"],
        next_stage="qa-complete",
        session_group=1,
    ),
    Stage(
        name="qa-complete",
        skills=["aet-review"],
        next_stage="reviewed",
        session_group=2,
    ),
    Stage(
        name="reviewed",
        skills=["aet-cso"],
        next_stage="secure",
        session_group=3,
        conditional=lambda plan_file, worktree_dir: _security_sensitive(worktree_dir),
    ),
    Stage(
        name="secure",
        skills=["aet-sync-docs"],
        next_stage="synced",
        session_group=3,
        conditional=lambda plan_file, worktree_dir: _divergences_found(plan_file, worktree_dir),
    ),
    Stage(
        name="synced",
        skills=[],
        next_stage="done",
        session_group=None,
    ),
]

STAGE_MAP: dict[str, Stage] = {s.name: s for s in STAGES}


def get_stage(name: str) -> Stage | None:
    """Return a stage by name."""
    return STAGE_MAP.get(name)


def get_next_stage(current: str) -> Stage | None:
    """Return the next stage after the current one."""
    stage = STAGE_MAP.get(current)
    if not stage or not stage.next_stage:
        return None
    return STAGE_MAP.get(stage.next_stage)


def group_stages_by_session(isolation: str = "standard") -> list[list[Stage]]:
    """Group stages into session bundles based on isolation level."""
    if isolation == "minimal":
        return [STAGES[:-1]]  # all stages except synced in one session
    if isolation == "full":
        return [[s] for s in STAGES if s.skills]

    # standard: group by session_group
    groups: dict[int, list[Stage]] = {}
    for stage in STAGES:
        if stage.session_group is None:
            continue
        groups.setdefault(stage.session_group, []).append(stage)
    return [groups[k] for k in sorted(groups)]


def _security_sensitive(worktree_dir: str) -> bool:
    """Check if diff touches auth, data models, API, or dependencies."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "-C", worktree_dir, "diff", "--name-only", "main...HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        files = result.stdout.lower()
        keywords = [
            "auth",
            "login",
            "password",
            "token",
            "secret",
            "model",
            "api",
            "route",
            "endpoint",
            "package",
            "requirements",
            "package.json",
            "dockerfile",
            "docker-compose",
        ]
        return any(k in files for k in keywords)
    except subprocess.CalledProcessError:
        return False


def _divergences_found(plan_file: str, worktree_dir: str) -> bool:
    """Return True when review/cso/sync-docs verdicts report findings.

    Reads the structured evidence verdicts from the evidence home rather than
    the legacy on-disk markdown reports. A non-empty ``findings`` list
    (review/cso) or ``divergences`` list (sync-docs) means the sync-docs stage
    should run.
    """
    task_id = Path(plan_file).stem.removesuffix("-plan")
    project_slug = telemetry.derive_project_slug(worktree_dir)

    for kind in ("review", "cso"):
        try:
            path = evidence.evidence_path(
                task_id=task_id, kind=kind, project_slug=project_slug
            )
            record = evidence.read_verdict(path)
            evidence.validate_verdict(record, kind)
        except (
            FileNotFoundError,
            evidence.VerdictValidationError,
            evidence.VerdictValueError,
        ):
            continue
        if record.get("findings"):
            return True

    try:
        path = evidence.evidence_path(
            task_id=task_id, kind="sync-docs", project_slug=project_slug
        )
        record = evidence.read_verdict(path)
        evidence.validate_verdict(record, "sync-docs")
    except (
        FileNotFoundError,
        evidence.VerdictValidationError,
        evidence.VerdictValueError,
    ):
        return False
    return bool(record.get("divergences"))
