"""Unified orchestrator for the Agentic Engineering Toolkit.

Usage:
    orchestrator --queue-file .agents/work-queue.json
    orchestrator --plan-file docs/plans/FEAT-001-plan.md

Daemonization design (Open Question #3, nc-06-run-daemonization):

The orchestrator itself is process-attachment-agnostic: it reads stdin/stdout
normally and relies on the dispatcher to decide whether to wait for it.  When
invoked with ``--log-file`` the orchestrator redirects its own stdout/stderr to
that file so the log is authoritative even if the parent dispatcher exits.  The
dispatcher performs the actual detach by spawning the orchestrator with
``subprocess.Popen(..., start_new_session=True)`` and immediately returning.
This keeps all fork/session-leader logic in one place (the dispatcher) while the
orchestrator remains a well-behaved Python program that can still be run
interactively for debugging.

Run metadata lives under ``.agents/runs/<run-id>/``:

* ``output.log`` — stdout/stderr of the orchestrator
* ``pid`` — orchestrator pid, written after startup
* ``started`` — ISO timestamp

The per-task ``--task-timeout`` and ``--stall-timeout`` watchdog logic is
untouched by this change; only the launch presentation layer changed.
"""

from __future__ import annotations

import argparse
import collections
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import typer

_SCRIPT_DIR = Path(__file__).resolve().parent
from aet import (  # noqa: E402
    breaker,
    evidence,
    plan_parser,
    plan_size,
    telemetry,
    track_record,
    triage,
    wirelog,
)
from aet import failure as failure_lib  # noqa: E402
from aet import usage as usage_lib  # noqa: E402
from aet.backends.factory import create_backend  # noqa: E402
from aet.cli_adapter import resolve_cli_adapter  # noqa: E402
from aet.queue import (  # noqa: E402
    LEGAL_TRANSITIONS,
    QueueIntegrityError,
    acquire_lease,
    current_state,
    get_next_unblocked,
    queue_lock,
    release_lease,
)
from aet.queue import (  # noqa: E402
    has_pending_tasks as queue_has_pending_tasks,
)
from aet.verifier import (  # noqa: E402
    read_plan_stage,
    verify_branch_has_commits,
    verify_stage_advancement,
)
from aet.workflow import Workflow, WorkflowError, WorkflowStage, load_workflow  # noqa: E402
from aet.worktree import (  # noqa: E402
    check_main_hygiene,
    copy_untracked_files,
    create_worktree,
    prepare_worktree_dependencies,
    remove_worktree,
)

# Global shutdown flag
_shutdown_requested = False


def _handle_signal(signum: int, _frame) -> None:
    global _shutdown_requested
    _shutdown_requested = True
    print(f"\n⚠️  Received signal {signum}. Shutting down gracefully...")


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


def _killpg(pid: int, sig: int) -> None:
    """Send a signal to the process group led by pid, ignoring stale targets."""
    try:
        pgid = os.getpgid(pid)
        os.killpg(pgid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def _terminate_process_group(proc: subprocess.Popen, timeout: float = 10) -> None:
    """Escalate from SIGTERM to SIGKILL for a process group."""
    if proc.poll() is not None:
        return
    _killpg(proc.pid, signal.SIGTERM)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return
        time.sleep(0.1)
    _killpg(proc.pid, signal.SIGKILL)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def _make_backend(queue_file: str):
    """Create a task backend for the given queue file.

    The history file is derived from the queue file path so the backend pair
    stays consistent regardless of where the queue lives.
    """
    history_file = str(Path(queue_file).with_name("work-history.jsonl"))
    return create_backend(queue_file=queue_file, history_file=history_file)


def _runs_dir(repo_root: str) -> Path:
    """Return the canonical directory for detached-run metadata."""
    return Path(repo_root) / ".agents" / "runs"


def _run_dir(repo_root: str, run_id: str) -> Path:
    """Return the per-run metadata directory for ``run_id``."""
    return _runs_dir(repo_root) / run_id


def _write_run_metadata(repo_root: str, run_id: str) -> None:
    """Persist pid and started timestamp for an active detached run.

    Best-effort: any filesystem failure is logged but does not block the run.
    """
    rdir = _run_dir(repo_root, run_id)
    try:
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "pid").write_text(str(os.getpid()), encoding="utf-8")
        (rdir / "started").write_text(telemetry.iso_now(), encoding="utf-8")
    except OSError as exc:
        print(f"   ⚠️  Could not write run metadata for {run_id}: {exc}")


def _write_returncode(repo_root: str, run_id: str, exit_code: int) -> None:
    """Persist the orchestrator's exit code so ``aet run --follow`` can mirror it.

    Best-effort: any filesystem failure is logged but does not block the run.
    """
    rc_file = _run_dir(repo_root, run_id) / "returncode"
    try:
        rc_file.parent.mkdir(parents=True, exist_ok=True)
        rc_file.write_text(str(exit_code), encoding="utf-8")
    except OSError as exc:
        print(f"   ⚠️  Could not write returncode for {run_id}: {exc}")


def _redirect_output(log_file: str | None) -> None:
    """Redirect stdout/stderr to ``log_file`` when in detached-run mode.

    The original stdout/stderr file descriptors are duplicated so tracebacks
    during early startup still have somewhere to go.  ``log_file`` is created
    if it does not exist and appended to if it does (supports ``--follow`` on
    a restarted run).
    """
    if not log_file:
        return
    try:
        # Ensure the log directory exists before reopening fds.
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        log = open(log_file, "a", buffering=1, encoding="utf-8")
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(log.fileno(), sys.stdout.fileno())
        os.dup2(log.fileno(), sys.stderr.fileno())
        # Keep the file object alive so the interpreter does not close the fd.
        sys._aet_run_log = log  # type: ignore[attr-defined]
    except OSError as exc:
        print(f"   ⚠️  Could not redirect output to {log_file}: {exc}", file=sys.stderr)



def read_plan_pipeline(plan_file: str) -> str | None:
    """Return the pipeline mode declared in plan frontmatter, if any.

    Only the simple ``pipeline: minimal|standard|full`` form is supported.
    Returns ``None`` when the field is absent so the caller can fall back to
    the CLI default.
    """
    try:
        text = Path(plan_file).read_text(encoding="utf-8")
    except OSError:
        return None

    if not text.startswith("---"):
        return None

    end = text.find("\n---", 3)
    if end == -1:
        return None

    frontmatter = text[3:end]
    match = re.search(r"^pipeline:\s*(\S+)", frontmatter, re.MULTILINE)
    if not match:
        return None

    value = match.group(1).strip().strip("\"'")
    if value in ("minimal", "standard", "full"):
        return value
    return None


def effective_isolation(plan_file: str, cli_isolation: str) -> str:
    """Return the isolation level for a task.

    Plan frontmatter takes precedence; the CLI flag is the fallback.
    """
    plan_isolation = read_plan_pipeline(plan_file)
    return plan_isolation if plan_isolation else cli_isolation


def get_current_stage(task: dict, plan_file: str, entry_stage: str) -> str:
    """Return the current pipeline stage from the task record.

    The footer is consulted only as a backward-compatible fallback; it is
    never used to make scheduling decisions (ADR-011). With no record and no
    footer the task starts at the workflow's entry stage.
    """
    return task.get("stage") or read_plan_stage(plan_file) or entry_stage


