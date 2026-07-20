"""aet-state — Owns queue mutations, stage transitions, and footer updates.

Standard-library Python only. Derives status from ground truth (git, filesystem),
validates transition legality, and updates footers + queue JSON atomically.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from aet import queue as queue_lib  # noqa: E402
from aet.backends.factory import create_backend  # noqa: E402, I001

_INTEGRITY_ERRORS = (queue_lib.QueueIntegrityError,)

def make_backend(queue_path):
    """Create a task backend for the given queue path."""
    history_file = str(Path(queue_path).with_name("work-history.jsonl"))
    return create_backend(queue_file=queue_path, history_file=history_file)


def find_task(queue, task_id):
    for task in queue:
        if task.get("id") == task_id:
            return task
    return None


def run_git(*args, cwd=None):
    """Run a git command; return (returncode, stdout, stderr)."""
    cmd = ["git", *args]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=cwd, check=False
        )
    except FileNotFoundError:
        return (127, "", "git not found")
    return (result.returncode, result.stdout, result.stderr)


def run_gh(args, cwd=None):
    """Run a gh command; return (returncode, stdout, stderr)."""
    cmd = ["gh", *args]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=cwd, check=False
        )
    except FileNotFoundError:
        return (127, "", "gh not found")
    return (result.returncode, result.stdout, result.stderr)


def branch_exists(branch, cwd=None):
    if not branch:
        return False
    rc, _, _ = run_git("show-ref", "--verify", "--quiet", f"refs/heads/{branch}", cwd=cwd)
    return rc == 0


def is_ancestor_of_main(branch, cwd=None):
    if not branch:
        return False
    rc, _, _ = run_git("merge-base", "--is-ancestor", branch, "origin/main", cwd=cwd)
    return rc == 0


def resolve_merge_commit(branch, cwd=None):
    """Resolve the merge commit for a branch on origin/main.

    Tries, in order:
      1. Regular merge: branch tip is an ancestor of origin/main.
      2. Squash merge via `gh pr view <branch> --json mergeCommit`.
      3. Diff-equivalence fallback against recent origin/main commits.

    Returns (merge_commit, merge_strategy) or (None, None) if unresolved.
    """
    if not branch:
        return None, None

    # 1. Regular merge: branch tip is on origin/main.
    rc, out, _ = run_git("rev-parse", branch, cwd=cwd)
    if rc == 0:
        tip = out.strip()
        if is_ancestor_of_main(tip, cwd=cwd):
            return tip, "regular"

    # 2. Squash merge via GitHub CLI.
    rc, out, _ = run_gh(["pr", "view", branch, "--json", "mergeCommit"], cwd=cwd)
    if rc == 0:
        try:
            data = json.loads(out)
            sha = data.get("mergeCommit", {}).get("oid")
            if sha and is_ancestor_of_main(sha, cwd=cwd):
                return sha, "squash"
        except json.JSONDecodeError:
            pass

    # 3. Diff-equivalence fallback.
    sha = resolve_by_diff(branch, cwd=cwd)
    if sha:
        return sha, "squash"

    return None, None


def resolve_by_diff(branch, cwd=None, max_commits=20):
    """Find a squash merge by matching the branch diff to a recent main commit."""
    rc, merge_base, _ = run_git("merge-base", branch, "origin/main", cwd=cwd)
    if rc != 0:
        return None
    merge_base = merge_base.strip()

    rc, branch_diff, _ = run_git("diff", f"{merge_base}..{branch}", cwd=cwd)
    if rc != 0:
        return None
    branch_diff = branch_diff.strip()
    if not branch_diff:
        return None

    rc, commits_out, _ = run_git(
        "rev-list", "--max-count", str(max_commits), "origin/main", cwd=cwd
    )
    if rc != 0:
        return None

    for commit in commits_out.strip().splitlines():
        commit = commit.strip()
        if not commit:
            continue
        rc, commit_diff, _ = run_git("diff", f"{commit}^..{commit}", cwd=cwd)
        if rc != 0:
            continue
        if commit_diff.strip() == branch_diff:
            return commit

    return None


def derive_status(task, blocker_status_fn=None, cwd=None):
    """Derive canonical state from ground truth.

    Derivation rules, applied in order:
      1. merged   — branch or merge_commit is an ancestor of origin/main.
      2. in_progress — local branch exists.
      3. ready    — plan exists, no branch, and all blockers are terminal
                   (including the case of no blockers).
      4. blocked  — plan exists, no branch, and some blocker is not terminal.
      5. drift    — plan file is missing.
      6. planned  — plan exists, no branch, no blockers.
    """
    plan_file = task.get("plan_file")
    branch = task.get("branch")
    worktree = task.get("worktree")
    merge_commit = task.get("merge_commit")

    derived = {"derived_status": "unknown"}

    # Plan file exists?
    if plan_file and Path(plan_file).exists():
        derived["plan_exists"] = True
    else:
        derived["plan_exists"] = False

    # Branch exists?
    if branch and branch_exists(branch, cwd=cwd):
        derived["branch_exists"] = True
    else:
        derived["branch_exists"] = False

    # Ancestry check (branch OR merge_commit must be on main)
    on_main = False
    if branch and is_ancestor_of_main(branch, cwd=cwd):
        on_main = True
    if merge_commit and is_ancestor_of_main(merge_commit, cwd=cwd):
        on_main = True
    derived["on_main"] = on_main

    # Worktree present?
    if worktree and Path(worktree).is_dir():
        derived["has_worktree"] = True
    else:
        derived["has_worktree"] = False

    # Merge commit set?
    if merge_commit:
        derived["merge_verified"] = True
    else:
        derived["merge_verified"] = False

    # Determine actionable canonical state.
    status = "unknown"
    if on_main:
        status = "merged"
    elif derived["branch_exists"]:
        status = "in_progress"
    elif derived["plan_exists"]:
        blockers = task.get("blocked_by", [])
        if blockers and blocker_status_fn:
            terminal = {"merged", "abandoned"}
            all_terminal = all(blocker_status_fn(b) in terminal for b in blockers)
            status = "ready" if all_terminal else "blocked"
        elif blockers and not blocker_status_fn:
            # Blockers exist but we cannot resolve them; fall back to planned.
            status = "planned"
        else:
            # No blockers means the task is actionable.
            status = "ready"
    else:
        status = "drift"
        derived["drift"] = "plan_file missing"

    # Warnings
    current_status = queue_lib.current_state(task) or ""
    warnings = []
    if current_status == "awaiting_merge" and not merge_commit and not on_main:
        warnings.append("awaiting_merge without merge verification")
    if current_status == "merged" and not on_main:
        warnings.append("merged state but not ancestor of origin/main")
    if warnings:
        derived["warnings"] = warnings
        status = f"{status} (warning: {'; '.join(warnings)})"

    derived["derived_status"] = status
    return derived


def validate_transition(task, from_stage, to_stage, cwd=None):
    """Return (ok, message). ok=True means the state transition is legal.

    Validates the recorded-forward lifecycle (ADR-011).  ``from_stage`` and
    ``to_stage`` are canonical state values, not legacy status strings.
    """
    current_state = queue_lib.current_state(task)
    branch = task.get("branch")
    merge_commit = task.get("merge_commit")

    # Basic: from_stage should match current state
    if from_stage != current_state:
        return (False, f"Current state is '{current_state}', not '{from_stage}'.")

    # Transition must be legal in the lifecycle
    legal = queue_lib.LEGAL_TRANSITIONS.get(from_stage, set())
    if to_stage not in legal:
        return (False, f"Illegal transition: {from_stage} -> {to_stage}.")

    # Cannot set merged without ancestry check
    if to_stage == "merged":
        on_main = False
        if branch:
            on_main = is_ancestor_of_main(branch, cwd=cwd)
        if merge_commit:
            on_main = on_main or is_ancestor_of_main(merge_commit, cwd=cwd)
        if not on_main:
            return (False, "Cannot set merged: branch/merge_commit is not ancestor of origin/main.")

    return (True, "Transition is valid.")


def _apply_transition(backend, queue, task, from_state, to_state, by, evidence=None, cwd=None, history_file=None):
    """Apply a validated state transition and propagate the forward frontier.

    This is the only function that assigns ``task["state"]``.  It validates the
    transition, appends history, promotes dependents after terminal transitions,
    persists the queue through the configured backend, and seals terminal tasks
    to the settled history log.
    """
    ok, msg = validate_transition(task, from_state, to_state, cwd=cwd)
    if not ok:
        raise RuntimeError(msg)

    now = datetime.now(timezone.utc).isoformat()

    task["state"] = to_state

    if to_state == "merged":
        task["merged_at"] = now
        task["completed_at"] = now
    elif to_state in queue_lib.TERMINAL_STATES:
        task["completed_at"] = now

    queue_lib.append_history(task, from_state, to_state, by, evidence)

    # Forward frontier: terminal transitions unblock dependents. A dependent is
    # promoted once its last blocker clears, whether it was curated as
    # ``blocked`` or is still sitting at ``planned`` (pre-frh-15 intake). The
    # release history entry records the actual from-state.
    if to_state in queue_lib.TERMINAL_STATES:
        for dep_id in task.get("blocks", []):
            dep = find_task(queue, dep_id)
            if not dep:
                continue
            pb = queue_lib.pending_blockers(dep)
            if pb > 0:
                pb -= 1
                dep["pending_blockers"] = pb
            dep_state = queue_lib.current_state(dep)
            if pb == 0 and dep_state in ("blocked", "planned"):
                dep["state"] = "ready"
                queue_lib.append_history(dep, dep_state, "ready", "release")

    backend.save(queue)
    backend.on_transition(task["id"], from_state, to_state, evidence)

    # Seal terminal tasks to the append-only settled history log. Routing
    # through the backend keeps the file-path assumption out of aet-state so
    # non-file backends (e.g. git refs) can drop their own live record first.
    if to_state in queue_lib.TERMINAL_STATES:
        if history_file is None:
            history_file = getattr(backend, "history_file", None) or str(
                Path(backend.queue_file).with_name("work-history.jsonl")
            )
        backend.seal(task["id"], history_file)
        backend.close_task(task["id"], evidence)


def _set_stage(task, stage, by="orch"):
    """Set the pipeline stage sub-state on a task that is in_progress.

    This is the only function that assigns ``task["stage"]``.  It appends a
    history entry and returns nothing.  The caller must ensure the task is
    loaded from the latest queue and that the queue is saved afterwards.
    """
    current = queue_lib.current_state(task)
    if current != "in_progress":
        raise RuntimeError(
            f"Cannot set stage: task state is '{current}', must be 'in_progress'."
        )

    previous_stage = task.get("stage")
    task["stage"] = stage
    queue_lib.append_history(task, previous_stage, stage, by, {"kind": "stage"})


def cmd_set_stage(args):
    """Set the pipeline stage sub-state for a task in the queue."""
    backend = make_backend(args.queue)

    if not queue_lib.lease_guard(args.queue, force=getattr(args, "force", False)):
        return 1

    with queue_lib.queue_lock(args.queue):
        data = backend.load()
        queue = data["queue"]
        task = find_task(queue, args.task_id)
        if not task:
            print(f"Task not found: {args.task_id}", file=sys.stderr)
            return 1

        if args.dry_run:
            current = queue_lib.current_state(task)
            if current == "in_progress":
                print(
                    f"[dry-run] Would set stage for {args.task_id}: "
                    f"{task.get('stage')} -> {args.stage}"
                )
                return 0
            print(
                f"Cannot set stage: task state is '{current}', must be 'in_progress'.",
                file=sys.stderr,
            )
            return 1

        try:
            _set_stage(task, args.stage, by="orch")
        except RuntimeError as e:
            print(str(e), file=sys.stderr)
            return 1

        backend.save(queue)

    print(f"Set stage for {args.task_id}: {args.stage}")
    return 0


def _derive_all_states(queue, cwd, history=None):
    """Return (task_by_id, derived) for every task in the queue.

    Settled history records seed ``derived`` so a dependent whose blocker
    already reached a terminal state and was archived out of the live queue
    derives ``ready`` instead of staying ``blocked`` forever. The settled log
    is terminal by construction (only ``seal_terminal`` writes to it).
    """
    tasks = queue
    task_by_id = {t["id"]: t for t in tasks if t.get("id")}
    derived = {}

    for settled in history or []:
        sid = settled.get("id")
        if sid and sid not in task_by_id:
            state = settled.get("state")
            derived[sid] = {
                "derived_status": state if state in queue_lib.TERMINAL_STATES else "merged"
            }

    def blocker_status(task_id):
        if task_id not in derived and task_id in task_by_id:
            derived[task_id] = derive_status(task_by_id[task_id], blocker_status, cwd=cwd)
        status = derived.get(task_id, {}).get("derived_status", "unknown")
        return status.split(" (warning")[0]

    for task in tasks:
        task_id = task["id"]
        if task_id not in derived:
            derived[task_id] = derive_status(task, blocker_status, cwd=cwd)

    return task_by_id, derived


def cmd_audit(args):
    """Reconcile stored state against git ground truth without mutating.

    Reports every task where the recorded state disagrees with the state
    derived from git. This is the old ``derive`` command repurposed as an
    explicit, human-run audit; it never runs during normal operation.

    A queue whose integrity envelope no longer matches its tasks (edited
    outside ``aet-state``) is still auditable: the mismatch is reported on
    stderr and the audit proceeds with the unverified data, so audit works
    as the diagnostic for exactly the situation it is recommended in. Run
    ``aet state heal --apply`` to reconcile and restamp the envelope.
    """
    backend = make_backend(args.queue)
    try:
        backend.load()
    except _INTEGRITY_ERRORS:
        print(
            "⚠️  Queue integrity check failed (content_hash mismatch); "
            "audit continues with unverified data. "
            "Run `aet state heal --apply` to reconcile and restamp.",
            file=sys.stderr,
        )
    data = backend.load(verify=False)
    queue = data["queue"]
    cwd = os.path.dirname(args.queue) if args.queue else "."
    task_by_id, derived = _derive_all_states(queue, cwd, history=data["history"])

    results = {}
    for task in queue:
        task_id = task["id"]
        stored_state = queue_lib.current_state(task)
        derived_state = derived[task_id]["derived_status"].split(" (warning")[0]
        results[task_id] = {
            "stored": stored_state,
            "derived": derived[task_id]["derived_status"],
            "discrepancy": stored_state != derived_state,
        }

    print(json.dumps(results, indent=2))
    return 0


def cmd_heal(args):
    """Reconcile stored state against git ground truth and apply safe fixes.

    Safe fixes:
      - merged: task branch or merge_commit is an ancestor of origin/main.
      - failed -> ready: plan exists, no branch, and blockers are terminal.
      - pending_blockers recount: the stored counter is reconciled against
        blockers that are not terminal in the live queue or the settled
        history log, so tasks added after a blocker merged cannot deadlock
        on a stale count.

    With ``--apply``, transitions are applied; otherwise the command prints a
    dry-run report.

    A queue whose integrity envelope no longer matches its tasks (edited
    outside ``aet-state``) is loaded unverified so heal can act as the
    repair path. ``--apply`` restamps the envelope (revision + content_hash)
    before applying any fixes, so a successful heal always leaves the queue
    verifiable again — including when there is nothing else to fix.
    """
    backend = make_backend(args.queue)
    integrity_ok = True
    try:
        backend.load()
    except _INTEGRITY_ERRORS:
        integrity_ok = False
        print(
            "⚠️  Queue integrity check failed (content_hash mismatch); "
            "heal continues with unverified data.",
            file=sys.stderr,
        )
    data = backend.load(verify=False)
    queue = data["queue"]
    cwd = os.path.dirname(args.queue) if args.queue else "."
    task_by_id, derived = _derive_all_states(queue, cwd, history=data["history"])

    # A blocker counts as pending only while it is not terminal in the live
    # queue and not settled in history.
    terminal_ids = {
        t["id"]
        for t in queue
        if t.get("id") and queue_lib.current_state(t) in queue_lib.TERMINAL_STATES
    }
    terminal_ids.update(h["id"] for h in data["history"] if h.get("id"))

    changes: list[dict] = []
    for task in queue:
        task_id = task["id"]
        stored_state = queue_lib.current_state(task)
        derived_state = derived[task_id]["derived_status"].split(" (warning")[0]

        # Quarantined is a human-held state: it reconciles to itself and is never
        # auto-derived away by heal (nsr-02).
        if stored_state == "quarantined":
            continue

        change = None
        # Only heal toward terminal/ready states; never move a merged task backward.
        if derived_state == "merged" and stored_state != "merged":
            change = {
                "task_id": task_id,
                "from": stored_state,
                "to": "merged",
                "reason": "branch/merge_commit is ancestor of origin/main",
                "branch": task.get("branch"),
            }
        elif derived_state == "ready" and stored_state in ("failed", "blocked", "planned"):
            change = {
                "task_id": task_id,
                "from": stored_state,
                "to": "ready",
                "reason": "plan exists and blockers are terminal",
            }
        elif derived_state == "failed" and stored_state == "in_progress":
            change = {
                "task_id": task_id,
                "from": stored_state,
                "to": "failed",
                "reason": "branch does not exist and plan is missing or blocked",
            }

        computed_pb = len(
            [b for b in task.get("blocked_by", []) if b not in terminal_ids]
        )
        if computed_pb != queue_lib.pending_blockers(task):
            if change is None:
                change = {
                    "task_id": task_id,
                    "from": stored_state,
                    "to": stored_state,
                    "reason": "pending_blockers recount against settled blockers",
                }
            change["pending_blockers"] = computed_pb

        if change is not None:
            changes.append(change)

    if not changes:
        print("No healable discrepancies found.")
        if integrity_ok:
            return 0
        if not args.apply:
            print("Queue integrity envelope is stale; run with --apply to restamp it.")
            return 0
        # Fall through: no state fixes, but the envelope needs restamping.
    else:
        print("Proposed changes:")
        for change in changes:
            line = f"  {change['task_id']}: {change['from']} -> {change['to']} ({change['reason']})"
            if "pending_blockers" in change:
                line += f" [pending_blockers -> {change['pending_blockers']}]"
            print(line)

        if not args.apply:
            print("\nRun with --apply to apply these changes.")
            return 0

    if not queue_lib.lease_guard(args.queue, force=getattr(args, "force", False)):
        return 1

    if not integrity_ok:
        # Restamp before applying fixes: every later load in this run (the
        # per-change reloads below and any record-merge invocation) verifies
        # against the new hash.
        with queue_lib.queue_lock(args.queue):
            fresh = backend.load(verify=False)
            backend.save(fresh["queue"])
        print("Restamped queue integrity envelope (revision + content_hash).")
        if not changes:
            return 0

    applied = 0
    failed = 0
    for change in changes:
        task_id = change["task_id"]

        # Each change is a full read-modify-write cycle on the queue; hold the
        # lock for the duration so concurrent writers cannot interleave.
        with queue_lib.queue_lock(args.queue):
            # Re-load the queue before each change; previous changes (especially
            # record-merge sealing a task) mutate the stored queue.
            data = backend.load()
            queue = data["queue"]
            task = find_task(queue, task_id)
            if not task:
                # Task was already sealed by a previous heal step.
                applied += 1
                continue

            from_state = queue_lib.current_state(task)
            to_state = change["to"]

            if "pending_blockers" in change:
                task["pending_blockers"] = change["pending_blockers"]

            if from_state == to_state:
                # Counter-only reconciliation: no transition, just persist.
                if "pending_blockers" in change:
                    backend.save(queue)
                applied += 1
                continue

            if to_state == "merged":
                # Prefer resolving via record-merge so merge_commit is captured.
                branch = task.get("branch") or change.get("branch")
                if branch:
                    merge_ns = argparse.Namespace(
                        command="record-merge",
                        task_id=task_id,
                        queue=args.queue,
                        dry_run=False,
                        plan=None,
                        branch=branch,
                        merge_commit=task.get("merge_commit"),
                    )
                    rc = cmd_record_merge(merge_ns)
                    if rc == 0:
                        applied += 1
                    else:
                        failed += 1
                    continue

            try:
                _apply_transition(
                    backend, queue, task, from_state, to_state,
                    by="heal", evidence={"reason": change["reason"]}, cwd=cwd,
                )
                applied += 1
            except RuntimeError as e:
                print(f"  Could not heal {task_id}: {e}", file=sys.stderr)
                failed += 1

    print(f"\nHealed {applied} task(s); {failed} failed.")
    return 1 if failed > 0 else 0


def cmd_validate(args):
    backend = make_backend(args.queue)
    data = backend.load()
    queue = data["queue"]
    task = find_task(queue, args.task_id)
    if not task:
        print(f"Task not found: {args.task_id}", file=sys.stderr)
        return 1
    cwd = os.path.dirname(args.queue) if args.queue else "."
    ok, msg = validate_transition(task, args.from_stage, args.to_stage, cwd=cwd)
    if ok:
        print(msg)
        return 0
    print(msg, file=sys.stderr)
    return 1


def cmd_transition(args):
    backend = make_backend(args.queue)
    cwd = os.path.dirname(args.queue) if args.queue else "."

    if not queue_lib.lease_guard(args.queue, force=getattr(args, "force", False)):
        return 1

    with queue_lib.queue_lock(args.queue):
        data = backend.load()
        queue = data["queue"]
        task = find_task(queue, args.task_id)
        if not task:
            print(f"Task not found: {args.task_id}", file=sys.stderr)
            return 1

        if args.dry_run:
            ok, msg = validate_transition(task, args.from_stage, args.to_stage, cwd=cwd)
            if ok:
                print(f"[dry-run] Would transition {args.task_id} {args.from_stage} -> {args.to_stage}")
                return 0
            print(msg, file=sys.stderr)
            return 1

        evidence = {"reason": args.reason} if args.reason else None
        try:
            _apply_transition(
                backend, queue, task, args.from_stage, args.to_stage,
                by="transition", evidence=evidence, cwd=cwd,
            )
        except RuntimeError as e:
            print(str(e), file=sys.stderr)
            return 1

    print(f"Transitioned {args.task_id}: {args.from_stage} -> {args.to_stage}")
    return 0


def cmd_record_merge(args):
    """Resolve and record the merge commit for a task atomically."""
    backend = make_backend(args.queue)
    cwd = os.path.dirname(args.queue) if args.queue else "."
    history_file = getattr(backend, "history_file", None)

    if not queue_lib.lease_guard(args.queue, force=getattr(args, "force", False)):
        return 1

    # Load task. If a previous record-merge already transitioned the task to
    # merged but failed to push the plan status commit, retry only the plan
    # closure push.
    with queue_lib.queue_lock(args.queue):
        data = backend.load()
        queue = data["queue"]
        task = find_task(queue, args.task_id)
        sealed_task = None
        if not task and history_file:
            sealed_task = find_task(
                queue_lib.read_history(history_file), args.task_id
            )
            if sealed_task and sealed_task.get("state") != "merged":
                sealed_task = None

        if not task and not sealed_task:
            print(f"Task not found: {args.task_id}", file=sys.stderr)
            return 1

    if sealed_task:
        explicit_plan = getattr(args, "plan", None)
        plan_path = explicit_plan or sealed_task.get("plan_file")
        if plan_path and Path(plan_path).exists():
            rc = queue_lib.commit_and_push_status(
                plan_path, "merged", task_id=args.task_id, cwd=cwd,
                footer_stage="merged",
            )
            if rc != 0:
                print(
                    f"Merge recorded locally, but plan closure could not be pushed "
                    f"for {args.task_id}. Re-run record-merge to retry.",
                    file=sys.stderr,
                )
                return rc
        elif explicit_plan:
            print(
                f"Merge recorded, but explicit plan file not found: {explicit_plan}",
                file=sys.stderr,
            )
            return 1
        print(
            f"Recorded merge for {args.task_id}: "
            f"{sealed_task.get('merge_commit')} ({sealed_task.get('merge_strategy')})"
        )
        return 0

    # Resolve the merge commit against git before touching the queue.
    branch = getattr(args, "branch", None)
    cli_merge_commit = getattr(args, "merge_commit", None)

    # Fetch origin first.
    rc, _, err = run_git("fetch", "origin", cwd=cwd)
    if rc != 0:
        print(f"git fetch origin failed: {err}", file=sys.stderr)
        return 1

    if cli_merge_commit:
        if not is_ancestor_of_main(cli_merge_commit, cwd=cwd):
            print(
                f"Merge verification failed: {cli_merge_commit} is not an ancestor of origin/main.",
                file=sys.stderr,
            )
            return 1
        merge_commit = cli_merge_commit
        merge_strategy = "manual"
    else:
        branch = branch or task.get("branch")
        if not branch:
            print(f"Task {args.task_id} has no branch. Use --branch or --merge-commit.", file=sys.stderr)
            return 1
        merge_commit, merge_strategy = resolve_merge_commit(branch, cwd=cwd)

    if not merge_commit:
        print(
            "Merge verification failed: could not determine merge commit on origin/main.",
            file=sys.stderr,
        )
        return 1

    with queue_lib.queue_lock(args.queue):
        # Re-load in case another process changed the queue while we talked to git.
        data = backend.load()
        queue = data["queue"]
        task = find_task(queue, args.task_id)
        if not task:
            print(f"Task not found: {args.task_id}", file=sys.stderr)
            return 1

        current_state = queue_lib.current_state(task)
        previous_merge_commit = task.get("merge_commit")
        previous_merge_strategy = task.get("merge_strategy")
        previous_branch = task.get("branch")
        task["merge_commit"] = merge_commit
        task["merge_strategy"] = merge_strategy
        if branch and task.get("branch") != branch:
            task["branch"] = branch

        if args.dry_run:
            ok, msg = validate_transition(task, current_state, "merged", cwd=cwd)
            if ok:
                print(
                    f"[dry-run] Would record merge for {args.task_id}: "
                    f"{merge_commit} ({merge_strategy})"
                )
                return 0
            task["merge_commit"] = previous_merge_commit
            task["merge_strategy"] = previous_merge_strategy
            task["branch"] = previous_branch
            print(msg, file=sys.stderr)
            return 1

        evidence = {"merge_commit": merge_commit, "merge_strategy": merge_strategy}
        try:
            _apply_transition(
                backend, queue, task, current_state, "merged",
                by="record-merge", evidence=evidence, cwd=cwd,
            )
        except RuntimeError as e:
            task["merge_commit"] = previous_merge_commit
            task["merge_strategy"] = previous_merge_strategy
            task["branch"] = previous_branch
            print(str(e), file=sys.stderr)
            return 1

    # Terminal truth lives in the plan file. Update both frontmatter status and
    # footer stage when a plan path is provided or the task references an
    # existing plan file, then commit and push so the closure is versioned.
    explicit_plan = getattr(args, "plan", None)
    plan_path = explicit_plan or task.get("plan_file")
    if plan_path and Path(plan_path).exists():
        rc = queue_lib.commit_and_push_status(
            plan_path, "merged", task_id=args.task_id, cwd=cwd,
            footer_stage="merged",
        )
        if rc != 0:
            # Local commit is intact; recoverable on re-run.
            print(
                f"Merge recorded locally, but plan closure could not be pushed "
                f"for {args.task_id}. Re-run record-merge to retry.",
                file=sys.stderr,
            )
            return rc
    elif explicit_plan:
        print(
            f"Merge recorded, but explicit plan file not found: {explicit_plan}",
            file=sys.stderr,
        )
        return 1

    print(f"Recorded merge for {args.task_id}: {merge_commit} ({merge_strategy})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aet-state",
        description="Owns queue mutations, stage transitions, and footer updates.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show changes without applying them.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Override a live run lease and mutate the queue anyway (with a warning).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # audit
    audit_parser = subparsers.add_parser("audit", help="Reconcile stored state against git without mutating.")
    audit_parser.add_argument("queue", nargs="?", default=".agents/work-queue.json", help="Path to queue JSON.")

    # heal
    heal_parser = subparsers.add_parser("heal", help="Reconcile stored state against git and apply safe fixes.")
    heal_parser.add_argument("queue", nargs="?", default=".agents/work-queue.json", help="Path to queue JSON.")
    heal_parser.add_argument("--apply", action="store_true", help="Apply proposed changes; otherwise dry-run.")

    # validate
    validate_parser = subparsers.add_parser("validate", help="Check if a transition is legal.")
    validate_parser.add_argument("task_id", help="Task ID.")
    validate_parser.add_argument("from_stage", help="Current stage.")
    validate_parser.add_argument("to_stage", help="Target stage.")
    validate_parser.add_argument("queue", nargs="?", default=".agents/work-queue.json", help="Path to queue JSON.")

    # transition
    transition_parser = subparsers.add_parser("transition", help="Validate legality, then apply state change.")
    transition_parser.add_argument("task_id", help="Task ID.")
    transition_parser.add_argument("from_stage", help="Current stage.")
    transition_parser.add_argument("to_stage", help="Target stage.")
    transition_parser.add_argument("queue", nargs="?", default=".agents/work-queue.json", help="Path to queue JSON.")
    transition_parser.add_argument("--reason", help="Reason for transition (used as history evidence).")

    # set-stage
    set_stage_parser = subparsers.add_parser(
        "set-stage", help="Set the pipeline stage sub-state for an in-progress task."
    )
    set_stage_parser.add_argument("task_id", help="Task ID.")
    set_stage_parser.add_argument("stage", help="Pipeline stage to record.")
    set_stage_parser.add_argument("queue", nargs="?", default=".agents/work-queue.json", help="Path to queue JSON.")

    # record-merge
    record_merge_parser = subparsers.add_parser(
        "record-merge", help="Resolve and record the merge commit for a task."
    )
    record_merge_parser.add_argument("task_id", help="Task ID.")
    record_merge_parser.add_argument(
        "queue", nargs="?", default=".agents/work-queue.json", help="Path to queue JSON."
    )
    record_merge_parser.add_argument(
        "--branch",
        help="Branch name to use for merge verification. Overrides the task's branch field.",
    )
    record_merge_parser.add_argument(
        "--merge-commit",
        help="Merge commit SHA to record directly. Must be an ancestor of origin/main.",
    )
    record_merge_parser.add_argument(
        "--plan",
        help="Path to the plan markdown file. If omitted, uses the task's plan_file.",
    )

    return parser


def main(argv: list[str] | None = None):
    args = build_parser().parse_args(argv)

    try:
        if args.command == "audit":
            return cmd_audit(args)
        if args.command == "heal":
            return cmd_heal(args)
        if args.command == "validate":
            return cmd_validate(args)
        if args.command == "transition":
            return cmd_transition(args)
        if args.command == "set-stage":
            return cmd_set_stage(args)
        if args.command == "record-merge":
            return cmd_record_merge(args)
    except _INTEGRITY_ERRORS as exc:
        # Fail closed with a deliberate message, not a traceback.
        print(f"⛔ {exc}", file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
