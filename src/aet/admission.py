"""Single admission operation for plans joining the board (ADR-019, R-1..R-12).

Both board doors — `aet sprint add` and `aet sprint intake` — obtain their
admission decisions exclusively from `admit_plan`. The admission policy, validation,
and task construction live here in the domain layer, keeping the CLI doors
focused entirely on presentation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from aet import plan_parser, plan_validate
from aet.queue import HISTORY_TERMINAL_STATES, read_history


class SkipReason(str, Enum):
    """Reasons why a plan is skipped from admission."""

    ALREADY_IN_QUEUE = "already in queue"
    ALREADY_SETTLED = "already settled"


class RefusalReason(str, Enum):
    """Reasons why a plan is refused admission."""

    PLAN_NOT_FOUND = "plan file not found"
    VALIDATION_FAILED = "intake validation failed"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class Admitted:
    """Outcome when a plan is admitted and the task is built."""

    task: dict[str, Any]
    plan_file: Path


@dataclass(frozen=True)
class Skipped:
    """Outcome when a plan is already live or settled."""

    reason: SkipReason
    plan_file: Path | None = None
    existing_task: dict[str, Any] | None = None


@dataclass(frozen=True)
class Refused:
    """Outcome when a plan is refused entry to the board."""

    reason: RefusalReason
    plan_file: Path | None = None
    findings: list[plan_validate.Finding] | None = None
    coverage: plan_validate.RecordCoverage | None = None
    blockers: list[str] | None = None
    detail: str | None = None


AdmissionOutcome = Admitted | Skipped | Refused


def resolve_plan(target: str | Path, plans_dir: Path) -> Path | None:
    """Resolve a target identifier or file path to a plan file in ``plans_dir``."""
    target_str = str(target)
    try:
        return Path(
            plan_parser.resolve_plan_arg(target_str, plans_dir=plans_dir)
        )
    except ValueError:
        pass

    prefix = f"{target_str}-"
    matches = [
        p
        for p in plans_dir.glob("*.md")
        if p.name.startswith(prefix) or p.stem == target_str
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def settled_ids_from(
    backend: Any = None,
    history_file: str | Path | None = None,
    history: list[dict[str, Any]] | None = None,
) -> set[str]:
    """Extract the set of settled task IDs from backend, history list, or JSONL file."""
    settled: set[str] = set()

    if history is not None:
        settled.update(t.get("id") for t in history if t.get("id"))

    if backend is not None:
        getter = getattr(backend, "settled_ids", None)
        if getter is not None:
            try:
                settled |= getter()
            except Exception:
                pass
        elif history is None and hasattr(backend, "load"):
            try:
                data = backend.load()
                settled.update(
                    t.get("id") for t in data.get("history", []) if t.get("id")
                )
            except Exception:
                pass

    path = history_file or (
        getattr(backend, "history_file", None) if backend else None
    )
    if path and Path(path).exists():
        try:
            settled |= {
                record["id"]
                for record in read_history(str(path))
                if record.get("id")
                and record.get("state") in HISTORY_TERMINAL_STATES
            }
        except Exception:
            pass

    return settled


def unacked_intake_findings(
    plan_file: Path,
    plans_dir: Path,
    backend: Any,
    history_file: str | Path | None = None,
    queue: list[dict[str, Any]] | None = None,
    history: list[dict[str, Any]] | None = None,
) -> tuple[list[plan_validate.Finding], plan_validate.RecordCoverage | None]:
    """Return ``plan_file``'s unacked intake findings and coverage record."""
    all_plan_files = sorted(plans_dir.glob("*.md"))
    if plan_file not in all_plan_files:
        all_plan_files.append(plan_file)

    settled_ids = settled_ids_from(
        backend=backend, history_file=history_file, history=history
    )
    live_ids = {t.get("id") for t in (queue or []) if t.get("id")}
    extra_known = settled_ids | live_ids

    repo_root = Path(getattr(backend, "repo_root", "."))
    if hasattr(backend, "load"):
        record = plan_validate.coverage_from_backend(backend, repo_root)
    else:
        record = plan_validate.RecordCoverage({}, set(), None)

    findings = plan_validate.validate(
        all_plan_files,
        repo_root=repo_root,
        extra_known_ids=extra_known,
        extra_coverage=record.coverage,
    )
    plan_texts = {pf: pf.read_text(errors="ignore") for pf in all_plan_files}
    findings = plan_validate.apply_acks(findings, plan_texts)
    unacked = [f for f in findings if f.plan == plan_file and not f.acked]
    return unacked, record


