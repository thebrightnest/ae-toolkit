"""aet-work init-queue — Rebuild the work queue from the existing sprint record.

Reads the plans that are already represented in the queue, validates the
frontmatter contract, rebuilds dependency facts, preserves terminal metadata
from the settled history log and git ancestry, and writes a fresh
`.agents/work-queue.json`. It does **not** auto-add new plans or derive
actionable status.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import typer

_SCRIPT_DIR = Path(__file__).resolve().parent
from aet import plan_validate  # noqa: E402
from aet.backends.factory import create_backend  # noqa: E402
from aet.plan_parser import (  # noqa: E402
    most_recent_prd,
    new_task_from_plan,
)
from aet.queue import (  # noqa: E402
    HISTORY_TERMINAL_STATES,
    QueueIntegrityError,
    append_history_record,
    lease_guard,
)


def git_merge_commit_for(task_id: str, repo_root: str | Path | None = None) -> str | None:
    """Return the latest commit on origin/main whose message mentions ``task_id``.

    This is a best-effort reconciliation for squash-merged work: a task whose
    id appears in a commit on origin/main is treated as merged with that SHA.
    """
    cmd = ["git"]
    if repo_root:
        cmd.extend(["-C", str(repo_root)])
    cmd.extend(["log", "origin/main", "--format=%H", "--grep", task_id, "-n", "1"])
    result = subprocess.run(cmd, capture_output=True, text=True)
    sha = result.stdout.strip()
    return sha or None


def plan_footer_stage(plan_file: str | Path) -> str | None:
    """Read the human-authored footer stage from a plan file, if present.

    Returns the raw stage string (e.g. ``merged``, ``awaiting_merge``,
    ``implemented``) or ``None`` when no footer stage is found.
    """
    path = Path(plan_file)
    if not path.is_file():
        return None
    # Footer stage lines look like: _Stage: plan-approved_ or *Stage: merged*
    for line in path.read_text(errors="ignore").splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if lowered.startswith("_stage:") or lowered.startswith("*stage:"):
            # Extract value after the colon, trimming markdown emphasis.
            value = stripped.split(":", 1)[1].strip()
            value = value.strip("_").strip("*").strip()
            return value or None
    return None


def _is_settled_from_authority(
    plan_file: str | Path,
    history_by_id: dict[str, dict],
    repo_root: str | Path | None = None,
) -> bool:
    """Return True when a plan is settled from the ledger or git ancestry.

    Settled-ness is derived from the append-only settled history, a merge
    commit mentioning the task id on ``origin/main``, or a terminal footer
    stage. It is never derived from plan frontmatter ``status``.
    """
    path = Path(plan_file)
    tid = path.stem

    hist = history_by_id.get(tid)
    if hist and hist.get("state") in HISTORY_TERMINAL_STATES:
        return True

    if git_merge_commit_for(tid, repo_root=repo_root):
        return True

    footer = plan_footer_stage(path)
    if footer in ("merged", "abandoned"):
        return True

    return False


def reconcile_terminal_state(
    task: dict,
    history_by_id: dict[str, dict],
    plan_file: str | Path | None = None,
    repo_root: str | Path | None = None,
) -> bool:
    """If a task is terminal in history, git, or its plan footer, mark it terminal.

    Returns True when the task should be removed from the live queue.
    """
    tid = task.get("id")
    if not tid:
        return False

    # Already terminal in the live record.
    if task.get("state") in HISTORY_TERMINAL_STATES:
        return True

    # Terminal in settled history.
    hist = history_by_id.get(tid)
    if hist and hist.get("state") in HISTORY_TERMINAL_STATES:
        task["state"] = hist["state"]
        task["merge_commit"] = hist.get("merge_commit")
        task["merged_at"] = hist.get("merged_at")
        task["completed_at"] = hist.get("completed_at")
        task["merge_strategy"] = hist.get("merge_strategy")
        return True

    # Terminal in git history on origin/main.
    merge_commit = git_merge_commit_for(tid, repo_root=repo_root)
    if merge_commit:
        task["state"] = "merged"
        task["merge_commit"] = merge_commit
        task["merged_at"] = datetime.now().isoformat()
        return True

    # Reconcile against the human-authored plan footer stage.
    footer = plan_footer_stage(plan_file) if plan_file else None
    if footer in ("merged", "abandoned"):
        task["state"] = footer
        return True

    return False


def preserve_task_metadata(
    existing: dict,
    fresh: dict,
    history_by_id: dict[str, dict],
    repo_root: str | Path | None = None,
) -> dict:
    """Preserve terminal state and metadata from an existing queue entry.

    Terminal states (merged, abandoned) and terminal history/git states are
    preserved so completed work is not resurrected when the queue is rebuilt.
    Non-terminal stored states are reset based on the fresh frontmatter
    blockers. This matches ``init-queue``'s rebuild-from-plans semantics.
    """
    state = existing.get("state")
    task_id = existing.get("id") or fresh.get("id")

    # Terminal in the live record, settled history, or git -> keep terminal.
    hist = history_by_id.get(task_id)
    if state in ("merged", "abandoned"):
        pass
    elif hist and hist.get("state") in ("merged", "abandoned"):
        state = hist["state"]
        fresh["merge_commit"] = hist.get("merge_commit")
        fresh["merged_at"] = hist.get("merged_at")
        fresh["completed_at"] = hist.get("completed_at")
        fresh["merge_strategy"] = hist.get("merge_strategy")
    else:
        # Reconcile against git history on origin/main.
        merge_commit = git_merge_commit_for(task_id, repo_root=repo_root)
        if merge_commit:
            state = "merged"
            fresh["merge_commit"] = merge_commit
            fresh["merged_at"] = datetime.now().isoformat()
        else:
            # init-queue rebuilds the queue from plan frontmatter; non-terminal
            # stored states follow blockers.
            blockers = fresh.get("blocked_by", [])
            pending = len(blockers)
            state = fresh.get("state", "ready")
            fresh["pending_blockers"] = pending

    fresh["state"] = state
    for key in (
        "branch",
        "worktree",
        "merge_strategy",
        "completed_at",
        "merged_at",
        "failed_stage",
        "history",
    ):
        if key in existing:
            fresh[key] = existing[key]
    # merge_commit may come from history/git above, so keep existing only if no
    # reconciliation value was set.
    if "merge_commit" not in fresh and "merge_commit" in existing:
        fresh["merge_commit"] = existing["merge_commit"]
    return fresh


def build_blocks(queue: list[dict]) -> None:
    """Recompute ``blocks`` as the inverse of ``blocked_by`` for the whole queue."""
    task_by_id = {t["id"]: t for t in queue if t.get("id")}
    for task in queue:
        task["blocks"] = []
    for task in queue:
        for blocker in task.get("blocked_by", []):
            if blocker in task_by_id:
                task_by_id[blocker].setdefault("blocks", []).append(task["id"])


def _run(
    queue_file: str,
    history_file: str,
    plans_dir: Path,
    prds_dir: Path,
    config: str,
    force: bool,
) -> int:
    backend = create_backend(
        config_path=config,
        queue_file=queue_file,
        history_file=history_file,
    )

    # Ensure the append-only history log exists so commands recreate missing
    # files on demand without waiting for a terminal record to be appended.
    os.makedirs(os.path.dirname(history_file) or ".", exist_ok=True)
    if not os.path.exists(history_file):
        open(history_file, "a", encoding="utf-8").close()

    try:
        data = backend.load()
    except QueueIntegrityError as exc:
        # Mutating command: fail closed with a one-line refusal, not a
        # traceback. The error message names the recovery path (ADR-024).
        print(f"⛔ {exc}", file=sys.stderr)
        return 1
    queue = data["queue"]
    history = data["history"]

    existing_by_file = {t.get("plan_file"): t for t in queue if t.get("plan_file")}
    history_by_id = {t.get("id"): t for t in history if t.get("id")}

    repo_root = Path(
        subprocess.run(
            ["git", "-C", str(plans_dir), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        or str(plans_dir.parent.parent)
    )

    # Queue membership is the explicit sprint-add record. Rebuild only the
    # plans that are already represented in the queue, skip plans that are
    # settled according to the ledger or git ancestry, and validate the
    # remaining included set fail-closed.
    included_plan_files: list[Path] = []
    skipped_settled = 0
    for pf_str, existing in existing_by_file.items():
        pf = Path(pf_str)
        if not pf.is_file():
            continue
        if _is_settled_from_authority(pf, history_by_id, repo_root=repo_root):
            skipped_settled += 1
            continue
        included_plan_files.append(pf)

    # Fail closed for invalid plans in the included set.
    findings = plan_validate.validate(included_plan_files, repo_root=repo_root)
    plan_texts = {pf: pf.read_text(errors="ignore") for pf in included_plan_files}
    findings = plan_validate.apply_acks(findings, plan_texts)
    unacked = [f for f in findings if not f.acked]
    if unacked:
        for finding in unacked:
            print(
                f"❌ {finding.plan.name}: {finding.check_id}: {finding.message}",
                file=sys.stderr,
            )
        return 1

    preserved = 0
    added = 0
    reconciled_terminal = 0
    final_queue: list[dict] = []
    seen_files = set()

    for pf in included_plan_files:
        pf_str = str(pf)
        existing = existing_by_file[pf_str]
        fresh = new_task_from_plan(pf)
        task = preserve_task_metadata(existing, fresh, history_by_id, repo_root=repo_root)
        preserved += 1

        if reconcile_terminal_state(task, history_by_id, pf, repo_root=repo_root):
            tid = task.get("id")
            if tid not in history_by_id:
                append_history_record(history_file, task)
            reconciled_terminal += 1
            continue

        final_queue.append(task)
        seen_files.add(pf_str)

    # Retain any queue entries whose plan file is temporarily missing rather
    # than silently dropping them; drift is reported by ``status`` / ``sync``.
    for task in queue:
        pf = task.get("plan_file")
        tid = task.get("id")
        if pf and pf not in seen_files:
            if reconcile_terminal_state(task, history_by_id, pf, repo_root=repo_root):
                if tid not in history_by_id:
                    append_history_record(history_file, task)
                reconciled_terminal += 1
                continue
            final_queue.append(task)
            seen_files.add(pf)

    build_blocks(final_queue)

    source_prd = most_recent_prd(prds_dir)
    wrapper: dict = {"queue_updated_at": datetime.now().isoformat()}
    if source_prd is not None:
        wrapper["source_prd"] = str(source_prd)

    if not lease_guard(queue_file, force=force):
        backend.close()
        return 1

    backend.save(final_queue, wrapper=wrapper)

    print(
        f"✅ init-queue complete: {added} new tasks added, {preserved} existing tasks preserved, "
        f"{skipped_settled} settled tasks skipped, "
        f"{reconciled_terminal} reconciled as terminal, {len(final_queue)} active tasks."
    )
    backend.close()
    return 0


app = typer.Typer(invoke_without_command=True)


@app.callback()
def init_queue(
    queue_file: str = typer.Option(
        ".agents/work-queue.json",
        "--queue-file",
        help="Path to work-queue.json",
    ),
    history_file: str = typer.Option(
        ".agents/work-history.jsonl",
        "--history-file",
        help="Path to work-history.jsonl",
    ),
    plans_dir: Path = typer.Option(
        Path("docs/plans"),
        "--plans-dir",
        help="Directory containing atomic plan markdown files",
    ),
    prds_dir: Path = typer.Option(
        Path("docs/prds"),
        "--prds-dir",
        help="Directory containing PRD markdown files",
    ),
    config: str = typer.Option(
        ".agents/aet-config.json",
        "--config",
        help="Path to AET backend configuration",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Override a live run lease and mutate the queue anyway (with a warning).",
    ),
) -> None:
    """Rebuild the work queue from docs/plans."""
    rc = _run(queue_file, history_file, plans_dir, prds_dir, config, force)
    raise typer.Exit(rc)


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    try:
        return app(argv, standalone_mode=False)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0


if __name__ == "__main__":
    app()
