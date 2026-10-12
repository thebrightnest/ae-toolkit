"""Unified task integration into the integration target (ADR-045, R-3, R-4).

Extracts the single-PR / task merge path into an atomic, lock-managed
operation that:
1. Runs pre-integration checks *before* taking the lock (R-2, R-3).
2. Acquires ``integration_lock``.
3. Rebases onto the latest integration branch tip.
4. Enforces release-guard and monolithic-commit guards under lock (R-3).
5. Runs post-rebase validation and checks required evidence gates (R-18, R-22).
6. Detached squash-merges into the integration target, updates refs, pushes.
7. Cleans up worktree and task branch under lock.
8. Records the merge commit and transitions state to ``merged``.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from aet import gate, plan_parser, telemetry, validation
from aet.backends import create_backend
from aet.backends.factory import DEFAULT_CONFIG_PATH, resolve_config, resolve_integration_mode
from aet.branch_ref import resolve_integration_branch_for_task
from aet.integration_lock import IntegrationFailureError, integration_lock
from aet.queue import current_state, queue_lock
from aet.worktree import delete_local_branch, push_branch, run_git_plain


@dataclass
class IntegrateResult:
    status: Literal["merged", "staged_conflict", "guard_refused"]
    detail: Any = None

    @property
    def ok(self) -> bool:
        return self.status == "merged"

    @property
    def message(self) -> str:
        if isinstance(self.detail, str):
            return self.detail
        if isinstance(self.detail, dict):
            return (
                self.detail.get("stderr_tail")
                or self.detail.get("reason")
                or str(self.detail)
            )
        return ""

    def __bool__(self) -> bool:
        return self.ok

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.status == other
        if isinstance(other, IntegrateResult):
            return self.status == other.status and self.detail == other.detail
        return False


def plan_task_count(spec: dict[str, Any]) -> int:
    """Count checked/unchecked tasks from the task record."""
    count = 0
    for item in spec.get("tasks", []):
        stripped = item.strip()
        if stripped.startswith("- [ ]") or stripped.startswith("- [x]"):
            count += 1
    return count


def commit_count(
    pr_base: str,
    feature_branch: str | None = None,
    workspace: Path | str | None = None,
) -> int:
    """Return the number of commits between pr_base and feature_branch."""
    target_ref = feature_branch or "HEAD"
    git_args = ["-C", str(workspace)] if workspace else []
    result = subprocess.run(
        ["git", *git_args, "rev-list", "--count", f"{pr_base}..{target_ref}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return 0
    try:
        return int(result.stdout.strip())
    except ValueError:
        return 0


def commit_subjects(
    pr_base: str,
    feature_branch: str | None = None,
    workspace: Path | str | None = None,
) -> list[str]:
    """Return commit subjects in the pr_base..feature_branch range."""
    target_ref = feature_branch or "HEAD"
    git_args = ["-C", str(workspace)] if workspace else []
    result = subprocess.run(
        ["git", *git_args, "log", f"{pr_base}..{target_ref}", "--pretty=format:%s"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def check_release_guard(
    pr_base: str,
    feature_branch: str | None = None,
    workspace: Path | str | None = None,
) -> str | None:
    """Block ``chore(release)`` commits and VERSION changes on feature branches."""
    for subject in commit_subjects(pr_base, feature_branch=feature_branch, workspace=workspace):
        if re.match(r"^chore\(release\)", subject):
            return f"Release guard: commit '{subject}' is a chore(release) on a feature branch."
    target_ref = feature_branch or "HEAD"
    git_args = ["-C", str(workspace)] if workspace else []
    diff = subprocess.run(
        ["git", *git_args, "diff", f"{pr_base}..{target_ref}", "--name-only"],
        capture_output=True,
        text=True,
    )
    if diff.returncode == 0:
        for line in diff.stdout.splitlines():
            if line.strip() == "VERSION":
                return "Release guard: VERSION file changed on a feature branch."
    return None


def is_monolithic_commit(
    pr_base: str,
    spec: dict[str, Any],
    feature_branch: str | None = None,
    workspace: Path | str | None = None,
) -> bool:
    """True when one commit covers the whole range while the plan has >1 task."""
    count = commit_count(pr_base, feature_branch=feature_branch, workspace=workspace)
    return count == 1 and plan_task_count(spec) > 1


def _validate_after_rebase(
    worktree_dir: str,
    task_id: str = "",
    repo_root: str = "",
) -> tuple[bool, str]:
    """Re-run task validation in the rebased worktree.

    Returns ``(True, "")`` on success, ``(False, output)`` on failure.
    Uses ``pre_integration_check`` so an unmoved target yields SKIP.
    """
    check_result = validation.pre_integration_check(
        task_id=task_id,
        worktree_dir=worktree_dir,
        repo_root=repo_root or None,
    )
    if not check_result.ok:
        return False, check_result.output
    return True, ""


def _task_in_queue(backend: Any, task_id: str) -> bool:
    if backend is None:
        return False
    try:
        data = backend.load()
        return any(t.get("id") == task_id for t in data.get("queue", []))
    except Exception:
        return False


def _save_task_record(backend: Any, queue: list[dict[str, Any]]) -> None:
    backend.save(queue)
    try:
        replicated = backend.push()
    except Exception as exc:  # noqa: BLE001
        replicated = False
        print(f"   ⚠️  Could not replicate the task record: {exc}")
    if replicated is False:
        print(
            "   ⚠️  Task record saved locally but not pushed; the next "
            "`aet state` fetch will discard it."
        )


def _stage_task_conflict(
    repo_root: str,
    task_id: str,
    queue_file: str,
    backend: Any,
    diag: dict[str, Any],
) -> None:
    """Stage a task in awaiting_merge due to conflict and record diagnostic metadata (R-7)."""
    if backend is not None and _task_in_queue(backend, task_id):
        aet_state_bin = str(Path(__file__).resolve().parent / "cli" / "aet_state.py")
        queue = backend.load()["queue"]
        t = next((item for item in queue if item.get("id") == task_id), None)
        curr = current_state(t) if t else "in_progress"
        if curr != "awaiting_merge":
            res = subprocess.run(
                [
                    sys.executable,
                    aet_state_bin,
                    "transition",
                    task_id,
                    curr,
                    "awaiting_merge",
                    queue_file,
                ],
                capture_output=True,
                text=True,
            )
            if res.returncode != 0:
                print(
                    f"   ⚠️  Could not transition {task_id} to awaiting_merge: {res.stderr.strip()}"
                )
        with queue_lock(queue_file):
            if hasattr(backend, "fetch"):
                try:
                    backend.fetch()
                except Exception:
                    pass
            data = backend.load()
            q = data["queue"]
            for target in q:
                if target.get("id") == task_id:
                    target["conflict_diagnostics"] = diag
                    break
            _save_task_record(backend, q)


def integrate(
    repo_root: str,
    task: dict[str, Any] | str | None = None,
    worktree_dir: str | None = None,
    *,
    backend: Any = None,
    config: dict[str, Any] | None = None,
    integration_mode: str | None = None,
    integration_branch: str | None = None,
    plan_file: str | None = None,
    plan_data: dict[str, Any] | None = None,
    task_id: str | None = None,
) -> IntegrateResult:
    """Serialize, rebase, re-validate, squash-merge, push, and clean up.

    Integration (rebase onto current tip -> guards -> re-validate -> detached squash-merge)
    is executed inside the task worktree under the local advisory integration lock
    without checking out the integration branch in repo_root (ADR-045, R-18).
    Pre-integration checks run before taking the lock (R-2, R-3).
    A rebase conflict, guard refusal, or post-rebase validation failure stages
    the task in awaiting_merge with conflict diagnostics (R-7).

    Also transitions the queued task to ``merged`` when a queue file exists.
    Returns ``IntegrateResult``.
    """
    if task is None:
        if task_id is None:
            raise ValueError("integrate requires either task or task_id")
        task = task_id
    if worktree_dir is None:
        raise ValueError("integrate requires worktree_dir")
    resolved_task_id = task["id"] if isinstance(task, dict) else str(task)
    task_id = resolved_task_id
    task_dict = task if isinstance(task, dict) else {"id": task_id}
    queue_file = os.path.join(repo_root, ".agents", "aet-queue")

    if backend is None:
        try:
            backend = create_backend(
                config_path=os.path.join(repo_root, DEFAULT_CONFIG_PATH),
                queue_file=queue_file,
                history_file=os.path.join(repo_root, ".agents", "work-history.jsonl"),
            )
        except Exception:
            backend = None

    if backend is not None and not task_dict.get("branch"):
        try:
            q_tasks = backend.load().get("queue", [])
            matched = next((t for t in q_tasks if t.get("id") == task_id), None)
            if matched and matched.get("branch"):
                task_dict["branch"] = matched["branch"]
        except Exception:
            pass

    if config is None:
        config = resolve_config(DEFAULT_CONFIG_PATH, repo_root=repo_root)
    if integration_mode is None:
        integration_mode = os.environ.get("AET_INTEGRATION_MODE") or resolve_integration_mode(
            DEFAULT_CONFIG_PATH, repo_root=repo_root
        )
    if integration_branch is None:
        integration_branch = resolve_integration_branch_for_task(
            repo_root, config, task_dict, integration_mode, backend=backend
        ).ref

    # Resolve spec for guards and gate
    _plan_path = (
        Path(plan_file)
        if plan_file
        else Path(worktree_dir) / "docs" / "plans" / f"{task_id}.md"
    )
    if not _plan_path.exists() and repo_root:
        _candidate = Path(repo_root) / "docs" / "plans" / f"{task_id}.md"
        if _candidate.exists():
            _plan_path = _candidate

    _plan_fm = plan_data or (
        plan_parser.parse_frontmatter(_plan_path)
        if _plan_path.exists()
        else (task_dict.get("spec") or {})
    )

    spec: dict[str, Any] = {}
    if _plan_path.exists():
        spec = plan_parser.extract_plan_spec(_plan_path) or {}
    if not spec:
        spec = task_dict.get("spec") or {}
    if backend is not None:
        try:
            q_tasks = backend.load().get("queue", [])
            matched = next((t for t in q_tasks if t.get("id") == task_id), None)
            if matched and matched.get("spec"):
                if not spec:
                    spec = matched.get("spec") or {}
                elif "tasks" not in spec and "tasks" in matched["spec"]:
                    spec["tasks"] = matched["spec"]["tasks"]
        except Exception:
            pass

    # 1. Pre-integration check on the task worktree BEFORE taking integration_lock (R-2, R-3)
    pre_check = validation.pre_integration_check(
        task_id=task_id,
        worktree_dir=worktree_dir,
        repo_root=repo_root,
    )
    if not pre_check.ok:
        diag = {
            "reason": "validation_failure",
            "conflicting_files": [],
            "stderr_tail": (pre_check.output or "").strip()[-500:] or "pre-integration check failed",
            "at": telemetry.iso_now(),
        }
        _stage_task_conflict(repo_root, task_id, queue_file, backend, diag)
        print(
            f"⚠️  Task {task_id} staged in awaiting_merge due to pre-integration check "
            "failure. Lock was not acquired. Independent tasks continue."
        )
        return IntegrateResult(status="staged_conflict", detail=diag)

    print(f"   🔀 Integrating {task_id} into {integration_branch}")

    with integration_lock(repo_root):
        # Fetch latest tip so local tracking ref tracks the live remote tip.
        subprocess.run(
            ["git", "-C", repo_root, "fetch", "origin", integration_branch],
            capture_output=True,
            text=True,
        )

        res = subprocess.run(
            ["git", "-C", repo_root, "rev-parse", "--verify", f"refs/remotes/origin/{integration_branch}"],
            capture_output=True,
        )
        target_ref = f"origin/{integration_branch}" if res.returncode == 0 else integration_branch

        rc_pre, pre_rebase_commit, _ = run_git_plain(["-C", worktree_dir, "rev-parse", "HEAD"])
        pre_rebase_commit = pre_rebase_commit.strip()

        # Rebase the task branch onto the live integration tip inside the worktree.
        rebase = subprocess.run(
            ["git", "-C", worktree_dir, "rebase", target_ref],
            capture_output=True,
            text=True,
        )
        if rebase.returncode != 0:
            conflicts_run = subprocess.run(
                ["git", "-C", worktree_dir, "diff", "--name-only", "--diff-filter=U"],
                capture_output=True,
                text=True,
            )
            conflicts = [f.strip() for f in conflicts_run.stdout.splitlines() if f.strip()]
            subprocess.run(
                ["git", "-C", worktree_dir, "rebase", "--abort"],
                capture_output=True,
            )
            tail = (rebase.stderr if rebase.stderr.strip() else rebase.stdout or "").strip()[-500:]
            diag = {
                "reason": "rebase_conflict",
                "conflicting_files": conflicts,
                "stderr_tail": tail,
                "at": telemetry.iso_now(),
            }
            _stage_task_conflict(repo_root, task_id, queue_file, backend, diag)
            print(
                f"⚠️  Task {task_id} staged in awaiting_merge due to rebase conflicts. Independent tasks continue."
            )
            return IntegrateResult(status="staged_conflict", detail=diag)

        # Release guard and monolithic-commit guard under lock right after rebase, before validation (R-3)
        guard_error = check_release_guard(target_ref, feature_branch="HEAD", workspace=Path(worktree_dir))
        if guard_error:
            subprocess.run(
                ["git", "-C", worktree_dir, "reset", "--hard", pre_rebase_commit],
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", worktree_dir, "clean", "-fd"],
                capture_output=True,
            )
            diag = {
                "reason": "guard_refused",
                "conflicting_files": [],
                "stderr_tail": guard_error,
                "at": telemetry.iso_now(),
            }
            _stage_task_conflict(repo_root, task_id, queue_file, backend, diag)
            print(f"⚠️  Task {task_id} staged in awaiting_merge due to guard refusal: {guard_error}")
            return IntegrateResult(status="guard_refused", detail=diag)

        if is_monolithic_commit(target_ref, spec, feature_branch="HEAD", workspace=Path(worktree_dir)):
            subprocess.run(
                ["git", "-C", worktree_dir, "reset", "--hard", pre_rebase_commit],
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", worktree_dir, "clean", "-fd"],
                capture_output=True,
            )
            diag = {
                "reason": "guard_refused",
                "conflicting_files": [],
                "stderr_tail": (
                    "Monolithic commit detected: one commit spans the entire merge range "
                    "while the plan lists multiple tasks.\n"
                    "Run `aet ship split` to split it into logical pieces before merging."
                ),
                "at": telemetry.iso_now(),
            }
            _stage_task_conflict(repo_root, task_id, queue_file, backend, diag)
            print(f"⚠️  Task {task_id} staged in awaiting_merge due to guard refusal: {diag['stderr_tail']}")
            return IntegrateResult(status="guard_refused", detail=diag)

        # Re-validate the rebased combination before it lands (R-18).
        ok, output = _validate_after_rebase(worktree_dir, task_id=task_id, repo_root=repo_root)
        if not ok:
            subprocess.run(
                ["git", "-C", worktree_dir, "reset", "--hard", pre_rebase_commit],
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", worktree_dir, "clean", "-fd"],
                capture_output=True,
            )
            diag = {
                "reason": "validation_failure",
                "conflicting_files": [],
                "stderr_tail": output.strip()[-500:] if output else "validation failed after rebase",
                "at": telemetry.iso_now(),
            }
            _stage_task_conflict(repo_root, task_id, queue_file, backend, diag)
            print(
                f"⚠️  Task {task_id} staged in awaiting_merge due to post-rebase "
                "validation failure. Independent tasks continue."
            )
            return IntegrateResult(status="staged_conflict", detail=diag)

        # Verify required gate evidence before the squash-merge lands (R-22).
        _evidence_ok, _evidence_failures = gate.check_task_evidence(
            task_id, _plan_fm, repo_root
        )
        if not _evidence_ok:
            raise IntegrationFailureError(
                "missing required gate evidence for "
                f"{task_id}:\n" + "\n".join(_evidence_failures)
            )

        # Clean any working tree modifications from post-rebase validation before checkout.
        subprocess.run(
            ["git", "-C", worktree_dir, "reset", "--hard", "HEAD"],
            capture_output=True,
        )
        # Detached squash-merge inside the isolated worktree without touching repo_root HEAD.
        checkout = subprocess.run(
            ["git", "-C", worktree_dir, "checkout", "-f", "--detach", target_ref],
            capture_output=True,
            text=True,
        )
        if checkout.returncode != 0:
            raise IntegrationFailureError(
                f"checkout {target_ref} in worktree failed: {checkout.stderr.strip()}"
            )

        task_branch = task_dict.get("branch") or task_id
        merge = subprocess.run(
            ["git", "-C", worktree_dir, "merge", "--squash", task_branch],
            capture_output=True,
            text=True,
        )
        if merge.returncode != 0:
            subprocess.run(
                ["git", "-C", worktree_dir, "merge", "--abort"],
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", worktree_dir, "checkout", task_branch],
                capture_output=True,
            )
            raise IntegrationFailureError(
                f"squash merge of {task_branch} failed: {merge.stderr.strip()}"
            )

        commit = subprocess.run(
            ["git", "-C", worktree_dir, "commit", "-m", f"Integrate {task_id}"],
            capture_output=True,
            text=True,
        )
        if commit.returncode != 0:
            subprocess.run(
                ["git", "-C", worktree_dir, "checkout", task_branch],
                capture_output=True,
            )
            raise IntegrationFailureError(
                f"commit after squash merge failed: {commit.stderr.strip()}"
            )

        rc, out, _ = run_git_plain(["-C", worktree_dir, "rev-parse", "HEAD"])
        if rc != 0:
            raise IntegrationFailureError("could not resolve merge commit")
        merge_commit = out.strip()

        # Update local ref in repo_root.
        head_ref = subprocess.run(
            ["git", "-C", repo_root, "symbolic-ref", "--short", "HEAD"],
            capture_output=True,
            text=True,
        )
        if head_ref.returncode == 0 and head_ref.stdout.strip() == integration_branch:
            subprocess.run(
                ["git", "-C", repo_root, "reset", "--hard", merge_commit],
                capture_output=True,
                text=True,
            )
        else:
            subprocess.run(
                ["git", "-C", repo_root, "update-ref", f"refs/heads/{integration_branch}", merge_commit],
                capture_output=True,
                text=True,
            )

        ok, err = push_branch(repo_root, integration_branch)
        if not ok:
            raise IntegrationFailureError(
                f"push of {integration_branch} failed: {err}"
            )

        # Update remote-tracking ref so ancestry checks pass.
        subprocess.run(
            ["git", "-C", repo_root, "update-ref", f"refs/remotes/origin/{integration_branch}", merge_commit],
            capture_output=True,
        )

        # Clean up the task branch and worktree under lock.
        subprocess.run(
            ["git", "-C", repo_root, "worktree", "remove", "--force", worktree_dir],
            capture_output=True,
        )
        delete_local_branch(repo_root, task_branch)

    # Record the merge commit on the task record.
    if backend is not None and _task_in_queue(backend, task_id):
        queue = backend.load()["queue"]
        for t in queue:
            if t.get("id") == task_id:
                t["merge_commit"] = merge_commit
                break
        _save_task_record(backend, queue)

    # Transition task state to merged.
    if backend is not None and _task_in_queue(backend, task_id):
        aet_state_bin = str(Path(__file__).resolve().parent / "cli" / "aet_state.py")
        queue = backend.load()["queue"]
        t = next((item for item in queue if item.get("id") == task_id), None)
        curr = current_state(t) if t else "in_progress"
        if curr != "awaiting_merge" and curr != "merged":
            res = subprocess.run(
                [
                    sys.executable,
                    aet_state_bin,
                    "transition",
                    task_id,
                    curr,
                    "awaiting_merge",
                    queue_file,
                ],
                capture_output=True,
                text=True,
            )
            if res.returncode != 0:
                raise IntegrationFailureError(
                    f"Could not transition {task_id} to awaiting_merge: {res.stderr.strip()}"
                )
            curr = "awaiting_merge"
        if curr == "awaiting_merge":
            res = subprocess.run(
                [
                    sys.executable,
                    aet_state_bin,
                    "transition",
                    task_id,
                    "awaiting_merge",
                    "merged",
                    queue_file,
                ],
                capture_output=True,
                text=True,
            )
            if res.returncode != 0:
                raise IntegrationFailureError(
                    f"Could not transition {task_id} to merged: {res.stderr.strip()}"
                )

    print(f"   ✅ {task_id} integrated into {integration_branch}")
    return IntegrateResult(status="merged", detail=merge_commit)
