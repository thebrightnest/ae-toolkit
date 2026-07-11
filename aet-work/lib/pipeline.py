"""Pipeline stage state machine."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Stage:
    """A pipeline stage definition.

    ``gate_key`` names the plan-frontmatter key that routes the stage
    (``security_review`` for aet-cso, ``docs_sync`` for aet-sync-docs). It is
    pure data: the orchestrator resolves it against the plan once per task,
    so no runtime judgment lives in the engine (ADR-020).
    """

    name: str
    skills: list[str]
    next_stage: str | None
    session_group: int | None = None
    gate_key: str | None = None


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
        gate_key="security_review",
    ),
    Stage(
        name="secure",
        skills=["aet-sync-docs"],
        next_stage="synced",
        session_group=3,
        gate_key="docs_sync",
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
