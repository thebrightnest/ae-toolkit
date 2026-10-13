"""Merge Train: staging ref management and batch flush (ADR-079, R-3, R-5, R-6, R-7).

Under the merge train:
1. `integrate()` squash-merges tasks onto a local staging ref
   `refs/aet/train/<branch>` with compare-and-swap under `integration_lock`.
2. A single `flush()` validates a snapshot of the staging tip in a temporary
   worktree outside the lock.
3. Green flush fast-forwards the integration branch to the snapshot, pushes,
   transitions snapshot tasks `awaiting_merge → merged`, and records a batch verdict.
4. Red flush halts integration fail-closed (ADR-029).
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from aet import evidence, telemetry, verifier
from aet.backends import create_backend, resolve_validation_commands
from aet.backends.factory import DEFAULT_CONFIG_PATH
from aet.integration_lock import integration_lock
from aet.worktree import push_branch


@dataclass
class FlushResult:
    ok: bool
    status: Literal["green", "red", "empty", "halt"]
    tasks_flushed: list[str] = field(default_factory=list)
    commit: str | None = None
    output: str = ""
    error: str = ""

    def __bool__(self) -> bool:
        return self.ok


def train_ref(branch: str) -> str:
    """Return the git ref path for the given branch's staging ref."""
    return f"refs/aet/train/{branch}"


def train_tip(repo_root: str | Path, branch: str) -> str:
    """Return the current tip to rebase onto: staging ref if present, else origin/branch."""
    ref = train_ref(branch)
    res = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--verify", ref],
        capture_output=True,
    )
    if res.returncode == 0:
        return ref

    res_origin = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--verify", f"refs/remotes/origin/{branch}"],
        capture_output=True,
    )
    if res_origin.returncode == 0:
        return f"origin/{branch}"

    return branch


def update_train_ref(
    repo_root: str | Path,
    branch: str,
    new_commit: str,
    old_commit: str | None = None,
) -> bool:
    """Atomically update the staging ref with compare-and-swap (CAS)."""
    ref = train_ref(branch)
    cmd = ["git", "-C", str(repo_root), "update-ref", ref, new_commit]
    if old_commit is not None:
        cmd.append(old_commit)
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.returncode == 0


def is_ancestor_or_equal(repo_root: str | Path, commit_a: str, commit_b: str) -> bool:
    """True if commit_a is an ancestor of or equal to commit_b."""
    if commit_a == commit_b:
        return True
    res = subprocess.run(
        ["git", "-C", str(repo_root), "merge-base", "--is-ancestor", commit_a, commit_b],
        capture_output=True,
    )
    return res.returncode == 0


def rebuild_from_records(
    repo_root: str | Path,
    branch: str,
    *,
    backend: Any = None,
    queue: list[dict[str, Any]] | None = None,
) -> str | None:
    """Re-derive refs/aet/train/<branch> from task train markers if lost."""
    if queue is None:
        if backend is not None:
            queue = backend.load().get("queue", [])
        else:
            queue_file = os.path.join(str(repo_root), ".agents", "aet-queue")
            if os.path.exists(queue_file):
                try:
                    backend = create_backend(
                        config_path=os.path.join(str(repo_root), DEFAULT_CONFIG_PATH),
                        queue_file=queue_file,
                        history_file=os.path.join(str(repo_root), ".agents", "work-history.jsonl"),
                    )
                    queue = backend.load().get("queue", [])
                except Exception:
                    queue = []
            else:
                queue = []

    matching = [
        t
        for t in queue
        if t.get("train")
        and isinstance(t["train"], dict)
        and t["train"].get("branch", branch) == branch
        and t["train"].get("staged_commit")
    ]
    if not matching:
        return None

    matching.sort(key=lambda t: t["train"].get("position", 0))
    latest = matching[-1]
    staged_commit = latest["train"]["staged_commit"]
    subprocess.run(
        ["git", "-C", str(repo_root), "update-ref", train_ref(branch), staged_commit],
        check=True,
        capture_output=True,
    )
    return staged_commit


def _save_task_record(backend: Any, queue: list[dict[str, Any]]) -> None:
    if backend is None:
        return
    backend.save(queue)
    try:
        backend.push()
    except Exception:
        pass