def _record_stage(task: dict, stage: str, repo_root: str) -> bool:
    """Persist an advanced pipeline stage to the task record.

    When the task is tracked in the work queue, this routes through
    ``aet-state set-stage`` so the sole-writer rule is preserved.  Otherwise
    the in-memory task dict is updated directly (single-plan mode without a
    queue).
    """
    task_id = task.get("id")
    queue_file = os.path.join(repo_root, ".agents", "work-queue.json")
    if task_id and os.path.exists(queue_file):
        aet_state_bin = str(_SCRIPT_DIR / "aet_state.py")
        result = subprocess.run(
            [
                sys.executable,
                aet_state_bin,
                "set-stage",
                task_id,
                stage,
                queue_file,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            task["stage"] = stage
            return True
        print(f"   ⚠️  Could not set stage for {task_id}: {result.stderr.strip()}")
        return False

    task["stage"] = stage
    return True


def enforce_main_hygiene(repo_root: str) -> bool:
    """Check main hygiene and decide whether to proceed.

    Returns True when the caller should continue, False when it should halt.
    Main hygiene is a mechanical durability check (see ADR-005/ADR-027): a real
    violation halts in both interactive and unattended mode so an AFK run never
    builds an empty worktree off a dirty or unpushed ``main``.
    """
    ok, msg = check_main_hygiene(repo_root)
    if ok:
        return True

    print(f"⛔ {msg}. Halting.")
    return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AE Toolkit Unified Orchestrator")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--queue-file", help="Path to work-queue.json (batch mode)")
    group.add_argument("--plan-file", help="Path to a single plan.md (single-plan mode)")
    parser.add_argument("--repo-root", default=os.getcwd(), help="Repository root path")
    parser.add_argument("--cli-bin", default=None, help="Agent CLI binary path")
    parser.add_argument("--isolation", default="standard", choices=["minimal", "standard", "full"])
    parser.add_argument("--max-jobs", type=int, default=4, help="Max parallel tasks (batch mode)")
    parser.add_argument(
        "--task-timeout",
        type=int,
        default=7200,
        help="Per-task wall-clock timeout in seconds (default: 7200).",
    )
    parser.add_argument(
        "--stall-timeout",
        type=int,
        default=300,
        help="Stdout-silence timeout in seconds before a session is killed (default: 300).",
    )
    parser.add_argument(
        "--heartbeat-interval",
        type=int,
        default=60,
        help="Seconds between heartbeat log lines (default: 60).",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Run identifier used for telemetry and run metadata.",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="Redirect stdout/stderr to this file (detached-run mode).",
    )
    parser.add_argument(
        "--on-failure",
        choices=["triage", "continue", "halt"],
        default="triage",
        help=(
            "What to do when a task fails in batch mode: triage (default) "
            "requeues transient failures; continue marks failed and keeps "
            "spawning; halt stops the shift on the first failure."
        ),
    )
    return parser


def parse_args(argv) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def _freshness_clause(decision: str) -> str:
    """Prompt text that modulates the 'run validations' instruction.

    Empty for RUN or unknown — validations run as normal. For a fresh QA
    verdict it tells the stage to trust that verdict instead of re-running the
    suite on a tree QA already proved green: the F2 dedup, decided in code and
    obeyed in prose.
    """
    if decision == evidence.SKIP:
        return (
            " The toolkit verified the working tree is UNCHANGED since QA"
            " validated it green: trust the QA verdict and do NOT re-run the"
            " test suite to reconfirm it. Run validations only if you modify"
            " code in this stage; if you do, re-run full validation before"
            " finishing."
        )
    if decision == evidence.LINT_ONLY:
        return (
            " The toolkit verified only non-code files changed since QA"
            " validated the tree green: run lint/format checks only and do NOT"
            " re-run the test suite. If you modify code, re-run full validation"
            " before finishing."
        )
    return ""


def _qa_freshness_decision(
    task_id: str | None, repo_root: str, worktree_dir: str
) -> str:
    """Freshness of the QA verdict vs. the current worktree, or "" on any error.

    Never raises: a stage spawn must not hinge on this optimization. The
    worktree is hashed here, where the orchestrator knows the real path, rather
    than left for a stage session to resolve from env.
    """
    if not task_id:
        return ""
    try:
        result = evidence.validation_freshness(
            task_id,
            "qa",
            worktree_dir=worktree_dir,
            project_slug=telemetry.derive_project_slug(repo_root),
        )
        return result.decision
    except (OSError, ValueError):
        return ""


def build_prompt(
    skills: list[str],
    plan_file: str,
    current_stage: str,
    next_stage: str,
    freshness_clause: str = "",
) -> str:
    skills_str = " → ".join(skills)
    return (
        f"Run {skills_str} on {plan_file}\n"
        f"Current stage: {current_stage}. Target stage: {next_stage}.\n"
        f"Execute only this stage. Do not proceed to subsequent stages.\n"
        f"Run validations (tests, lint, format checks) in the foreground and "
        f"wait for them to finish — never background validations or end your "
        f"turn while one is still running.{freshness_clause}\n"
        f"Commit your work and update the plan footer to *Stage: {next_stage}* before exiting."
    )


def _session_diff_stats(worktree_dir: str) -> tuple[list[str], int]:
    """Return (files_modified, commits_created) for a worktree relative to main.

    Best-effort: any git failure yields an empty/zero result so telemetry
    emission never blocks a run.
    """
    files_modified: list[str] = []
    commits_created = 0

    diff = subprocess.run(
        ["git", "-C", worktree_dir, "diff", "--name-only", "main...HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if diff.returncode == 0:
        files_modified = [line for line in diff.stdout.splitlines() if line]

    rev = subprocess.run(
        ["git", "-C", worktree_dir, "rev-list", "--count", "main..HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if rev.returncode == 0:
        try:
            commits_created = int(rev.stdout.strip() or 0)
        except ValueError:
            commits_created = 0

    return files_modified, commits_created


def _emit_stage_session(
    logger: telemetry.RunLogger,
    task_id: str,
    plan_file: str,
    agent_cli: str,
    isolation_level: str,
    stage: str,
    stages: list[str] | None,
    worktree_dir: str,
    start_time: str,
    end_time: str,
    exit_code: int,
    usage: dict | None = None,
    session_dir: Path | None = None,
) -> None:
    """Emit one stage telemetry record for a completed agent session.

    ``usage`` is the parsed CLI usage dict (or ``None`` for CLIs without a
    usage mode); it populates ``token_count`` / ``cost_estimate`` on the
    record. Null is the honest value when usage was not measurable.

    ``session_dir`` is the resolved kimi wire dir for the session (``None``
    for non-kimi CLIs and unresolvable sessions); when present, one
    wire-derived ``test_run`` record is appended per extracted test
    invocation, tagged with the session's ``stage``.
    """
    files_modified, commits_created = _session_diff_stats(worktree_dir)
    logger.append_record(
        telemetry.stage_record(
            run_id=logger.run_id,
            task_id=task_id,
            plan_file=plan_file,
            stage=stage,
            agent_cli=agent_cli,
            isolation_level=isolation_level,
            start_time=start_time,
            end_time=end_time,
            exit_code=exit_code,
            files_modified=files_modified,
            commits_created=commits_created,
            stages=stages,
            token_count=usage.get("total_tokens") if usage else None,
            cost_estimate=usage.get("cost_usd") if usage else None,
        ),
        task_id=task_id,
    )
    _emit_wire_test_runs(logger, task_id, plan_file, stage, session_dir)


def _emit_wire_test_runs(
    logger: telemetry.RunLogger,
    task_id: str,
    plan_file: str,
    stage: str,
    session_dir: Path | None,
) -> None:
    """Append one ``test_run`` record per wire-log test invocation.

    Best-effort, mirroring ``_session_diff_stats``: extraction is defensive,
    and any unexpected failure must never block a run.
    """
    if session_dir is None:
        return
    try:
        invocations = wirelog.extract_test_invocations(session_dir)
    except Exception as exc:  # noqa: BLE001
        print(f"   ⚠️  Wire test-run extraction failed (skipping): {exc}")
        return
    for invocation in invocations:
        logger.append_record(
            telemetry.test_run_record(
                run_id=logger.run_id,
                task_id=task_id,
                plan_file=plan_file,
                stage=stage,
                scope=telemetry.classify_test_scope(invocation["command"]),
                test_command=invocation["command"],
                start_time=invocation["start_time"],
                end_time=invocation["end_time"],
                exit_code=invocation["exit_code"],
            ),
            task_id=task_id,
        )


def _usage_aggregates(logger: telemetry.RunLogger) -> tuple[int | None, float | None]:
    """Sum token/cost over this run's stage records; all-null -> ``(None, None)``.

    The ``work-history.jsonl`` copy is queue history, not execution telemetry,
    and is skipped (mirrors the panel's filtering).
    """
    total_tokens = 0
    total_cost = 0.0
    have_tokens = False
    have_cost = False
    for path in logger.run_dir.glob("*.jsonl"):
        if path.name == "work-history.jsonl":
            continue
        for record in telemetry.read_jsonl(path):
            if record.get("type") != "stage":
                continue
            if record.get("token_count") is not None:
                total_tokens += record["token_count"]
                have_tokens = True
            if record.get("cost_estimate") is not None:
                total_cost += record["cost_estimate"]
                have_cost = True
    return (total_tokens if have_tokens else None, total_cost if have_cost else None)


def _task_usage_aggregates(
    logger: telemetry.RunLogger, task_id: str
) -> tuple[int | None, float | None]:
    """Sum token/cost over ``task_id``'s stage records; all-null -> ``(None, None)``.

    Mirrors ``_usage_aggregates`` but filtered to a single task. The result is
    written to the task's ledger record at close and is analytics-only: no
    control path reads it (ADR-031).
    """
    total_tokens = 0
    total_cost = 0.0
    have_tokens = False
    have_cost = False
    path = logger.task_log_path(task_id)
    if not path.exists():
        return (None, None)
    for record in telemetry.read_jsonl(path):
        if record.get("type") != "stage":
            continue
        if record.get("task_id") != task_id:
            continue
        if record.get("token_count") is not None:
            total_tokens += record["token_count"]
            have_tokens = True
        if record.get("cost_estimate") is not None:
            total_cost += record["cost_estimate"]
            have_cost = True
    return (total_tokens if have_tokens else None, total_cost if have_cost else None)


def _load_checking_verdict(task_id: str, kind: str, repo_root: str) -> dict:
    """Read and schema-validate a checking verdict from the evidence home.

    Raises ``FileNotFoundError`` when the verdict is absent and
    ``evidence.VerdictValidationError`` / ``VerdictValueError`` when it is
    malformed.
    """
    path = evidence.evidence_path(
        task_id=task_id,
        kind=kind,
        project_slug=telemetry.derive_project_slug(repo_root),
    )
    record = evidence.read_verdict(path)
    evidence.validate_verdict(record, kind)
    return record


def _emit_test_run_from_verdict(
    logger: telemetry.RunLogger,
    record: dict,
    task_id: str,
    plan_file: str,
    stage: str,
) -> None:
    """Derive a ``test_run`` telemetry record from a passing qa verdict."""
    test_command = record.get("test_command", "")
    logger.append_record(
        telemetry.test_run_record(
            run_id=logger.run_id,
            task_id=task_id,
            plan_file=plan_file,
            stage=stage,
            scope=telemetry.classify_test_scope(test_command),
            test_command=test_command,
            start_time=None,
            end_time=None,
            exit_code=0,
            tests_total=record.get("tests_total"),
            tests_passed=record.get("tests_passed"),
            tests_failed=record.get("tests_failed"),
        ),
        task_id=task_id,
    )


def _require_passing_verdict(
    task_id: str,
    kind: str,
    repo_root: str,
    plan_file: str,
    stage: str,
    logger: telemetry.RunLogger,
) -> bool:
    """Fail-closed evidence gate for a checking stage.

    Returns ``True`` only when a schema-valid verdict with ``verdict: "pass"``
    exists. A missing, malformed, or failing verdict returns ``False`` so the
    caller takes the same failure path as a non-zero session exit. On a passing
    ``qa`` verdict a derived ``test_run`` telemetry record is emitted.
    """
    try:
        record = _load_checking_verdict(task_id, kind, repo_root)
    except FileNotFoundError:
        path = evidence.evidence_path(
            task_id=task_id,
            kind=kind,
            project_slug=telemetry.derive_project_slug(repo_root),
        )
        print(
            f"   ❌ Gate fail-closed: missing {kind} verdict for {task_id} "
            f"(looked at {path})"
        )
        return False
    except (evidence.VerdictValidationError, evidence.VerdictValueError) as exc:
        print(f"   ❌ Gate fail-closed: invalid {kind} verdict for {task_id}: {exc}")
        return False

    if record.get("verdict") != "pass":
        print(
            f"   ❌ Gate fail-closed: {kind} verdict is "
            f"{record.get('verdict')!r} for {task_id}"
        )
        return False

    if kind == "qa":
        _emit_test_run_from_verdict(logger, record, task_id, plan_file, stage)
    return True


def _run_with_live_tee(
    cmd: list[str],
    cwd: str,
    env: dict,
    stall_timeout: float = 300,
) -> tuple[int, str]:
    """Spawn a session: echo its output live, keep a bounded tail buffer.

    Stage sessions run up to ~1 hour, so ``capture_output=True`` is not an
    option — it would silence live agent output for the whole session. This
    reader loop mirrors each line to the terminal as it arrives AND keeps the
    last ~256 KB (usage blocks are emitted at exit). Returns
    ``(exit_code, tail_text)``.

    A watchdog thread monitors stdout silence. If no line arrives for
    ``stall_timeout`` seconds, the process group is terminated and the result
    is classified as a timeout (nsr-01), the same class as a wall-clock kill.
    """
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        start_new_session=True,
    )
    chunks: collections.deque[str] = collections.deque()
    buffered = 0
    last_output = time.monotonic()
    last_output_lock = threading.Lock()
    stop_watchdog = threading.Event()
    cause_lock = threading.Lock()
    cause: str | None = None

    def _watchdog() -> None:
        nonlocal cause
        poll_interval = 0.1
        while not stop_watchdog.wait(timeout=poll_interval):
            if proc.poll() is not None:
                return
            if _shutdown_requested:
                with cause_lock:
                    cause = "shutdown"
                _terminate_process_group(proc, timeout=10)
                return
            with last_output_lock:
                elapsed = time.monotonic() - last_output
            if elapsed > stall_timeout:
                with cause_lock:
                    cause = "stall"
                _terminate_process_group(proc, timeout=10)
                return

    watchdog = threading.Thread(target=_watchdog, daemon=True)
    watchdog.start()

    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            with last_output_lock:
                last_output = time.monotonic()
            sys.stdout.write(line)
            sys.stdout.flush()
            chunks.append(line)
            buffered += len(line)
            while buffered > usage_lib.TAIL_SCAN_BYTES and chunks:
                buffered -= len(chunks.popleft())
    finally:
        stop_watchdog.set()
        watchdog.join(timeout=5)

    exit_code = proc.wait()
    with cause_lock:
        if cause == "stall":
            return -9, "".join(chunks)
    return exit_code, "".join(chunks)


def _spawn_session(
    adapter,
    cmd: list[str],
    worktree_dir: str,
    env: dict,
    stall_timeout: float = 300,
) -> tuple[int, dict | None, Path | None]:
    """Run one agent session, returning ``(exit_code, usage, session_dir)``.

    ``usage`` is parsed from the captured tail only when the adapter declares
    a usage mode; otherwise it is ``None`` and the record keeps null fields.
    ``session_dir`` is the resolved kimi wire dir (``None`` for non-kimi CLIs
    and unresolvable sessions); it feeds wire-log test-run extraction.
    """
    return _spawn_session_with_tail(
        adapter, cmd, worktree_dir, env, stall_timeout=stall_timeout
    )[:3]


def _spawn_session_with_tail(
    adapter,
    cmd: list[str],
    worktree_dir: str,
    env: dict,
    stall_timeout: float = 300,
) -> tuple[int, dict | None, Path | None, str]:
    """Run one agent session, returning ``(exit_code, usage, session_dir, tail)``.

    The bounded ``tail`` is used by the circuit breaker to classify failures.
    The public ``run_stage``/``run_stage_group`` functions call this helper and
    record signatures when a *task* and *backend* are provided.
    """
    exit_code, output = _run_with_live_tee(
        cmd, worktree_dir, env, stall_timeout=stall_timeout
    )
    usage = None
    if adapter.usage_mode is not None:
        usage = usage_lib.parse_usage(adapter.name, output)
    session_dir = None
    if adapter.name == "kimi":
        session_dir = usage_lib.resolve_kimi_session_dir_from_output(output)
    return exit_code, usage, session_dir, output


def run_stage(
    adapter,
    repo_root: str,
    plan_file: str,
    worktree_dir: str,
    skills: list[str],
    current_stage: str,
    next_stage: str,
    task_id: str | None = None,
    run_id: str | None = None,
    verdict_kind: str | None = None,
    task: dict | None = None,
    backend=None,
    stall_timeout: float = 300,
) -> tuple[int, dict | None, Path | None]:
    """Spawn a single stage session, returning ``(exit_code, usage, session_dir)``.

    When *task* and *backend* are provided, a non-zero exit records a failure
    signature on the task's ledger record for the circuit breaker (nsr-03).
    """
    freshness = _qa_freshness_decision(task_id, repo_root, worktree_dir)
    prompt = build_prompt(
        skills, plan_file, current_stage, next_stage,
        freshness_clause=_freshness_clause(freshness),
    )
    cmd = adapter.build_cmd(prompt, workdir=worktree_dir, headless=True)

    env = os.environ.copy()
    env["AET_EXECUTION_MODE"] = "unattended"
    env["AET_ORCHESTRATOR_PID"] = str(os.getpid())
    if freshness:
        env["AET_QA_FRESHNESS"] = freshness
    if task_id is not None:
        env["AET_TASK_ID"] = task_id
    if run_id is not None:
        env["AET_RUN_ID"] = run_id
    if task_id is not None and verdict_kind is not None:
        env["AET_EVIDENCE_PATH"] = str(
            evidence.evidence_path(
                task_id=task_id,
                kind=verdict_kind,
                project_slug=telemetry.derive_project_slug(repo_root),
            )
        )

    print(f"   Invoking: {' '.join(cmd)}")
    exit_code, usage, session_dir, output = _spawn_session_with_tail(
        adapter, cmd, worktree_dir, env, stall_timeout=stall_timeout
    )
    if exit_code != 0 and task is not None:
        _record_failure_on_task(
            backend,
            task,
            _classify_failure(
                exit_code=exit_code,
                tail=output,
                stage=current_stage,
                verdict_recorded=verdict_kind is not None,
                shutdown=_shutdown_requested,
                killed_by_timeout=exit_code == -9,
            ),
            current_stage,
            output,
        )
    return exit_code, usage, session_dir


def build_stage_group_prompt(
    plan_file: str,
    stages: list[WorkflowStage],
    workflow: Workflow,
    freshness_clause: str = "",
) -> str:
    """Build a compound prompt for running multiple stages in one session.

    Each stage block preserves the single-stage prompt format so the agent
    can execute them sequentially, committing and updating the plan footer
    between stages. Successors resolve through the workflow's list order.
    """
    preamble = (
        "Execute the following consecutive pipeline stages in order. "
        "Complete each stage (including its commit and plan-footer update) "
        "before starting the next. Do not proceed past the final stage listed. "
        "Run validations (tests, lint, format checks) in the foreground and "
        "wait for them to finish — never background validations or end your "
        "turn while one is still running." + freshness_clause
    )
    blocks = [preamble]
    for stage in stages:
        next_stage = workflow.next_stage(stage.name) or stage.name
        skills_str = " → ".join(stage.skills)
        blocks.append(
            f"Run {skills_str} on {plan_file}\n"
            f"Current stage: {stage.name}. Target stage: {next_stage}.\n"
            f"Execute only this stage. Do not proceed to subsequent stages.\n"
            f"Commit your work and update the plan footer to *Stage: {next_stage}* before exiting."
        )
    return "\n\n".join(blocks)


def run_stage_group(
    adapter,
    repo_root: str,
    plan_file: str,
    worktree_dir: str,
    stages: list[WorkflowStage],
    task_id: str | None = None,
    run_id: str | None = None,
    *,
    workflow: Workflow,
    task: dict | None = None,
    backend=None,
    stall_timeout: float = 300,
) -> tuple[int, dict | None, Path | None]:
    """Spawn one session that runs every stage in the group sequentially.

    Returns ``(exit_code, usage, session_dir)``; usage covers the whole group
    session and ``session_dir`` is the resolved kimi wire dir (``None`` for
    non-kimi CLIs and unresolvable sessions). When *task* and *backend* are
    provided, a non-zero exit records a failure signature on the task's ledger
    record using the first stage's name (nsr-03).
    """
    freshness = _qa_freshness_decision(task_id, repo_root, worktree_dir)
    prompt = build_stage_group_prompt(
        plan_file, stages, workflow, freshness_clause=_freshness_clause(freshness)
    )
    cmd = adapter.build_cmd(prompt, workdir=worktree_dir, headless=True)

    env = os.environ.copy()
    env["AET_EXECUTION_MODE"] = "unattended"
    env["AET_ORCHESTRATOR_PID"] = str(os.getpid())
    if freshness:
        env["AET_QA_FRESHNESS"] = freshness
    if task_id is not None:
        env["AET_TASK_ID"] = task_id
    if run_id is not None:
        env["AET_RUN_ID"] = run_id
    if task_id is not None:
        # Publish the canonical verdict path per evidence-bound stage so
        # writers and the gate share one derivation in group sessions too
        # (ADR-023). Same formula run_stage uses for AET_EVIDENCE_PATH.
        project_slug = telemetry.derive_project_slug(repo_root)
        for stage in stages:
            if stage.evidence is None:
                continue
            env[evidence.evidence_path_env_var(stage.evidence)] = str(
                evidence.evidence_path(
                    task_id=task_id,
                    kind=stage.evidence,
                    project_slug=project_slug,
                )
            )

    print(f"   Invoking group: {' '.join(cmd)}")
    exit_code, usage, session_dir, output = _spawn_session_with_tail(
        adapter, cmd, worktree_dir, env, stall_timeout=stall_timeout
    )
    if exit_code != 0 and task is not None:
        _record_failure_on_task(
            backend,
            task,
            _classify_failure(
                exit_code=exit_code,
                tail=output,
                stage=stages[0].name,
                verdict_recorded=False,
                shutdown=_shutdown_requested,
                killed_by_timeout=exit_code == -9,
            ),
            stages[0].name,
            output,
        )
    return exit_code, usage, session_dir


def stage_enabled(stage: WorkflowStage, plan_fm: dict) -> bool:
    """Return True when ``stage`` should run for the given plan frontmatter.

    A stage without a ``gate_key`` always runs. A gated stage runs unless the
    plan frontmatter sets its gate key to ``skipped``; a missing key defaults
    to ``required`` (fail-safe — the stage runs). Routing is decided once at
    plan time and enforced here as pure data (ADR-020).
    """
    if not stage.gate_key:
        return True
    return plan_fm.get(stage.gate_key) != "skipped"


def _report_gate_decision(stage: WorkflowStage, plan_fm: dict, enabled: bool) -> None:
    """Print how a gated stage's run/skip decision was resolved.

    The source is ``frontmatter`` when the plan sets the gate key and
    ``default`` when the key is absent (fail-safe run). Ungated stages and
    frontmatter-directed runs are silent.
    """
    if not stage.gate_key:
        return
    if enabled:
        if stage.gate_key not in plan_fm:
            print(
                f"   🔒 Gate {stage.gate_key} unset; running {stage.name} (source: default)"
            )
        return
    print(
        f"   ⏭️  Skipping gated stage: {stage.name} "
        f"({stage.gate_key}=skipped, source: frontmatter)"
    )


def process_task(
    task: dict,
    repo_root: str,
    adapter,
    isolation: str,
    logger: telemetry.RunLogger | None = None,
    worktree_dir: str | None = None,
    workflow: Workflow | None = None,
    backend=None,
    stall_timeout: float = 300,
) -> bool:
    """Process a single task through all its stage groups.

    The stage sequence, skill bindings, evidence kinds, and session grouping
    come from the workflow file (``workflow:`` plan frontmatter key, default
    ``software``) — loaded once per task and threaded through every decision.
    """
    if logger is None:
        logger = telemetry.RunLogger(repo_root)
    task_id = task["id"]
    plan_file = task.get("plan_file", "")
    if not os.path.isabs(plan_file):
        plan_file = os.path.join(repo_root, plan_file)

    print(f"▶️  Task: {task.get('title', task_id)} ({task_id})")
    print(f"   Plan: {plan_file}")

    # Create or reuse worktree
    if worktree_dir is None:
        worktree_dir = create_worktree(repo_root, task_id)
    copy_untracked_files(repo_root, worktree_dir)

    # Warm up configured worktree dependencies.
    warmup_results = prepare_worktree_dependencies(repo_root, worktree_dir)
    for result in warmup_results:
        name = result["name"]
        if result["status"] == "created":
            print(f"   🔗 Warmed dependency: {name}")
        elif result["status"] == "skipped":
            print(f"   ℹ️  Dependency skipped: {name} ({result['message']})")
        elif result["status"] == "failed":
            print(f"   ⚠️  Dependency warmup failed: {name} ({result['message']})")
    print(f"   Worktree: {worktree_dir}")

    # Emit telemetry for any failed dependency warmups.
    for result in warmup_results:
        if result["status"] != "failed":
            continue
        logger.append_record(
            telemetry.environment_issue_record(
                run_id=logger.run_id,
                task_id=task_id,
                plan_file=plan_file,
                issue_type="missing_dependency",
                dependency=result.get("target", result.get("name", "unknown")),
                message=f"Dependency warmup failed: {result['message']}",
            ),
            task_id=task_id,
        )

    # Use the worktree copy of the plan file for stages and verification.
    plan_file = os.path.join(worktree_dir, os.path.relpath(plan_file, repo_root))

    # Fail loudly if the plan is missing in the worktree. A missing plan usually
    # means the base branch (origin/main) is stale relative to the plan commit.
    if not os.path.exists(plan_file):
        print(
            "   ❌ Plan not found in worktree — base may be stale; "
            "ensure the plan is committed and pushed to origin/main"
        )
        return False

    # Gate routing resolves against the plan frontmatter — parse it once per
    # task so every stage decision below is a pure data lookup.
    plan_fm = plan_parser.parse_frontmatter(Path(plan_file))

    # The workflow file is the engine's source of truth for stage sequencing.
    # A missing or invalid file fails the run loudly at task start — there is
    # no silent fallback to a baked-in sequence; the packaged default is the
    # fallback (ADR-020).
    if workflow is None:
        workflow_name = plan_fm.get("workflow") or "software"
        try:
            workflow = load_workflow(repo_root, workflow_name)
        except WorkflowError as exc:
            print(f"   ❌ {exc}")
            return False

    # Determine current stage from the task record; footer is only a breadcrumb.
    current_stage = get_current_stage(task, plan_file, workflow.entry_stage)

    # A terminal or unknown stage with no commits means the plan footer (or a
    # stale worktree) is lying. Fail loudly instead of marking the task done.
    if current_stage not in workflow.stage_map:
        ok, msg = verify_branch_has_commits(worktree_dir)
        if not ok:
            print(f"   ❌ Stage '{current_stage}' is not a runnable pipeline stage and {msg}")
            return False

    # Allow the plan frontmatter to override the CLI isolation default.
    task_isolation = effective_isolation(plan_file, isolation)
    if task_isolation != isolation:
        print(f"   📋 Plan isolation: {task_isolation}")

    # Group stages by isolation level
    groups = workflow.session_groups(task_isolation)
    agent_invoked = False

    for group in groups:
        if _shutdown_requested:
            print(f"   ⚠️  Shutdown requested, stopping task {task_id}")
            return False

        # Find the first stage in this group that hasn't been completed yet.
        start_idx = None
        for i, stage in enumerate(group):
            if stage.name == current_stage:
                start_idx = i
                break

        if start_idx is None:
            # All stages in this group are done; move to the next group.
            continue

        remaining = group[start_idx:]

        # For standard isolation, try to run the remaining stages in one session.
        if task_isolation == "standard":
            decisions = [(s, stage_enabled(s, plan_fm)) for s in remaining]
            runnable = [s for s, ok in decisions if ok]
            if len(runnable) != 1:
                # The per-stage walk below only runs when exactly one stage is
                # runnable; in every other case this is where skip decisions
                # are final, so report them here.
                for s, ok in decisions:
                    _report_gate_decision(s, plan_fm, ok)
            if runnable and len(runnable) > 1:
                expected_final = workflow.next_stage(runnable[-1].name) or runnable[-1].name
                stage_span = [s.name for s in runnable]
                print(
                    f"   Stage group: {' → '.join(stage_span)} → {expected_final}"
                )

                start_time = telemetry.iso_now()
                exit_code, usage, session_dir = run_stage_group(
                    adapter,
                    repo_root,
                    plan_file,
                    worktree_dir,
                    runnable,
                    task_id=task_id,
                    run_id=logger.run_id,
                    workflow=workflow,
                    task=task,
                    backend=backend,
                    stall_timeout=stall_timeout,
                )
                end_time = telemetry.iso_now()
                _emit_stage_session(
                    logger,
                    task_id,
                    plan_file,
                    adapter.name,
                    task_isolation,
                    expected_final,
                    stage_span,
                    worktree_dir,
                    start_time,
                    end_time,
                    exit_code,
                    usage=usage,
                    session_dir=session_dir,
                )
                agent_invoked = True
                if exit_code != 0:
                    print(f"   ❌ Stage group failed with exit code {exit_code}")
                    return False

                # Verify the group session produced commits.
                ok, msg = verify_branch_has_commits(worktree_dir)
                if not ok:
                    print(f"   ❌ Stage group verification failed: {msg}")
                    return False

                # Fail-closed evidence gates: every stage in the group span
                # with an evidence binding must have a schema-valid passing
                # verdict. Group advancement is determined by evidence, not
                # the plan footer (which is a breadcrumb only).
                for stage in runnable:
                    kind = stage.evidence
                    if kind is None:
                        continue
                    target = workflow.next_stage(stage.name) or stage.name
                    if not _require_passing_verdict(
                        task_id, kind, repo_root, plan_file, target, logger
                    ):
                        return False

                if not _record_stage(task, expected_final, repo_root):
                    print(f"   ❌ Could not record stage {expected_final} for {task_id}")
                    return False

                ok, msg = verify_stage_advancement(
                    task.get("stage"), worktree_dir, expected_final
                )
                if not ok:
                    print(f"   ❌ Stage group advancement verification failed: {msg}")
                    return False

                print(f"   ✅ Stage group advanced to {expected_final}")
                current_stage = expected_final
                continue
            elif not runnable:
                # All remaining stages are gated skips; jump to the end of the group.
                current_stage = workflow.next_stage(remaining[-1].name) or remaining[-1].name
                continue

        # Per-stage execution: used for minimal/full isolation and for single-stage
        # groups. Standard multi-stage groups fail closed on missing evidence
        # rather than falling back here.
        while True:
            # Find the first stage in this group that hasn't been completed yet.
            target_stage = None
            for stage in group:
                if stage.name == current_stage:
                    target_stage = stage
                    break

            if not target_stage:
                # All stages in this group are done; break to next group.
                break

            # Gated stages resolve from the plan frontmatter — pure data,
            # no runtime judgment.
            enabled = stage_enabled(target_stage, plan_fm)
            _report_gate_decision(target_stage, plan_fm, enabled)
            if not enabled:
                current_stage = workflow.next_stage(target_stage.name) or current_stage
                continue

            next_stage_name = workflow.next_stage(target_stage.name) or current_stage
            skills = target_stage.skills

            if not skills:
                # Terminal stage (skill-less, e.g. synced).
                current_stage = next_stage_name
                continue

            print(f"   Stage: {target_stage.name} → {next_stage_name} ({' → '.join(skills)})")

            kind = target_stage.evidence
            start_time = telemetry.iso_now()
            exit_code, usage, session_dir = run_stage(
                adapter,
                repo_root,
                plan_file,
                worktree_dir,
                skills,
                target_stage.name,
                next_stage_name,
                task_id=task_id,
                run_id=logger.run_id,
                verdict_kind=kind,
                task=task,
                backend=backend,
                stall_timeout=stall_timeout,
            )
            end_time = telemetry.iso_now()
            _emit_stage_session(
                logger,
                task_id,
                plan_file,
                adapter.name,
                task_isolation,
                next_stage_name,
                None,
                worktree_dir,
                start_time,
                end_time,
                exit_code,
                usage=usage,
                session_dir=session_dir,
            )
            agent_invoked = True

            if exit_code != 0:
                print(f"   ❌ Stage failed with exit code {exit_code}")
                return False

            # Verify the stage produced commits before persisting the advance.
            ok, msg = verify_branch_has_commits(worktree_dir)
            if not ok:
                print(f"   ❌ Stage verification failed: {msg}")
                return False

            # Fail-closed evidence gate for checking stages (qa/review/cso/sync-docs).
            if kind is not None and not _require_passing_verdict(
                task_id, kind, repo_root, plan_file, next_stage_name, logger
            ):
                return False

            # Record the advanced stage in the task record.
            if not _record_stage(task, next_stage_name, repo_root):
                print(f"   ❌ Could not record stage {next_stage_name} for {task_id}")
                return False

            # Confirm the recorded stage matches the expected target.
            ok, msg = verify_stage_advancement(
                task.get("stage"), worktree_dir, next_stage_name
            )
            if not ok:
                print(f"   ❌ Stage verification failed: {msg}")
                return False

            print(f"   ✅ Stage advanced to {next_stage_name}")
            current_stage = next_stage_name

    # If the orchestrator never actually invoked an agent, the only legitimate
    # success is a task whose branch already contains work (e.g. a resumed
    # terminal stage). An empty branch here means a stale footer or corrupt
    # worktree fooled us into skipping all stages.
    if not agent_invoked:
        ok, msg = verify_branch_has_commits(worktree_dir)
        if not ok:
            print(f"   ❌ Task completed without running any stage and {msg}")
            return False

    print(f"   ✅ Task complete: {task_id}")
    return True


def get_next_ready_task(queue: list[dict]) -> dict | None:
    """Return the first task whose stored state is ``ready``."""
    return get_next_unblocked(queue)


def has_pending_tasks(queue: list[dict]) -> bool:
    """Return True if any task is still actionable (stored non-terminal)."""
    return queue_has_pending_tasks(queue)


# States that can still make progress on their own inside the batch loop: a
# ``ready`` task will be spawned on the next pass, and an ``in_progress`` task
# has a live child. Anything else non-terminal (awaiting_merge/blocked/planned/
# failed) is stranded until an external actor (record-merge, curation, a human)
# moves it, so the batch must exit instead of spinning.
_BATCH_ACTIONABLE_STATES = frozenset({"ready", "in_progress"})

# Stranded non-terminal states, in the order they should appear in the leftover
# report. Terminal states (merged/abandoned) are excluded: a fully terminal
# queue is a clean completion, not a leftover. ``quarantined`` is non-actionable
# and must be surfaced so a human can un-quarantine it (nsr-02).
_BATCH_LEFTOVER_STATES = ("awaiting_merge", "blocked", "planned", "failed", "quarantined")
_BATCH_LEFTOVER_LABELS = {
    "awaiting_merge": "awaiting merge",
    "blocked": "blocked",
    "planned": "planned",
    "failed": "failed",
    "quarantined": "quarantined",
}


def has_actionable_tasks(queue: list[dict]) -> bool:
    """Return True if any stored task is ``ready`` or ``in_progress``."""
    return any(current_state(task) in _BATCH_ACTIONABLE_STATES for task in queue)


def leftover_counts(queue: list[dict]) -> dict[str, int]:
    """Count stranded non-terminal tasks by state (zero counts omitted)."""
    counts = {state: 0 for state in _BATCH_LEFTOVER_STATES}
    for task in queue:
        state = current_state(task)
        if state in counts:
            counts[state] += 1
    return {state: counts[state] for state in _BATCH_LEFTOVER_STATES if counts[state]}


def format_leftover_report(counts: dict[str, int]) -> str:
    """Render leftover counts as ``N awaiting merge, M blocked, ...``."""
    parts = [
        f"{counts[state]} {_BATCH_LEFTOVER_LABELS[state]}"
        for state in _BATCH_LEFTOVER_STATES
        if state in counts
    ]
    return ", ".join(parts)


def _classify_failure(
    *,
    exit_code: int,
    tail: str,
    stage: str,
    verdict_recorded: bool,
    shutdown: bool,
    killed_by_timeout: bool,
) -> failure_lib.FailureClass:
    """Classify a finished session using the nsr-01 taxonomy."""
    return failure_lib.classify(
        exit_code=exit_code,
        tail=tail,
        stage=stage,
        verdict_recorded=verdict_recorded,
        shutdown=shutdown,
        killed_by_timeout=killed_by_timeout,
    )


def _record_failure_on_task(
    backend,
    task: dict,
    failure_class: failure_lib.FailureClass,
    stage: str,
    tail: str,
    timestamp: str | None = None,
) -> str | None:
    """Record a failure signature on *task* when it is countable.

    Stores the signature together with the deterministic class, stage, and a
    bounded tail preview so the finalize path can consult a triage session
    without re-running the failed stage (nsr-04). ``canceled`` failures are
    skipped (ADR-030). Returns the computed signature when recorded, otherwise
    ``None``.
    """
    sig = failure_lib.signature(stage=stage, tail=tail)
    if not breaker.append_failure_if_countable(task, failure_class, sig, timestamp=timestamp):
        return None
    # Enrich the latest signature entry with triage inputs. The breaker only
    # cares about ``signature``; extra keys are ignored for counting.
    entry = task.get("failure_signatures", [])[-1]
    entry["class"] = failure_class.value
    entry["stage"] = stage
    entry["tail_preview"] = tail[-1500:] if tail else ""
    # Persist the updated task record if a backend is available.
    if backend is not None:
        queue = backend.load()["queue"]
        for qt in queue:
            if qt.get("id") == task.get("id"):
                qt["failure_signatures"] = task.get("failure_signatures", [])
                break
        backend.save(queue)
    return sig


# Fail-closed fallback when the triage session errors or returns an unparseable
# verdict. The deterministic classifier's class drives the default action.
_TRIAGE_DEFAULT_ACTIONS: dict[str, str] = {
    failure_lib.FailureClass.ENVIRONMENT.value: "requeue",
    failure_lib.FailureClass.FLAKY.value: "requeue",
    failure_lib.FailureClass.TIMEOUT.value: "requeue",
    failure_lib.FailureClass.DESIGN.value: "quarantine",
    failure_lib.FailureClass.CANCELED.value: "quarantine",
}


def _consult_triage_session(
    adapter,
    repo_root: str,
    worktree_dir: str,
    *,
    task_id: str,
    stage: str,
    failure_class: failure_lib.FailureClass,
    tail: str,
    signature: str,
    stall_timeout: float = 300,
) -> dict | None:
    """Spawn a triage session and return its parsed verdict, or ``None``.

    A ``None`` result (spawn error, non-zero exit, or unparseable output) tells
    the caller to fall back to the deterministic classifier default.
    """
    prompt = triage.build_triage_prompt(
        task_id=task_id,
        stage=stage,
        failure_class=failure_class.value,
        tail=tail,
        signature=signature,
    )
    try:
        cmd = adapter.build_cmd(prompt, workdir=worktree_dir, headless=True)
    except Exception:  # pragma: no cover - defensive fallback
        return None
    env = os.environ.copy()
    env["AET_EXECUTION_MODE"] = "unattended"
    env["AET_ORCHESTRATOR_PID"] = str(os.getpid())
    try:
        exit_code, _usage, _session_dir, output = _spawn_session_with_tail(
            adapter, cmd, worktree_dir, env, stall_timeout=stall_timeout
        )
    except Exception:  # pragma: no cover - defensive fallback
        return None
    if exit_code != 0:
        return None
    return triage.parse_triage_verdict(output)


def _mark_quarantined(
    backend, queue_file: str, task_id: str, from_state: str | None
) -> bool:
    """Mark a task as quarantined through the canonical state transition.

    Returns ``True`` when the transition succeeded.
    """
    if from_state is None:
        from_state = "in_progress"
    aet_state_bin = str(_SCRIPT_DIR / "aet_state.py")
    result = subprocess.run(
        [
            sys.executable,
            aet_state_bin,
            "transition",
            task_id,
            from_state,
            "quarantined",
            queue_file,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"   🚫 {task_id} quarantined (circuit breaker)")
        return True
    print(f"   ⚠️  Could not transition {task_id} to quarantined: {result.stderr.strip()}")
    return False


def _mark_failed(
    backend, queue_file: str, task_id: str, from_state: str | None
) -> None:
    """Mark a task as failed, preferring the canonical state transition.

    Routes through ``aet-state transition`` so the stored ``state`` field is
    updated. If the transition cannot be applied because the task has already
    moved, the queue is re-read under ``queue_lock`` and the transition is
    retried from the current state. No direct ``task["state"]`` assignment is
    ever performed; if no legal transition to ``failed`` exists (e.g. the task
    is already terminal), the state is left untouched and the failure is logged.
    """
    if from_state is None:
        from_state = "in_progress"
    aet_state_bin = str(_SCRIPT_DIR / "aet_state.py")
    result = subprocess.run(
        [
            sys.executable,
            aet_state_bin,
            "transition",
            task_id,
            from_state,
            "failed",
            queue_file,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"   ⚠️  Could not transition {task_id} to failed: {result.stderr.strip()}")
        with queue_lock(queue_file):
            data = backend.load()
            queue = data["queue"]
            task = next((t for t in queue if t.get("id") == task_id), None)
            if task is None:
                print(f"   ⚠️  Task {task_id} disappeared from queue; not marking failed")
                return
            current = current_state(task)
            if current == "failed":
                return
            if current is None or "failed" not in LEGAL_TRANSITIONS.get(current, set()):
                print(
                    f"   🚫  Cannot mark {task_id} as failed from state '{current}' "
                    "(no legal transition); leaving state untouched"
                )
                return
            retry = subprocess.run(
                [
                    sys.executable,
                    aet_state_bin,
                    "transition",
                    task_id,
                    current,
                    "failed",
                    queue_file,
                ],
                capture_output=True,
                text=True,
            )
            if retry.returncode != 0:
                print(
                    f"   🚫  Could not retry transition {task_id} {current} -> failed: "
                    f"{retry.stderr.strip()}; leaving state untouched"
                )


def _maybe_auto_merge(task: dict, queue_file: str, repo_root: str) -> bool:
    """Auto-merge ``task`` if its class is enabled and meets the threshold.

    Returns True when the task was auto-merged through the record-merge closure
    path. Returns False when the task should be left for a human decision at
    the desk (the default, since the shipped policy is empty).
    """
    try:
        policy_path = os.path.join(repo_root, track_record.DEFAULT_POLICY_PATH)
        policy = track_record.load_policy(policy_path)
    except Exception:  # pragma: no cover - defensive fallback
        return False
    if not track_record.is_eligible_for_auto_merge(task, policy=policy):
        return False
    return track_record.perform_auto_merge(task, queue_file, repo_root)


def _write_task_cost(
    backend,
    queue_file: str,
    task_id: str,
    logger: telemetry.RunLogger | None,
) -> None:
    """Roll up per-task cost from telemetry and write it to the ledger record.

    Null is preserved (analytics-only): when every stage record was null, the
    field is omitted rather than written as a pair of nulls.
    """
    if logger is None:
        return
    queue = backend.load()["queue"]
    task = next((t for t in queue if t.get("id") == task_id), None)
    if task is None:
        return
    tokens, usd = _task_usage_aggregates(logger, task_id)
    if tokens is not None or usd is not None:
        task["cost"] = {"tokens": tokens, "usd": usd}
        backend.save(queue)


def _attach_delivered_size(task: dict, repo_root: str) -> bool:
    """Record delivered diff size on the task record when the merge commit is known.

    The measurement is best-effort and analytics-only: any failure is recorded
    as a ``failed`` status with a reason and the task continues to settle. If
    no ``merge_commit`` is present yet (normal awaiting_merge closure), the
    field is left for ``append_history_record`` to populate at terminal seal
    time.

    Returns ``True`` when the task record was mutated.
    """
    merge_commit = task.get("merge_commit")
    if not merge_commit:
        return False
    size_info = plan_size.delivered_size(repo_root, merge_commit)
    plan_path = task.get("plan_file")
    declared_size: str | None = None
    if plan_path:
        try:
            plan_path_obj = Path(plan_path)
            if not plan_path_obj.is_absolute():
                plan_path_obj = Path(repo_root) / plan_path_obj
            declared_size = plan_parser.parse_frontmatter(plan_path_obj).get("size")
        except Exception:  # noqa: BLE001
            declared_size = None
    task["delivered_size"] = {**size_info, "declared_size": declared_size}
    return True


def _finalize_task(
    backend,
    queue_file: str,
    task_id: str,
    ret: int,
    repo_root: str | None = None,
    logger: telemetry.RunLogger | None = None,
    on_failure: str = "triage",
    adapter=None,
    worktree_dir: str | None = None,
) -> dict[str, int | bool]:
    """Finalize a single task after its child process exits.

    State changes go through ``aet-state transition``; the orchestrator avoids
    blind ``backend.save`` calls for state. The one exception is the analytics-
    only ``cost`` field, which is rolled up from stage telemetry and written to
    the task's ledger record before the transition so it is preserved when the
    task is later sealed. No control path reads ``cost`` (ADR-031).
    """
    aet_state_bin = str(_SCRIPT_DIR / "aet_state.py")
    repo_root = repo_root or os.path.dirname(os.path.dirname(queue_file))
    if ret == 0:
        queue = backend.load()["queue"]
        task = next((t for t in queue if t.get("id") == task_id), None)
        # A successful child that produced no commits is a false completion.
        # Fail the task rather than promoting an empty branch to awaiting_merge.
        if task:
            worktree_rel = task.get("worktree")
            if worktree_rel:
                ok, msg = verify_branch_has_commits(os.path.join(repo_root, worktree_rel))
                if not ok:
                    print(f"   ❌ {task_id} succeeded but produced no commits: {msg}")
                    _mark_failed(backend, queue_file, task_id, current_state(task))
                    return {"successes": 0, "failures": 1, "stop_spawn": True}
        from_state = current_state(task) if task else "in_progress"
        if from_state == "awaiting_merge":
            return {"successes": 1, "failures": 0, "stop_spawn": False}
        # Record delivered diff size when the merge commit is already known
        # (e.g. auto-merge closure). Normal awaiting_merge closure defers the
        # measurement to terminal seal time in ``append_history_record``.
        if task and _attach_delivered_size(task, repo_root):
            backend.save(queue)
        # Roll up per-task cost from this run's telemetry and write it to the
        # ledger record before transition.
        _write_task_cost(backend, queue_file, task_id, logger)
        if task and _maybe_auto_merge(task, queue_file, repo_root):
            return {"successes": 1, "failures": 0, "stop_spawn": False}
        print(f"   ✅ {task_id} awaiting merge")
        result = subprocess.run(
            [
                sys.executable,
                aet_state_bin,
                "transition",
                task_id,
                from_state,
                "awaiting_merge",
                queue_file,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(
                f"   ⚠️  Could not transition {task_id} to awaiting_merge: {result.stderr.strip()}"
            )
            _mark_failed(backend, queue_file, task_id, from_state)
            return {"successes": 0, "failures": 1, "stop_spawn": True}
        return {"successes": 1, "failures": 0, "stop_spawn": False}

    print(f"   ❌ {task_id} failed (exit {ret})")
    queue = backend.load()["queue"]
    task = next((t for t in queue if t.get("id") == task_id), None)
    from_state = current_state(task) if task else "in_progress"

    # Roll up per-task cost for incident tasks too (nsr-07).
    _write_task_cost(backend, queue_file, task_id, logger)

    # Stall/task-timeout failures are terminal: leave the task failed rather
    # than requeue it. The child process records the TIMEOUT class on the
    # task's failure_signatures ledger; read that back after the reload above.
    last_entry = (task.get("failure_signatures") or [])[-1:] if task else []
    entry = last_entry[0] if last_entry else {}
    if entry.get("class") == failure_lib.FailureClass.TIMEOUT.value:
        print(f"   ⏱️  {task_id} killed by timeout; leaving failed")
        _mark_failed(backend, queue_file, task_id, from_state)
        return {"successes": 0, "failures": 1, "stop_spawn": False}

    # Circuit breaker has absolute precedence over triage routing (nsr-03).
    if task and breaker.should_quarantine_task(task):
        if _mark_quarantined(backend, queue_file, task_id, from_state):
            return {"successes": 0, "failures": 1, "stop_spawn": True}

    # Establish the canonical failed state. All non-breaker failure modes route
    # from here so transitions stay legal (failed -> ready, failed -> quarantined).
    _mark_failed(backend, queue_file, task_id, from_state)
    queue = backend.load()["queue"]
    task = next((t for t in queue if t.get("id") == task_id), None)
    failed_state = current_state(task) if task else "failed"

    if on_failure == "halt":
        return {"successes": 0, "failures": 1, "stop_spawn": True}

    if on_failure == "continue":
        return {"successes": 0, "failures": 1, "stop_spawn": False}

    # on_failure == "triage" (default).
    last_entry = (task.get("failure_signatures") or [])[-1:] if task else []
    entry = last_entry[0] if last_entry else {}
    failure_class_name = entry.get("class", failure_lib.FailureClass.ENVIRONMENT.value)
    stage = entry.get("stage", "")
    tail = entry.get("tail_preview", "")
    signature = entry.get("signature", "")

    verdict = None
    if adapter is not None and worktree_dir is not None:
        try:
            failure_class = failure_lib.FailureClass(failure_class_name)
        except ValueError:
            failure_class = failure_lib.FailureClass.ENVIRONMENT
        verdict = _consult_triage_session(
            adapter,
            repo_root,
            worktree_dir,
            task_id=task_id,
            stage=stage,
            failure_class=failure_class,
            tail=tail,
            signature=signature,
        )

    action = verdict.get("action") if verdict else None
    if action is None:
        # Fail-closed: unparseable or errored triage falls back to the
        # deterministic classifier default (nsr-01).
        action = _TRIAGE_DEFAULT_ACTIONS.get(failure_class_name, "requeue")
        print(f"   ⚠️  Triage for {task_id} failed closed; using {action} ({failure_class_name})")

    if action == "quarantine":
        if _mark_quarantined(backend, queue_file, task_id, failed_state):
            return {"successes": 0, "failures": 1, "stop_spawn": True}
        # If quarantine transition fails, fall through to requeue/failed.

    # action == "requeue" (or quarantine transition failed): failed -> ready.
    result = subprocess.run(
        [
            sys.executable,
            aet_state_bin,
            "transition",
            task_id,
            failed_state,
            "ready",
            queue_file,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"   🔄 {task_id} requeued")
        return {"successes": 0, "failures": 0, "stop_spawn": False}
    print(
        f"   ⚠️  Could not transition {task_id} to ready: {result.stderr.strip()}; leaving failed"
    )
    return {"successes": 0, "failures": 1, "stop_spawn": False}


def run_batch(args: argparse.Namespace, adapter) -> int:
    """Run batch mode from queue file."""
    queue_file = args.queue_file
    repo_root = args.repo_root
    max_jobs = min(args.max_jobs, 8)
    backend = _make_backend(queue_file)
    breaker_store = breaker.BreakerStore(repo_root)
    systemic_tally = breaker_store.load()

    logger = telemetry.RunLogger(repo_root, run_id=getattr(args, "run_id", None))
    start_time = telemetry.iso_now()
    task_ids: list[str] = []

    try:
        queue = backend.load()["queue"]
    except QueueIntegrityError as exc:
        # Fail closed before spawning anything: a tampered queue must be
        # repaired explicitly (audit / heal --apply), not crashed into with a
        # traceback mid-batch (ADR-024).
        print(f"⛔ {exc}", file=sys.stderr)
        return 1
    if not queue:
        print("✅ Queue is empty.")
        end_time = telemetry.iso_now()
        logger.write_last_run(
            telemetry.run_summary_record(
                run_id=logger.run_id,
                start_time=start_time,
                end_time=end_time,
                tasks_spawned=0,
                tasks_succeeded=0,
                tasks_failed=0,
                outcome="success",
                exit_code=0,
                task_ids=[],
                final_stage=None,
            )
        )
        print(f"   📁 Telemetry: {logger.run_dir}")
        return 0

    # If a prior shift already tripped the systemic breaker, stop before
    # spawning anything. The tally persists across shifts (R-6).
    if breaker.systemic_tripped(systemic_tally):
        report = breaker.systemic_report(systemic_tally)
        print(f"⛔ {report}")
        end_time = telemetry.iso_now()
        logger.write_last_run(
            telemetry.run_summary_record(
                run_id=logger.run_id,
                start_time=start_time,
                end_time=end_time,
                tasks_spawned=0,
                tasks_succeeded=0,
                tasks_failed=0,
                outcome="failure",
                exit_code=1,
                task_ids=[],
                final_stage=None,
            )
        )
        print(f"   📁 Telemetry: {logger.run_dir}")
        return 1

    print("🚀 Batch orchestrator starting")
    print(f"   Queue: {queue_file}")
    print(f"   Concurrency: {max_jobs}")
    print(f"   Telemetry: {logger.run_dir}")
    print()

    # Check main hygiene
    if not enforce_main_hygiene(repo_root):
        end_time = telemetry.iso_now()
        logger.write_last_run(
            telemetry.run_summary_record(
                run_id=logger.run_id,
                start_time=start_time,
                end_time=end_time,
                tasks_spawned=0,
                tasks_succeeded=0,
                tasks_failed=0,
                outcome="failure",
                exit_code=1,
                task_ids=[],
                final_stage=None,
            )
        )
        return 1

    # Declare that this run owns the queue so out-of-band mutators refuse, and
    # ensure every subprocess inherits the run id for the lease check.
    os.environ["AET_RUN_ID"] = logger.run_id

    running: dict[str, subprocess.Popen] = {}
    spawn_times: dict[str, float] = {}
    successes = 0
    failures = 0
    stop_spawn = False
    last_heartbeat = time.monotonic()
    summary_written = False
    leftover_report: dict[str, int] = {}
    task_timeout = getattr(args, "task_timeout", 3600)
    heartbeat_interval = getattr(args, "heartbeat_interval", 60)

    def _write_summary(outcome: str, exit_code: int) -> None:
        nonlocal summary_written
        if summary_written:
            return
        summary_written = True
        end_time = telemetry.iso_now()
        total_tokens, total_cost_usd = _usage_aggregates(logger)
        logger.write_last_run(
            telemetry.run_summary_record(
                run_id=logger.run_id,
                start_time=start_time,
                end_time=end_time,
                tasks_spawned=len(task_ids),
                tasks_succeeded=successes,
                tasks_failed=failures,
                outcome=outcome,
                exit_code=exit_code,
                task_ids=task_ids,
                final_stage=None,
                leftover=leftover_report or None,
                total_tokens=total_tokens,
                total_cost_usd=total_cost_usd,
            )
        )
        logger.copy_work_history(os.path.join(repo_root, ".agents", "work-history.jsonl"))
        print()
        print("🏁 Orchestrator finished.")
        print(f"   Succeeded: {successes}")
        print(f"   Failed:    {failures}")
        if leftover_report:
            print(f"   Leftover:  {format_leftover_report(leftover_report)}")
        print(f"   Telemetry: {logger.run_dir}")

    def _cleanup_task(task_id: str, ret: int) -> None:
        nonlocal successes, failures, stop_spawn, systemic_tally
        running.pop(task_id, None)
        spawn_times.pop(task_id, None)
        queue = backend.load()["queue"]
        task = next((t for t in queue if t.get("id") == task_id), None)
        worktree_rel = task.get("worktree") if task else None
        worktree_dir = (
            os.path.join(repo_root, worktree_rel) if worktree_rel else None
        )
        deltas = _finalize_task(
            backend,
            queue_file,
            task_id,
            ret,
            repo_root=repo_root,
            logger=logger,
            on_failure=getattr(args, "on_failure", "triage"),
            adapter=adapter,
            worktree_dir=worktree_dir,
        )
        successes += deltas["successes"]
        failures += deltas["failures"]
        if deltas["stop_spawn"]:
            stop_spawn = True
        # Update the systemic breaker tally on every failure. A signature that
        # reaches the threshold across distinct tasks stops the shift.
        if ret != 0:
            queue = backend.load()["queue"]
            task = next((t for t in queue if t.get("id") == task_id), None)
            if task is not None:
                seen_sigs = {
                    entry.get("signature")
                    for entry in task.get("failure_signatures", [])
                    if entry.get("signature")
                }
                for sig in seen_sigs:
                    systemic_tally = breaker.update_systemic_tally(
                        systemic_tally, task_id, sig
                    )
                breaker_store.save(systemic_tally)
                if breaker.systemic_tripped(systemic_tally):
                    report = breaker.systemic_report(systemic_tally)
                    print(f"⛔ {report}")
                    stop_spawn = True
        remove_worktree(repo_root, task_id)

    try:
        acquire_lease(queue_file, logger.run_id)
        while True:
            # Refresh stored state before each spawn pass.
            queue = backend.load()["queue"]

            # Spawn tasks while slots available
            spawned_this_cycle: set[str] = set()
            while len(running) < max_jobs and not stop_spawn and not _shutdown_requested:
                task = get_next_ready_task(queue)
                if not task:
                    break

                task_id = task["id"]
                if task_id in spawned_this_cycle:
                    # Defensive: stored state is stale and keeps returning the same task.
                    break

                # Transition the task to in_progress through the sole writer so
                # stored state reflects that it has been picked up.
                from_state = current_state(task) or "ready"
                aet_state_bin = str(_SCRIPT_DIR / "aet_state.py")
                result = subprocess.run(
                    [
                        sys.executable,
                        aet_state_bin,
                        "transition",
                        task_id,
                        from_state,
                        "in_progress",
                        queue_file,
                    ],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    print(
                        f"   ⚠️  Could not transition {task_id} to in_progress: {result.stderr.strip()}"
                    )
                    _mark_failed(backend, queue_file, task_id, from_state)
                    failures += 1
                    stop_spawn = True
                    break

                # Re-read queue after transition and record branch/worktree so the
                # stored state reflects in_progress and does not spawn the same task
                # again on the next loop iteration.
                worktree_dir = create_worktree(repo_root, task_id)
                env = os.environ.copy()
                env["AET_TASK_ID"] = task_id
                env["AET_PLAN_FILE"] = task.get("plan_file", "")
                env["AET_WORKTREE"] = worktree_dir
                env["AET_RUN_ID"] = logger.run_id
                env["AET_REPO_ROOT"] = repo_root
                env["AET_STAGE"] = task.get("stage") or ""

                # Store a repo-relative worktree path for portability under lock.
                with queue_lock(queue_file):
                    queue = backend.load()["queue"]
                    for qt in queue:
                        if qt.get("id") == task_id:
                            qt["worktree"] = os.path.relpath(worktree_dir, repo_root)
                            qt["branch"] = task_id
                            break
                    backend.save(queue)

                # Build the orchestrator command for single-task mode
                cmd = [
                    sys.executable,
                    __file__,
                    "--plan-file",
                    task.get("plan_file", ""),
                    "--repo-root",
                    repo_root,
                    "--cli-bin",
                    adapter.bin,
                    "--isolation",
                    args.isolation,
                    "--stall-timeout",
                    str(getattr(args, "stall_timeout", 300)),
                    "--on-failure",
                    getattr(args, "on_failure", "triage"),
                ]

                proc = subprocess.Popen(cmd, env=env, start_new_session=True)
                running[task_id] = proc
                spawn_times[task_id] = time.monotonic()
                spawned_this_cycle.add(task_id)
                task_ids.append(task_id)
                print(f"▶️  Spawned {task.get('title', task_id)} (PID {proc.pid})")

                # Refresh stored state so the next spawn pass respects the branch we
                # just recorded and does not pick the same task again.
                queue = backend.load()["queue"]

            if not running:
                if stop_spawn or _shutdown_requested:
                    break
                if has_actionable_tasks(queue):
                    time.sleep(0.2)
                    continue
                # Nothing running and nothing that can still make progress on its
                # own (a ready/in_progress task). Whatever remains is stranded
                # until an external actor moves it, so exit with a leftover
                # report instead of spinning forever on the sleep.
                leftover_report.update(leftover_counts(queue))
                break

            # Poll for finished or timed-out processes
            now = time.monotonic()
            finished: list[tuple[str, int]] = []
            for task_id, proc in list(running.items()):
                ret = proc.poll()
                if ret is not None:
                    finished.append((task_id, ret))
                elif now - spawn_times[task_id] > task_timeout:
                    print(f"   ⏱️  {task_id} timed out after {args.task_timeout}s")
                    _terminate_process_group(proc, timeout=10)
                    finished.append((task_id, -9))

            for task_id, ret in finished:
                _cleanup_task(task_id, ret)

            # Heartbeat
            if now - last_heartbeat > heartbeat_interval:
                print(
                    f"   💓 Heartbeat: {len(running)} running, "
                    f"{successes} succeeded, {failures} failed"
                )
                last_heartbeat = now

            if _shutdown_requested:
                print("   ⚠️  Shutdown requested, stopping batch loop")
                break

            if not finished:
                time.sleep(0.2)

    finally:
        # Guarantee cleanup/summary even if the orchestrator crashes or is killed.
        for task_id, proc in list(running.items()):
            if proc.poll() is None:
                print(f"   ⚠️  Terminating leftover task {task_id}")
                _terminate_process_group(proc, timeout=10)
            _cleanup_task(task_id, -1)

        exit_code = 1 if failures > 0 else 0
        outcome = "success" if exit_code == 0 else "failure"
        _write_summary(outcome, exit_code)
        release_lease(queue_file, logger.run_id)

    return exit_code


def _find_queued_task(queue: list[dict], plan_file: str) -> dict | None:
    """Find a queued task that corresponds to ``plan_file``.

    Prefer an exact match on ``plan_file``. Fall back to matching the task
    ``id`` against the plan filename stem (with any ``-plan`` suffix removed).
    """
    plan_abs = os.path.abspath(plan_file)

    # First pass: exact path match (normalize both sides).
    for task in queue:
        task_plan = task.get("plan_file", "")
        if not task_plan:
            continue
        try:
            if os.path.abspath(task_plan) == plan_abs:
                return task
        except OSError:
            continue

    # Second pass: task id matches filename stem.
    stem = os.path.splitext(os.path.basename(plan_file))[0]
    task_id = stem.removesuffix("-plan")
    for task in queue:
        if task.get("id") == task_id:
            return task

    return None


def _record_run_one_in_queue(
    backend,
    queue_file: str,
    task_id: str,
    worktree: str,
    branch: str,
) -> bool:
    """Transition a queued task to in-progress and record branch/worktree.

    Uses ``aet-state transition`` to keep the queue's sole-writer rule intact,
    then re-reads the queue through the backend and records worktree/branch
    metadata atomically via ``backend.save``. Errors are logged but not raised
    so that a queue bookkeeping failure does not block the underlying run.
    """
    try:
        queue = backend.load()["queue"]
        task = next((t for t in queue if t.get("id") == task_id), None)
        if not task:
            print(f"   ⚠️  Task {task_id} disappeared from queue; skipping bookkeeping")
            return False

        from_state = current_state(task)
        if from_state is None:
            from_state = "planned"

        aet_state_bin = str(_SCRIPT_DIR / "aet_state.py")
        result = subprocess.run(
            [
                sys.executable,
                aet_state_bin,
                "transition",
                task_id,
                from_state,
                "in_progress",
                queue_file,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"   ⚠️  Could not transition {task_id} to in_progress: {result.stderr.strip()}")
            return False

        # Re-read the latest queue under lock and record branch/worktree.
        with queue_lock(queue_file):
            queue = backend.load()["queue"]
            for qt in queue:
                if qt.get("id") == task_id:
                    qt["worktree"] = worktree
                    qt["branch"] = branch
                    break
            backend.save(queue)
        print(f"   📝 Recorded {task_id} as in-progress (branch={branch}, worktree={worktree})")
        return True
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"   ⚠️  Queue bookkeeping failed for {task_id}: {exc}")
        return False


def run_single(args: argparse.Namespace, adapter) -> int:
    """Run single-plan mode."""
    repo_root = args.repo_root
    plan_file = args.plan_file

    run_id = getattr(args, "run_id", None) or os.environ.get("AET_RUN_ID")
    logger = telemetry.RunLogger(repo_root, run_id=run_id)
    # Ensure every subprocess (aet-state calls and stage sessions) inherits this
    # run id so their queue mutations pass the lease check.
    os.environ["AET_RUN_ID"] = logger.run_id
    queue_file = os.path.join(repo_root, ".agents", "work-queue.json")
    start_time = telemetry.iso_now()

    if not os.path.isabs(plan_file):
        plan_file = os.path.join(repo_root, plan_file)

    # When spawned by the batch orchestrator, the parent has already verified
    # main hygiene and will dirty the working tree by updating the queue file
    # between spawning tasks. Re-checking here would deadlock the pipeline.
    spawned_by_batch = bool(os.environ.get("AET_TASK_ID"))

    # Check main hygiene before any worktree work — but only for top-level
    # run-one invocations. Batch children rely on the parent-level check.
    if not spawned_by_batch and not enforce_main_hygiene(repo_root):
        end_time = telemetry.iso_now()
        logger.write_last_run(
            telemetry.run_summary_record(
                run_id=logger.run_id,
                start_time=start_time,
                end_time=end_time,
                tasks_spawned=0,
                tasks_succeeded=0,
                tasks_failed=1,
                outcome="failure",
                exit_code=1,
                task_ids=[],
                final_stage=None,
            )
        )
        print(f"   📁 Telemetry: {logger.run_dir}")
        return 1

    # Resolve the workflow once per task and thread it through process_task.
    # A missing or invalid workflow file fails the run loudly at task start;
    # the packaged default is the only fallback.
    try:
        plan_fm = plan_parser.parse_frontmatter(Path(plan_file))
    except OSError:
        plan_fm = {}
    workflow_name = plan_fm.get("workflow") or "software"
    try:
        wf = load_workflow(repo_root, workflow_name)
    except WorkflowError as exc:
        print(f"   ❌ {exc}")
        end_time = telemetry.iso_now()
        logger.write_last_run(
            telemetry.run_summary_record(
                run_id=logger.run_id,
                start_time=start_time,
                end_time=end_time,
                tasks_spawned=0,
                tasks_succeeded=0,
                tasks_failed=1,
                outcome="failure",
                exit_code=1,
                task_ids=[],
                final_stage=None,
            )
        )
        print(f"   📁 Telemetry: {logger.run_dir}")
        return 1

    # For a top-level run-one, declare that this run owns the queue so
    # out-of-band mutators refuse. Batch children share the parent's lease via
    # AET_RUN_ID and must not acquire/release their own.
    owns_lease = False
    try:
        if not spawned_by_batch:
            acquire_lease(queue_file, logger.run_id)
            owns_lease = True

        # Create a synthetic task. Prefer the batch-provided task ID/worktree so
        # parent and child agree on worktree/branch names (e.g. "*-plan" suffixes).
        base_name = os.path.splitext(os.path.basename(plan_file))[0]
        task_id = os.environ.get("AET_TASK_ID") or base_name.removesuffix("-plan")
        worktree_dir = os.environ.get("AET_WORKTREE")
        if worktree_dir and not os.path.isabs(worktree_dir):
            worktree_dir = os.path.join(repo_root, worktree_dir)

        # If this plan is tracked in the work queue and this is a top-level run-one
        # (not a child spawned by run_batch), transition the task to in-progress
        # and record branch/worktree so aet-state record-merge works after shipping.
        backend = _make_backend(queue_file)
        queued_task = None
        if os.path.exists(queue_file) and not spawned_by_batch:
            queue = backend.load()["queue"]
            queued_task = _find_queued_task(queue, plan_file)

        if queued_task and not spawned_by_batch:
            queued_task_id = queued_task.get("id", task_id)
            # Ensure the worktree/branch exist before recording them.
            worktree_dir = create_worktree(repo_root, queued_task_id)
            worktree_rel = os.path.relpath(worktree_dir, repo_root)
            _record_run_one_in_queue(backend, queue_file, queued_task_id, worktree_rel, queued_task_id)
            task_id = queued_task_id

        # Prefer the real queued task record so failure signatures are
        # persisted on the ledger (nsr-03). Fall back to a synthetic record for
        # manual run-one invocations that are not tracked in the queue.
        real_task = None
        if os.path.exists(queue_file):
            queue = backend.load()["queue"]
            real_task = next((t for t in queue if t.get("id") == task_id), None)
        env_stage = os.environ.get("AET_STAGE") or None
        if real_task is not None:
            task = real_task
            task["plan_file"] = plan_file
            # Batch children pass AET_STAGE so a stale footer does not fool
            # process_task; prefer the env value over whatever is on record.
            if env_stage:
                task["stage"] = env_stage
        else:
            task = {
                "id": task_id,
                "title": task_id,
                "plan_file": plan_file,
                "stage": env_stage,
            }

        print(f"📁 Telemetry: {logger.run_dir}")
        success = process_task(
            task,
            repo_root,
            adapter,
            args.isolation,
            logger=logger,
            worktree_dir=worktree_dir,
            workflow=wf,
            backend=backend,
            stall_timeout=getattr(args, "stall_timeout", 300),
        )
        exit_code = 0 if success else 1

        # Roll up per-task cost from this child's telemetry and persist it on the
        # queued task record. The batch parent later seals state, but cost must
        # be captured by the process that generated the stage records (nsr-07).
        if real_task is not None:
            queue = backend.load()["queue"]
            queue_task = next((t for t in queue if t.get("id") == task_id), None)
            if queue_task:
                tokens, usd = _task_usage_aggregates(logger, task_id)
                if tokens is not None or usd is not None:
                    queue_task["cost"] = {"tokens": tokens, "usd": usd}
                    backend.save(queue)

        # For top-level run-one on a queued task, mirror run_batch and transition
        # the task to awaiting_merge on success so aet-state record-merge can run.
        if success and queued_task and not spawned_by_batch:
            try:
                queue = backend.load()["queue"]
                queue_task = next((t for t in queue if t.get("id") == task_id), None)
                if queue_task:
                    from_state = current_state(queue_task) or "in_progress"
                    worktree_rel = queue_task.get("worktree")
                    if worktree_rel:
                        ok, msg = verify_branch_has_commits(
                            os.path.join(repo_root, worktree_rel)
                        )
                        if not ok:
                            print(f"   ❌ Task {task_id} succeeded but produced no commits: {msg}")
                            _mark_failed(backend, queue_file, task_id, from_state)
                            exit_code = 1
                        else:
                            tokens, usd = _task_usage_aggregates(logger, task_id)
                            if tokens is not None or usd is not None:
                                queue_task["cost"] = {"tokens": tokens, "usd": usd}
                                backend.save(queue)
                            if _maybe_auto_merge(queue_task, queue_file, repo_root):
                                pass  # perform_auto_merge prints success/failure.
                            else:
                                aet_state_bin = str(_SCRIPT_DIR / "aet_state.py")
                                result = subprocess.run(
                                    [
                                        sys.executable,
                                        aet_state_bin,
                                        "transition",
                                        task_id,
                                        from_state,
                                        "awaiting_merge",
                                        queue_file,
                                    ],
                                    capture_output=True,
                                    text=True,
                                )
                                if result.returncode == 0:
                                    print(f"   ✅ Task {task_id} awaiting merge")
                                else:
                                    print(
                                        f"   ⚠️  Could not transition {task_id} to "
                                        f"awaiting_merge: {result.stderr.strip()}"
                                    )
            except Exception as exc:  # pragma: no cover - defensive logging
                print(f"   ⚠️  Could not mark {task_id} awaiting merge: {exc}")

        end_time = telemetry.iso_now()

        # Read the final stage from the synthetic task record; the footer is only a breadcrumb.
        final_stage = task.get("stage") or read_plan_stage(plan_file) or wf.entry_stage

        total_tokens, total_cost_usd = _usage_aggregates(logger)
        logger.write_last_run(
            telemetry.run_summary_record(
                run_id=logger.run_id,
                start_time=start_time,
                end_time=end_time,
                tasks_spawned=1,
                tasks_succeeded=1 if success else 0,
                tasks_failed=0 if success else 1,
                outcome="success" if success else "failure",
                exit_code=exit_code,
                task_ids=[task_id],
                final_stage=final_stage,
                total_tokens=total_tokens,
                total_cost_usd=total_cost_usd,
            )
        )
        if not spawned_by_batch:
            logger.copy_work_history(os.path.join(repo_root, ".agents", "work-history.jsonl"))
        return exit_code
    finally:
        if owns_lease:
            release_lease(queue_file, logger.run_id)


def main(argv: list[str] | None = None):
    args = parse_args(argv)
    adapter = resolve_cli_adapter(args.cli_bin)

    repo_root = args.repo_root
    run_id = args.run_id
    if run_id:
        _redirect_output(args.log_file)
        _write_run_metadata(repo_root, run_id)

    print(f"🤖 Orchestrator using {adapter.name} ({adapter.bin})")
    if run_id:
        print(f"   Run ID: {run_id}")

    exit_code = 1
    try:
        if args.queue_file:
            exit_code = run_batch(args, adapter)
        else:
            exit_code = run_single(args, adapter)
    finally:
        if run_id:
            _write_returncode(repo_root, run_id, exit_code)
    return exit_code


app = typer.Typer(
    name="orchestrator",
    help="AE Toolkit Unified Orchestrator",
)


def _isolation_choice(value: str) -> str:
    if value not in ("minimal", "standard", "full"):
        raise typer.BadParameter("must be one of: minimal, standard, full")
    return value


def _on_failure_choice(value: str) -> str:
    if value not in ("triage", "continue", "halt"):
        raise typer.BadParameter("must be one of: triage, continue, halt")
    return value


@app.callback(invoke_without_command=True)
def orchestrator_callback(
    ctx: typer.Context,
    queue_file: Optional[str] = typer.Option(
        None,
        "--queue-file",
        help="Path to work-queue.json (batch mode).",
    ),
    plan_file: Optional[str] = typer.Option(
        None,
        "--plan-file",
        help="Path to a single plan.md (single-plan mode).",
    ),
    repo_root: str = typer.Option(
        os.getcwd(),
        "--repo-root",
        help="Repository root path.",
    ),
    cli_bin: Optional[str] = typer.Option(
        None,
        "--cli-bin",
        help="Agent CLI binary path.",
    ),
    isolation: str = typer.Option(
        "standard",
        "--isolation",
        help="Isolation level.",
        callback=_isolation_choice,
    ),
    max_jobs: int = typer.Option(
        4,
        "--max-jobs",
        help="Max parallel tasks (batch mode).",
    ),
    task_timeout: int = typer.Option(
        7200,
        "--task-timeout",
        help="Per-task wall-clock timeout in seconds (default: 7200).",
    ),
    stall_timeout: int = typer.Option(
        300,
        "--stall-timeout",
        help="Stdout-silence timeout in seconds before a session is killed (default: 300).",
    ),
    heartbeat_interval: int = typer.Option(
        60,
        "--heartbeat-interval",
        help="Seconds between heartbeat log lines (default: 60).",
    ),
    run_id: Optional[str] = typer.Option(
        None,
        "--run-id",
        help="Run identifier used for telemetry and run metadata.",
    ),
    log_file: Optional[str] = typer.Option(
        None,
        "--log-file",
        help="Redirect stdout/stderr to this file (detached-run mode).",
    ),
    on_failure: str = typer.Option(
        "triage",
        "--on-failure",
        help=(
            "What to do when a task fails in batch mode: triage (default) "
            "requeues transient failures; continue marks failed and keeps "
            "spawning; halt stops the shift on the first failure."
        ),
        callback=_on_failure_choice,
    ),
) -> None:
    """AE Toolkit Unified Orchestrator."""
    if queue_file is None and plan_file is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(2)
    if queue_file is not None and plan_file is not None:
        typer.echo("error: --queue-file and --plan-file are mutually exclusive", err=True)
        raise typer.Exit(2)

    argv: list[str] = []
    if queue_file is not None:
        argv.extend(["--queue-file", queue_file])
    if plan_file is not None:
        argv.extend(["--plan-file", plan_file])
    argv.extend(["--repo-root", repo_root])
    if cli_bin is not None:
        argv.extend(["--cli-bin", cli_bin])
    argv.extend(["--isolation", isolation])
    argv.extend(["--max-jobs", str(max_jobs)])
    argv.extend(["--task-timeout", str(task_timeout)])
    argv.extend(["--stall-timeout", str(stall_timeout)])
    argv.extend(["--heartbeat-interval", str(heartbeat_interval)])
    if run_id is not None:
        argv.extend(["--run-id", run_id])
    if log_file is not None:
        argv.extend(["--log-file", log_file])
    argv.extend(["--on-failure", on_failure])

    raise typer.Exit(main(argv))


if __name__ == "__main__":
    app()