def admit_plan(
    target: str | Path,
    plans_dir: Path,
    backend: Any,
    history_file: str | Path | None = None,
    queue: list[dict[str, Any]] | None = None,
    history: list[dict[str, Any]] | None = None,
    allow_blocked: bool = True,
) -> AdmissionOutcome:
    """Execute the single admission decision for a plan joining the board.

    Evaluates whether the candidate plan may enter the sprint backlog:
    1. Checks if already live or settled.
    2. Resolves the plan file.
    3. Executes the full plan_validate suite (ignoring any _Stage: footer).
    4. Builds the task representation via new_task_from_plan.
    5. Optionally verifies blocked state.
    """
    if queue is None and hasattr(backend, "load"):
        try:
            data = backend.load()
            live_tasks = data.get("queue", [])
            if history is None:
                history = data.get("history", [])
        except Exception:
            live_tasks = []
    else:
        live_tasks = queue if queue is not None else []

    live_ids = {t.get("id") for t in live_tasks if t.get("id")}
    settled_ids = settled_ids_from(
        backend=backend, history_file=history_file, history=history
    )

    target_stem = Path(str(target)).stem.removesuffix(".md")
    if target_stem in live_ids:
        existing = next((t for t in live_tasks if t.get("id") == target_stem), None)
        return Skipped(reason=SkipReason.ALREADY_IN_QUEUE, existing_task=existing)
    if target_stem in settled_ids:
        return Skipped(reason=SkipReason.ALREADY_SETTLED)

    plan_file = resolve_plan(target, plans_dir)
    if plan_file is None or not plan_file.is_file():
        return Refused(
            reason=RefusalReason.PLAN_NOT_FOUND,
            detail=f"No plan found for '{target}' in {plans_dir}",
        )

    plan_stem = plan_file.stem
    if plan_stem in live_ids or any(
        t.get("plan_file") == str(plan_file) for t in live_tasks
    ):
        existing = next(
            (
                t
                for t in live_tasks
                if t.get("id") == plan_stem
                or t.get("plan_file") == str(plan_file)
            ),
            None,
        )
        return Skipped(
            reason=SkipReason.ALREADY_IN_QUEUE,
            plan_file=plan_file,
            existing_task=existing,
        )
    if plan_stem in settled_ids:
        return Skipped(reason=SkipReason.ALREADY_SETTLED, plan_file=plan_file)

    unacked, record = unacked_intake_findings(
        plan_file,
        plans_dir,
        backend,
        history_file=history_file,
        queue=live_tasks,
        history=history,
    )
    if unacked:
        return Refused(
            reason=RefusalReason.VALIDATION_FAILED,
            plan_file=plan_file,
            findings=unacked,
            coverage=record,
        )

    task = plan_parser.new_task_from_plan(
        plan_file,
        live_tasks=live_tasks,
        settled_ids=settled_ids,
    )

    if not allow_blocked and task.get("state") == "blocked":
        blockers = [
            b
            for b in task.get("blocked_by", [])
            if b in live_ids
            and next(
                (
                    t
                    for t in live_tasks
                    if t.get("id") == b
                    and t.get("state") in {"merged", "abandoned"}
                ),
                None,
            )
            is None
        ]
        return Refused(
            reason=RefusalReason.BLOCKED,
            plan_file=plan_file,
            blockers=blockers,
        )

    return Admitted(task=task, plan_file=plan_file)