def flush(
    repo_root: str | Path,
    branch: str,
    *,
    backend: Any = None,
    config: dict[str, Any] | None = None,
    validate_command: list[str] | str | None = None,
) -> FlushResult:
    """Flush the merge train for branch.

    1. Under integration_lock: snapshot the staging tip and staged task list.
    2. Outside the lock: run validation command in a temporary worktree.
    3. On green: re-take lock, fast-forward branch, push, mark snapshot tasks merged,
       record batch verdict.
    4. On red: leave tasks awaiting_merge, halt integration fail-closed.
    """
    repo_root = Path(repo_root).resolve()
    ref = train_ref(branch)
    queue_file = str(repo_root / ".agents" / "aet-queue")

    if backend is None and (repo_root / ".agents" / "aet-queue").exists():
        try:
            backend = create_backend(
                config_path=str(repo_root / DEFAULT_CONFIG_PATH),
                queue_file=queue_file,
                history_file=str(repo_root / ".agents" / "work-history.jsonl"),
            )
        except Exception:
            backend = None

    snapshot_commit: str = ""
    snapshot_task_ids: list[str] = []

    with integration_lock(str(repo_root)):
        res = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--verify", ref],
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            return FlushResult(ok=True, status="empty", tasks_flushed=[])
        snapshot_commit = res.stdout.strip()

        if backend is not None:
            try:
                queue = backend.load().get("queue", [])
                snapshot_tasks = [
                    t
                    for t in queue
                    if t.get("train")
                    and isinstance(t["train"], dict)
                    and t["train"].get("branch", branch) == branch
                    and is_ancestor_or_equal(
                        repo_root,
                        t["train"].get("staged_commit", ""),
                        snapshot_commit,
                    )
                ]
                snapshot_task_ids = [t["id"] for t in snapshot_tasks]
            except Exception:
                snapshot_task_ids = []

    # Outside the lock: run validation suite
    if validate_command is None:
        cmd_list, _ = resolve_validation_commands(repo_root=repo_root)
    elif isinstance(validate_command, str):
        cmd_list = shlex.split(validate_command)
    else:
        cmd_list = list(validate_command)

    temp_worktree = tempfile.mkdtemp(prefix="aet-train-flush-")
    tree_hash = ""
    try:
        add_wt = subprocess.run(
            ["git", "-C", str(repo_root), "worktree", "add", "--detach", temp_worktree, snapshot_commit],
            capture_output=True,
            text=True,
        )
        if add_wt.returncode != 0:
            return FlushResult(
                ok=False,
                status="halt",
                commit=snapshot_commit,
                error=f"Could not create temporary worktree at {snapshot_commit}: {add_wt.stderr.strip()}",
            )

        tree_hash = verifier.working_tree_hash(temp_worktree)
        proc = subprocess.run(
            cmd_list,
            cwd=temp_worktree,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        return FlushResult(
            ok=False,
            status="halt",
            commit=snapshot_commit,
            error=f"Flush validation error: {exc}",
        )
    finally:
        subprocess.run(
            ["git", "-C", str(repo_root), "worktree", "remove", "--force", temp_worktree],
            capture_output=True,
        )
        shutil.rmtree(temp_worktree, ignore_errors=True)

    if proc.returncode != 0:
        output = (proc.stdout or "") + (proc.stderr or "")
        return FlushResult(
            ok=False,
            status="red",
            commit=snapshot_commit,
            output=output,
            error=output,
        )

    # Green flush! Re-acquire lock to commit changes
    with integration_lock(str(repo_root)):
        head_proc = subprocess.run(
            ["git", "-C", str(repo_root), "symbolic-ref", "--short", "HEAD"],
            capture_output=True,
            text=True,
        )
        if head_proc.returncode == 0 and head_proc.stdout.strip() == branch:
            subprocess.run(
                ["git", "-C", str(repo_root), "reset", "--hard", snapshot_commit],
                capture_output=True,
                check=True,
            )
        else:
            subprocess.run(
                ["git", "-C", str(repo_root), "update-ref", f"refs/heads/{branch}", snapshot_commit],
                capture_output=True,
                check=True,
            )

        ok_push, err_push = push_branch(str(repo_root), branch)
        if not ok_push:
            return FlushResult(
                ok=False,
                status="halt",
                commit=snapshot_commit,
                error=f"Push of {branch} failed: {err_push}",
            )

        subprocess.run(
            ["git", "-C", str(repo_root), "update-ref", f"refs/remotes/origin/{branch}", snapshot_commit],
            capture_output=True,
        )

        curr_res = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--verify", ref],
            capture_output=True,
            text=True,
        )
        if curr_res.returncode == 0:
            curr_tip = curr_res.stdout.strip()
            if curr_tip == snapshot_commit:
                subprocess.run(
                    ["git", "-C", str(repo_root), "update-ref", "-d", ref, snapshot_commit],
                    capture_output=True,
                )

        if backend is not None:
            queue = backend.load().get("queue", [])
            for t in queue:
                if t.get("id") in snapshot_task_ids:
                    staged_commit = t.get("train", {}).get("staged_commit") or snapshot_commit
                    t["merge_commit"] = staged_commit
                    t["merge_strategy"] = "squash"
                    t.pop("train", None)
            _save_task_record(backend, queue)

            aet_state_bin = str(Path(__file__).resolve().parent / "cli" / "aet_state.py")
            for tid in snapshot_task_ids:
                subprocess.run(
                    [
                        sys.executable,
                        aet_state_bin,
                        "transition",
                        tid,
                        "awaiting_merge",
                        "merged",
                        queue_file,
                    ],
                    capture_output=True,
                )

        batch_record = {
            "kind": "batch",
            "branch": branch,
            "verdict": "pass",
            "summary": f"Merge train flush passed ({len(snapshot_task_ids)} tasks)",
            "generated_at": telemetry.iso_now(),
            "tree_hash": tree_hash,
            "task_ids": snapshot_task_ids,
        }
        evidence.write_verdict(
            task_id=branch,
            kind="batch",
            record=batch_record,
            project_slug=telemetry.derive_project_slug(repo_root),
            worktree_dir=repo_root,
        )

    return FlushResult(
        ok=True,
        status="green",
        tasks_flushed=snapshot_task_ids,
        commit=snapshot_commit,
    )
