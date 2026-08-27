"""Workflow-as-data: schema, packaged default, and loader.

A workflow file (``<repo_root>/.agents/workflows/<name>.json`` overriding the
packaged ``src/aet/workflows/<name>.json``) declares the stage sequence,
per-stage skill bindings, evidence verdict kinds, session grouping, and
routing as per-project data. Succession is list order — linear only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aet import evidence

SUPPORTED_VERSION = 1
VALID_ISOLATION_LEVELS = {"minimal", "standard", "full"}
VALID_GATE_DEFAULTS = {"required", "critical-only"}

_PACKAGED_DIR = Path(__file__).resolve().parent / "workflows"

_STAGE_KEYS = {"name", "skills", "evidence", "gate_key", "gate_default"}
_EXECUTION_POLICY_KEYS = {"session_groups"}
_ROUTING_KEYS = {"default", "by_stage"}
_WORKFLOW_KEYS = {
    "version",
    "name",
    "done_state",
    "stages",
    "execution_policy",
    "routing",
}


class WorkflowError(ValueError):
    """Raised when a workflow file is missing or structurally invalid."""


@dataclass(frozen=True)
class WorkflowStage:
    """One pipeline stage: name, skill bindings, verdict kind, plan gate key."""

    name: str
    skills: list[str]
    evidence: str | None
    gate_key: str | None
    gate_default: str = "required"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionPolicy:
    """Session grouping for the skilled stages (list of stage-name lists)."""

    session_groups: list[list[str]]
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Routing:
    """Harness/model routing: a per-workflow default plus per-stage overrides."""

    default: dict[str, Any]
    by_stage: dict[str, dict[str, Any]]
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Workflow:
    """A resolved, validated workflow definition."""

    version: int
    name: str
    done_state: str
    stages: list[WorkflowStage]
    stage_map: dict[str, WorkflowStage]
    execution_policy: ExecutionPolicy
    routing: Routing
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def entry_stage(self) -> str:
        """The first stage in list order."""
        return self.stages[0].name

    def next_stage(self, name: str) -> str | None:
        """Return the successor of ``name`` in list order.

        The last stage advances to ``done_state``; ``done_state`` itself has
        no successor and returns ``None``.
        """
        if name == self.done_state:
            return None
        stage = self.stage_map.get(name)
        if stage is None:
            raise WorkflowError(f"Unknown stage: {name!r}")
        index = self.stages.index(stage)
        if index == len(self.stages) - 1:
            return self.done_state
        return self.stages[index + 1].name

    def session_groups(self, isolation: str = "standard") -> list[list[WorkflowStage]]:
        """Group the skilled stages into session bundles per isolation level.

        ``minimal`` — every skilled stage in a single session; ``full`` — one
        session per skilled stage; ``standard`` — the groups declared in the
        workflow file's ``execution_policy.session_groups``.
        """
        if isolation not in VALID_ISOLATION_LEVELS:
            raise WorkflowError(
                f"Unknown isolation level: {isolation!r} "
                f"(expected one of {sorted(VALID_ISOLATION_LEVELS)})"
            )
        skilled = [s for s in self.stages if s.skills]
        if isolation == "minimal":
            return [skilled]
        if isolation == "full":
            return [[s] for s in skilled]
        return [
            [self.stage_map[name] for name in group]
            for group in self.execution_policy.session_groups
        ]


def load_workflow(repo_root: str | Path, workflow_name: str = "software") -> Workflow:
    """Load and validate a workflow definition.

    Resolution order: ``<repo_root>/.agents/workflows/<name>.json`` first,
    then the packaged ``src/aet/workflows/<name>.json``.

    Raises:
        WorkflowError: the file is missing, unreadable, or structurally invalid.
    """
    path = _resolve_workflow_path(repo_root, workflow_name)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"Cannot read workflow {workflow_name!r} at {path}: {exc}") from exc
    return _parse_workflow(raw, path)


def _resolve_workflow_path(repo_root: str | Path, workflow_name: str) -> Path:
    repo_file = Path(repo_root) / ".agents" / "workflows" / f"{workflow_name}.json"
    if repo_file.is_file():
        return repo_file
    packaged_file = _PACKAGED_DIR / f"{workflow_name}.json"
    if packaged_file.is_file():
        return packaged_file
    raise WorkflowError(
        f"Workflow {workflow_name!r} not found: looked in {repo_file} and {packaged_file}"
    )


def _parse_workflow(raw: Any, path: Path) -> Workflow:
    if not isinstance(raw, dict):
        raise WorkflowError(f"Workflow {path} must be a JSON object, got {type(raw).__name__}")

    version = raw.get("version")
    if version != SUPPORTED_VERSION:
        raise WorkflowError(
            f"Unsupported workflow version: {version!r} (expected {SUPPORTED_VERSION}) in {path}"
        )

    name = raw.get("name")
    if not isinstance(name, str) or not name:
        raise WorkflowError(f"Workflow {path} requires a non-empty string 'name'")

    done_state = raw.get("done_state")
    if not isinstance(done_state, str) or not done_state:
        raise WorkflowError(f"Workflow {path} requires a non-empty string 'done_state'")

    stages = _parse_stages(raw.get("stages"), path)
    stage_map = {}
    for stage in stages:
        if stage.name in stage_map:
            raise WorkflowError(f"Duplicate stage name: {stage.name!r} in {path}")
        stage_map[stage.name] = stage

    execution_policy = _parse_execution_policy(raw.get("execution_policy"), stages, stage_map, path)
    routing = _parse_routing(raw.get("routing"), stage_map, path)

    return Workflow(
        version=version,
        name=name,
        done_state=done_state,
        stages=stages,
        stage_map=stage_map,
        execution_policy=execution_policy,
        routing=routing,
        extra={k: v for k, v in raw.items() if k not in _WORKFLOW_KEYS},
    )


def _parse_stages(raw_stages: Any, path: Path) -> list[WorkflowStage]:
    if not isinstance(raw_stages, list) or not raw_stages:
        raise WorkflowError(f"Workflow {path} requires a non-empty 'stages' list")
    stages = []
    for index, raw_stage in enumerate(raw_stages):
        if not isinstance(raw_stage, dict):
            raise WorkflowError(
                f"Stage #{index} in {path} must be a JSON object, got {type(raw_stage).__name__}"
            )
        stage_name = raw_stage.get("name")
        if not isinstance(stage_name, str) or not stage_name:
            raise WorkflowError(f"Stage #{index} in {path} requires a non-empty string 'name'")
        skills = raw_stage.get("skills")
        if not isinstance(skills, list) or not all(isinstance(s, str) for s in skills):
            raise WorkflowError(f"Stage {stage_name!r} in {path} requires 'skills' as a list of strings")
        verdict_kind = raw_stage.get("evidence")
        if verdict_kind is not None and verdict_kind not in evidence.SCHEMAS:
            raise WorkflowError(
                f"Stage {stage_name!r} in {path} has unknown evidence kind {verdict_kind!r} "
                f"(expected one of {sorted(evidence.SCHEMAS)} or null)"
            )
        gate_key = raw_stage.get("gate_key")
        if gate_key is not None and not isinstance(gate_key, str):
            raise WorkflowError(
                f"Stage {stage_name!r} in {path} requires 'gate_key' as a string or null"
            )
        gate_default = raw_stage.get("gate_default")
        if gate_default is not None:
            if not isinstance(gate_default, str) or gate_default not in VALID_GATE_DEFAULTS:
                raise WorkflowError(
                    f"Stage {stage_name!r} in {path} has unknown gate_default {gate_default!r} "
                    f"(expected one of {sorted(VALID_GATE_DEFAULTS)})"
                )
        else:
            gate_default = "required"
        stages.append(
            WorkflowStage(
                name=stage_name,
                skills=list(skills),
                evidence=verdict_kind,
                gate_key=gate_key,
                gate_default=gate_default,
                extra={k: v for k, v in raw_stage.items() if k not in _STAGE_KEYS},
            )
        )
    return stages


def _parse_execution_policy(
    raw_policy: Any,
    stages: list[WorkflowStage],
    stage_map: dict[str, WorkflowStage],
    path: Path,
) -> ExecutionPolicy:
    if not isinstance(raw_policy, dict):
        raise WorkflowError(f"Workflow {path} requires an 'execution_policy' object")
    raw_groups = raw_policy.get("session_groups")
    if not isinstance(raw_groups, list):
        raise WorkflowError(f"Workflow {path} requires 'execution_policy.session_groups' as a list")
    groups = []
    seen = set()
    for group in raw_groups:
        if not isinstance(group, list) or not all(isinstance(n, str) for n in group):
            raise WorkflowError(
                f"Each session group in {path} must be a list of stage names, got {group!r}"
            )
        for stage_name in group:
            stage = stage_map.get(stage_name)
            if stage is None:
                raise WorkflowError(
                    f"Session group references unknown stage {stage_name!r} in {path}"
                )
            if not stage.skills:
                raise WorkflowError(
                    f"Session group contains skill-less stage {stage_name!r} in {path}"
                )
            if stage_name in seen:
                raise WorkflowError(
                    f"Stage {stage_name!r} appears in more than one session group in {path}"
                )
            seen.add(stage_name)
        groups.append(list(group))
    missing = [s.name for s in stages if s.skills and s.name not in seen]
    if missing:
        raise WorkflowError(
            f"Session groups must partition the skilled stages; missing {missing!r} in {path}"
        )
    return ExecutionPolicy(
        session_groups=groups,
        extra={k: v for k, v in raw_policy.items() if k not in _EXECUTION_POLICY_KEYS},
    )


def _parse_routing(raw_routing: Any, stage_map: dict[str, WorkflowStage], path: Path) -> Routing:
    if not isinstance(raw_routing, dict):
        raise WorkflowError(f"Workflow {path} requires a 'routing' object")
    default = _parse_route_target(raw_routing.get("default"), "routing.default", path)
    raw_by_stage = raw_routing.get("by_stage", {})
    if not isinstance(raw_by_stage, dict):
        raise WorkflowError(f"Workflow {path} requires 'routing.by_stage' as an object")
    by_stage = {}
    for stage_name, raw_target in raw_by_stage.items():
        if stage_name not in stage_map:
            raise WorkflowError(
                f"routing.by_stage references unknown stage {stage_name!r} in {path}"
            )
        by_stage[stage_name] = _parse_route_target(
            raw_target, f"routing.by_stage.{stage_name}", path
        )
    return Routing(
        default=default,
        by_stage=by_stage,
        extra={k: v for k, v in raw_routing.items() if k not in _ROUTING_KEYS},
    )


def _parse_route_target(raw_target: Any, label: str, path: Path) -> dict[str, Any]:
    if not isinstance(raw_target, dict):
        raise WorkflowError(f"{label} in {path} must be an object, got {type(raw_target).__name__}")
    harness = raw_target.get("harness")
    if not isinstance(harness, str) or not harness:
        raise WorkflowError(f"{label} in {path} requires a non-empty string 'harness'")
    model = raw_target.get("model")
    if model is not None and not isinstance(model, str):
        raise WorkflowError(f"{label} in {path} requires 'model' as a string or null")
    return dict(raw_target)
