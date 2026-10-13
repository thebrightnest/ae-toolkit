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


@dataclass
class BisectResult:
    culprit: str
    k: int
    output: str = ""
    runs: int = 0

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str):
            return self.culprit == other
        if isinstance(other, BisectResult):
            return (self.culprit, self.k) == (other.culprit, other.k)
        return False

    def __str__(self) -> str:
        return self.culprit


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


def _run_flush_validation(cmd_list: list[str], worktree_dir: str) -> subprocess.CompletedProcess[str]:
    """Run validation command in worktree, skipping default 'make validate' if no Makefile exists."""
    if cmd_list == ["make", "validate"] and not (Path(worktree_dir) / "Makefile").exists():
        return subprocess.CompletedProcess(
            args=cmd_list,
            returncode=0,
            stdout="No Makefile found; skipping default make validate\n",
            stderr="",
        )
    return subprocess.run(
        cmd_list,
        cwd=worktree_dir,
        capture_output=True,
        text=True,
    )


def resolve_train_base(
    repo_root: str | Path,
    branch: str,
    snapshot: str,
) -> str:
    """Find the base commit on branch (origin/branch or branch) where the staging train branched off."""
    res_origin = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--verify", f"refs/remotes/origin/{branch}"],
        capture_output=True,
        text=True,
    )
    target = f"refs/remotes/origin/{branch}" if res_origin.returncode == 0 else branch
    res_base = subprocess.run(
        ["git", "-C", str(repo_root), "merge-base", snapshot, target],
        capture_output=True,
        text=True,
    )
    if res_base.returncode == 0 and res_base.stdout.strip():
        return res_base.stdout.strip()
    return target


