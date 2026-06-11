"""Pipeline stage state machine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


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
    """Check if review or cso reports note divergences."""
    import os

    import subprocess

    try:
        result = subprocess.run(
            ["git", "-C", worktree_dir, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        repo_root = result.stdout.strip()
        task_id = os.path.basename(plan_file).replace("-plan.md", "")
        report_dir = f"/tmp/aet-reports/{task_id}"
        if os.path.isdir(report_dir):
            return any(
                f.endswith(".md")
                for f in os.listdir(report_dir)
            )
        return False
    except subprocess.CalledProcessError:
        return False