def get_staged_commits(
    repo_root: str | Path,
    base: str,
    snapshot: str,
) -> list[str]:
    """Return ordered commit SHAs staged between base and snapshot (c1..cn)."""
    res = subprocess.run(
        ["git", "-C", str(repo_root), "rev-list", "--reverse", f"{base}..{snapshot}"],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        return []
    return [line.strip() for line in res.stdout.splitlines() if line.strip()]


def bisect(
    repo_root: str | Path,
    branch: str,
    snapshot: str,
    *,
    validate_command: list[str] | str | None = None,
    base: str | None = None,
    snapshot_output: str | None = None,
) -> BisectResult | None:
    """Binary search over staged prefixes c1..cn on base.

    Returns the smallest failing k (culprit ck) or None when every prefix passes (flake).
    Runs at most ceil(log2 n) validations.
    """
    repo_root = Path(repo_root).resolve()
    if base is None:
        base = resolve_train_base(repo_root, branch, snapshot)

    commits = get_staged_commits(repo_root, base, snapshot)
    if not commits:
        return None

    n = len(commits)
    if validate_command is None:
        cmd_list, _ = resolve_validation_commands(repo_root=repo_root)
    elif isinstance(validate_command, str):
        cmd_list = shlex.split(validate_command)
    else:
        cmd_list = list(validate_command)

    temp_worktree = tempfile.mkdtemp(prefix="aet-train-bisect-")
    try:
        add_wt = subprocess.run(
            ["git", "-C", str(repo_root), "worktree", "add", "--detach", temp_worktree, base],
            capture_output=True,
            text=True,
        )
        if add_wt.returncode != 0:
            return None

        low = 1
        high = n
        culprit_idx: int | None = None
        culprit_output = ""
        runs = 0

        while low <= high:
            mid = (low + high) // 2
            subprocess.run(
                ["git", "-C", temp_worktree, "checkout", "-f", commits[mid - 1]],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", temp_worktree, "clean", "-fd"],
                check=True,
                capture_output=True,
            )
            proc = _run_flush_validation(cmd_list, temp_worktree)
            runs += 1

            if proc.returncode != 0:
                culprit_idx = mid
                culprit_output = (proc.stdout or "") + (proc.stderr or "")
                high = mid - 1
            else:
                low = mid + 1

        if culprit_idx is not None:
            return BisectResult(
                culprit=commits[culprit_idx - 1],
                k=culprit_idx,
                output=culprit_output,
                runs=runs,
            )
        return None
    finally:
        subprocess.run(
            ["git", "-C", str(repo_root), "worktree", "remove", "--force", temp_worktree],
            capture_output=True,
        )
        shutil.rmtree(temp_worktree, ignore_errors=True)


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
        proc = _run_flush_validation(cmd_list, temp_worktree)
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
        initial_output = (proc.stdout or "") + (proc.stderr or "")

        # 1. Deterministic prefix bisect (R-8)
        base_commit = resolve_train_base(repo_root, branch, snapshot_commit)
        bisect_res = bisect(
            repo_root,
            branch,
            snapshot_commit,
            validate_command=cmd_list,
            base=base_commit,
            snapshot_output=initial_output,
        )

        # 2. Flake path: bisect finds no failing prefix
        if bisect_res is None:
            retry_wt = tempfile.mkdtemp(prefix="aet-train-retry-")
            proc_retry = None
            try:
                add_wt = subprocess.run(
                    ["git", "-C", str(repo_root), "worktree", "add", "--detach", retry_wt, snapshot_commit],
                    capture_output=True,
                    text=True,
                )
                if add_wt.returncode != 0:
                    return FlushResult(
                        ok=False,
                        status="halt",
                        commit=snapshot_commit,
                        error=f"Could not create retry worktree: {add_wt.stderr.strip()}",
                    )
                proc_retry = _run_flush_validation(cmd_list, retry_wt)
                tree_hash = verifier.working_tree_hash(retry_wt)
            finally:
                subprocess.run(
                    ["git", "-C", str(repo_root), "worktree", "remove", "--force", retry_wt],
                    capture_output=True,
                )
                shutil.rmtree(retry_wt, ignore_errors=True)

            if proc_retry is None or proc_retry.returncode != 0:
                # Red again -> halt fail-closed
                out = (proc_retry.stdout or "") + (proc_retry.stderr or "") if proc_retry else initial_output
                return FlushResult(
                    ok=False,
                    status="halt",
                    commit=snapshot_commit,
                    output=out,
                    error=out,
                )
            # If proc_retry.returncode == 0: green! Continue to green flush logic below
        else:
            # 3. Culprit found: eject culprit and re-stack remaining tasks (R-8)
            culprit_commit = bisect_res.culprit
            culprit_output = bisect_res.output or initial_output
            staged_commits = get_staged_commits(repo_root, base_commit, snapshot_commit)
            k = bisect_res.k

            with integration_lock(str(repo_root)):
                queue = backend.load().get("queue", []) if backend is not None else []
                commit_to_task: dict[str, dict[str, Any]] = {}
                pos_to_task: dict[int, dict[str, Any]] = {}
                for t in queue:
                    tr = t.get("train")
                    if isinstance(tr, dict) and tr.get("branch", branch) == branch:
                        sc = tr.get("staged_commit")
                        if sc:
                            commit_to_task[sc] = t
                        p = tr.get("position")
                        if isinstance(p, int):
                            pos_to_task[p] = t

                culprit_task = commit_to_task.get(culprit_commit)
                if culprit_task is None and 1 <= k <= len(staged_commits):
                    culprit_task = pos_to_task.get(k)

                if culprit_task is not None:
                    culprit_task.pop("train", None)
                    culprit_task["state"] = "awaiting_merge"
                    culprit_task["conflict_diagnostics"] = {
                        "reason": "batch_validation",
                        "conflicting_files": [],
                        "stderr_tail": culprit_output[-2000:],
                        "at": telemetry.iso_now(),
                    }

                current_tip = staged_commits[k - 2] if k > 1 else base_commit

                restack_wt = tempfile.mkdtemp(prefix="aet-train-restack-")
                try:
                    subprocess.run(
                        ["git", "-C", str(repo_root), "worktree", "add", "--detach", restack_wt, current_tip],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    for i in range(k, len(staged_commits)):
                        ci = staged_commits[i]
                        ti = commit_to_task.get(ci)
                        if ti is None:
                            ti = pos_to_task.get(i + 1)
                        cp = subprocess.run(
                            ["git", "-C", restack_wt, "cherry-pick", ci],
                            capture_output=True,
                            text=True,
                        )
                        if cp.returncode == 0:
                            new_sha = subprocess.run(
                                ["git", "-C", restack_wt, "rev-parse", "HEAD"],
                                capture_output=True,
                                text=True,
                                check=True,
                            ).stdout.strip()
                            current_tip = new_sha
                            if ti is not None and "train" in ti and isinstance(ti["train"], dict):
                                ti["train"]["staged_commit"] = new_sha
                        else:
                            conflicts_run = subprocess.run(
                                ["git", "-C", restack_wt, "diff", "--name-only", "--diff-filter=U"],
                                capture_output=True,
                                text=True,
                            )
                            conflicts = [f.strip() for f in conflicts_run.stdout.splitlines() if f.strip()]
                            subprocess.run(
                                ["git", "-C", restack_wt, "cherry-pick", "--abort"],
                                capture_output=True,
                            )
                            if ti is not None:
                                ti.pop("train", None)
                                ti["state"] = "awaiting_merge"
                                tail = (cp.stderr if cp.stderr.strip() else cp.stdout or "").strip()[-500:]
                                ti["conflict_diagnostics"] = {
                                    "reason": "restack_conflict",
                                    "conflicting_files": conflicts,
                                    "stderr_tail": tail,
                                    "at": telemetry.iso_now(),
                                }

                    curr_ref_res = subprocess.run(
                        ["git", "-C", str(repo_root), "rev-parse", "--verify", ref],
                        capture_output=True,
                        text=True,
                    )
                    current_ref_tip = curr_ref_res.stdout.strip() if curr_ref_res.returncode == 0 else snapshot_commit
                    if current_ref_tip != snapshot_commit:
                        later_commits = get_staged_commits(repo_root, snapshot_commit, current_ref_tip)
                        for c_later in later_commits:
                            t_later = commit_to_task.get(c_later)
                            cp = subprocess.run(
                                ["git", "-C", restack_wt, "cherry-pick", c_later],
                                capture_output=True,
                                text=True,
                            )
                            if cp.returncode == 0:
                                new_sha = subprocess.run(
                                    ["git", "-C", restack_wt, "rev-parse", "HEAD"],
                                    capture_output=True,
                                    text=True,
                                    check=True,
                                ).stdout.strip()
                                current_tip = new_sha
                                if t_later is not None and "train" in t_later and isinstance(t_later["train"], dict):
                                    t_later["train"]["staged_commit"] = new_sha
                            else:
                                conflicts_run = subprocess.run(
                                    ["git", "-C", restack_wt, "diff", "--name-only", "--diff-filter=U"],
                                    capture_output=True,
                                    text=True,
                                )
                                conflicts = [f.strip() for f in conflicts_run.stdout.splitlines() if f.strip()]
                                subprocess.run(
                                    ["git", "-C", restack_wt, "cherry-pick", "--abort"],
                                    capture_output=True,
                                )
                                if t_later is not None:
                                    t_later.pop("train", None)
                                    t_later["state"] = "awaiting_merge"
                                    tail = (cp.stderr if cp.stderr.strip() else cp.stdout or "").strip()[-500:]
                                    t_later["conflict_diagnostics"] = {
                                        "reason": "restack_conflict",
                                        "conflicting_files": conflicts,
                                        "stderr_tail": tail,
                                        "at": telemetry.iso_now(),
                                    }
                finally:
                    subprocess.run(
                        ["git", "-C", str(repo_root), "worktree", "remove", "--force", restack_wt],
                        capture_output=True,
                    )
                    shutil.rmtree(restack_wt, ignore_errors=True)

                if current_tip == base_commit:
                    subprocess.run(
                        ["git", "-C", str(repo_root), "update-ref", "-d", ref, current_ref_tip],
                        capture_output=True,
                    )
                    _save_task_record(backend, queue)
                    return FlushResult(ok=True, status="empty", tasks_flushed=[])

                chain = get_staged_commits(repo_root, base_commit, current_tip)
                chain_order = {sha: idx for idx, sha in enumerate(chain, start=1)}
                for t in queue:
                    tr = t.get("train")
                    if isinstance(tr, dict) and tr.get("branch", branch) == branch:
                        sc = tr.get("staged_commit")
                        if sc in chain_order:
                            tr["position"] = chain_order[sc]

                update_train_ref(repo_root, branch, current_tip, old_commit=current_ref_tip)
                _save_task_record(backend, queue)

            return flush(
                repo_root,
                branch,
                backend=backend,
                config=config,
                validate_command=validate_command,
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
