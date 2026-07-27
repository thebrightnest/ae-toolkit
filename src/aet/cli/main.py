"""aet — single Typer app entry point for the AE Toolkit.

All subcommands register directly on the ``app`` object below. The supported
invocations are the installed console script (``aet``) and
``python -m aet.cli.main``; both guarantee an interpreter that can import the
package, so no module-level bootstrap guard is required.
"""

from __future__ import annotations

import importlib
import os
import secrets
import string
import subprocess
import sys
import time
from pathlib import Path

import typer

# Import subcommand modules. Each module exposes an ``app`` attribute that is a
# ``typer.Typer()`` instance registered under a top-level name below.
# isort: off
from aet.cli import (
    aet_state,
    backlog,
    configure_backend,
    desk,
    docs,
    gate,
    harness_guard,
    hooks,
    init_queue,
    metrics,
    mine_learnings,
    next as next_module,
    panel,
    plan,
    plans,
    reconcile,
    release_prep,
    report,
    retro,
    setup,
    ship,
    size,
    sprint,
    status,
    sync,
    validate_workflows,
)
# isort: on
from aet.plan_parser import resolve_plan_arg

app = typer.Typer(
    help="Agentic Engineering Toolkit CLI",
    no_args_is_help=True,
    add_completion=False,
)

# Noun-scoped command groups.
app.add_typer(aet_state.app, name="state", help="Queue mutations, stage transitions, and footer updates.")
app.add_typer(backlog.app, name="backlog", help="Backlog curation commands.")
app.add_typer(desk.app, name="desk", help="Review cockpit for awaiting_merge tasks.")
app.add_typer(docs.app, name="docs", help="Documentation linting and syncing.")
app.add_typer(gate.app, name="gate", help="Fail-closed verdict writer and review board renderer.")
app.add_typer(hooks.app, name="hooks", help="Git hook installation and management.")
app.add_typer(plan.app, name="plan", help="Plan-quality commands.")
app.add_typer(plans.app, name="plans", help="Bulk plan operations and corpus linting.")
app.add_typer(sync.app, name="queue", help="Work queue sync and related operations.")
app.add_typer(setup.app, name="setup", help="Setup and bootstrap commands.")
app.add_typer(ship.app, name="ship", help="Pre-merge gate, PR creation, and post-merge closure.")
app.add_typer(size.app, name="size", help="Delivered-size measurement and reporting.")
app.add_typer(sprint.app, name="sprint", help="Sprint queue management.")

# Top-level single-word commands.
app.add_typer(configure_backend.app, name="configure")
app.add_typer(harness_guard.app, name="harness-guard")
app.add_typer(init_queue.app, name="init-queue")
app.add_typer(metrics.app, name="metrics")
app.add_typer(mine_learnings.app, name="mine-learnings")
app.add_typer(next_module.app, name="next")
app.add_typer(panel.app, name="panel")
app.add_typer(reconcile.app, name="reconcile")
app.add_typer(release_prep.app, name="release-prep")
app.add_typer(report.app, name="report")
app.add_typer(retro.app, name="retro")
app.add_typer(status.app, name="status")
app.add_typer(validate_workflows.app, name="validate-workflows")


def _version_callback(value: bool) -> None:
    if value:
        from importlib.metadata import version as get_version

        typer.echo(f"aet {get_version('aet')}")
        raise typer.Exit()


@app.callback()
def _main_callback(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show the version and exit.",
        is_eager=True,
        callback=_version_callback,
    ),
) -> None:
    """Top-level callback; handles --version only."""


# ---------------------------------------------------------------------------
# Orchestrator launch helpers (run / run-one)
# ---------------------------------------------------------------------------


def _generate_run_id() -> str:
    """Return a short, collision-resistant run identifier."""
    alphabet = string.ascii_lowercase + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(8))
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    return f"run-{timestamp}-{suffix}"


def _runs_dir() -> Path:
    """Return the canonical detached-run metadata directory."""
    return Path.cwd() / ".agents" / "runs"


def _run_dir(run_id: str) -> Path:
    """Return the per-run metadata directory."""
    return _runs_dir() / run_id


def _run_log_file(run_id: str) -> Path:
    """Return the log file path for ``run_id``."""
    return _run_dir(run_id) / "output.log"


def _is_process_alive(pid: int) -> bool:
    """Return True if ``pid`` is still running."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    return True


def _wait_for_run(run_id: str) -> int:
    """Wait silently for ``run_id`` to finish and return its exit code.

    Returns the stored returncode if one already exists. Otherwise waits for
    the orchestrator pid to disappear, then allows a short grace period for the
    returncode file to be written. If the pid file is absent or unparseable and
    no returncode exists, exits non-zero with a diagnostic.
    """
    rdir = _run_dir(run_id)
    pid_file = rdir / "pid"
    rc_file = rdir / "returncode"

    if not rdir.is_dir():
        typer.echo(f"error: unknown run id '{run_id}'", err=True)
        raise typer.Exit(1)

    if rc_file.is_file():
        return int(rc_file.read_text(encoding="utf-8").strip() or "0")

    pid: int | None = None
    if pid_file.is_file():
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
        except ValueError:
            pid = None

    if pid is None:
        typer.echo(
            f"error: run '{run_id}' has no process and no returncode", err=True
        )
        raise typer.Exit(1)

    while True:
        if rc_file.is_file():
            return int(rc_file.read_text(encoding="utf-8").strip() or "0")
        if not _is_process_alive(pid):
            for _ in range(20):
                if rc_file.is_file():
                    return int(rc_file.read_text(encoding="utf-8").strip() or "0")
                time.sleep(0.1)
            typer.echo(
                f"error: run '{run_id}' exited without writing a returncode",
                err=True,
            )
            raise typer.Exit(1)
        time.sleep(0.1)


def _follow_run(run_id: str) -> None:
    """Attach to ``run_id`` and exit with its final status without echoing output."""
    raise typer.Exit(_wait_for_run(run_id))


def _ensure_aet_importable() -> None:
    """Bootstrap PYTHONPATH for repo checkouts when ``aet`` is not installed."""
    try:
        importlib.import_module("aet")
        return
    except ImportError:
        pass

    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    src_dir = repo_root / "src"
    if (src_dir / "aet" / "__init__.py").is_file():
        current = os.environ.get("PYTHONPATH", "")
        if current:
            os.environ["PYTHONPATH"] = f"{src_dir}{os.pathsep}{current}"
        else:
            os.environ["PYTHONPATH"] = str(src_dir)


def _orchestrator_path() -> Path:
    """Return the path to the orchestrator module."""
    return Path(__file__).resolve().parent / "orchestrator.py"


def _build_orchestrator_flags(
    on_failure: str | None,
    task_timeout: int | None,
    cli_bin: str | None,
    base: str | None,
) -> list[str]:
    """Build the forwarded flag list for the orchestrator.

    ``--max-jobs`` and ``--isolation`` are supplied internally at their
    defaults (4, ``standard``); they are not caller-tunable (rid-01).
    """
    flags = ["--max-jobs", "4", "--isolation", "standard"]
    if on_failure is not None:
        flags.extend(["--on-failure", on_failure])
    if task_timeout is not None:
        flags.extend(["--task-timeout", str(task_timeout)])
    if cli_bin is not None:
        flags.extend(["--cli-bin", cli_bin])
    if base is not None:
        flags.extend(["--base", base])
    return flags


def _spawn_detached(argv: list[str], run_id: str) -> int:
    """Spawn the orchestrator detached and print the run ID."""
    rdir = _run_dir(run_id)
    rdir.mkdir(parents=True, exist_ok=True)
    log_file = _run_log_file(run_id)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["AET_RUN_ID"] = run_id

    with open(log_file, "a", buffering=1, encoding="utf-8") as log:
        proc = subprocess.Popen(
            [sys.executable, str(_orchestrator_path()), *argv],
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            env=env,
            cwd=os.getcwd(),
        )
        (rdir / "pid").write_text(str(proc.pid), encoding="utf-8")

    typer.echo(f"🚀 Started run {run_id}")
    typer.echo(f"   Log: {log_file}")
    typer.echo(f"   Follow: aet run --follow {run_id}")
    return 0


@app.command()
def run(
    follow: str | None = typer.Option(None, "--follow", help="Follow an existing run id."),
    on_failure: str | None = typer.Option(None, "--on-failure", help="triage|continue|halt"),
    task_timeout: int | None = typer.Option(None, "--task-timeout", help="Per-task timeout (s)."),
    cli_bin: str | None = typer.Option(None, "--cli-bin", help="Agent CLI binary path."),
    base: str | None = typer.Option(None, "--base", help="Override the worktree base branch/ref."),
) -> None:
    """Run the orchestrator in batch mode."""
    if follow is not None:
        _follow_run(follow)
        return

    run_id = _generate_run_id()
    flags = _build_orchestrator_flags(on_failure, task_timeout, cli_bin, base)
    flags.extend(["--run-id", run_id, "--log-file", str(_run_log_file(run_id))])
    argv = ["--queue-file", ".agents/work-queue.json", *flags]
    raise typer.Exit(_spawn_detached(argv, run_id))


@app.command("run-one")
def run_one(
    plan_file: str = typer.Argument(
        ..., help="Plan file path or task ID to run."
    ),
    follow: str | None = typer.Option(None, "--follow", help="Follow an existing run id."),
    on_failure: str | None = typer.Option(None, "--on-failure", help="triage|continue|halt"),
    task_timeout: int | None = typer.Option(None, "--task-timeout", help="Per-task timeout (s)."),
    cli_bin: str | None = typer.Option(None, "--cli-bin", help="Agent CLI binary path."),
    base: str | None = typer.Option(None, "--base", help="Override the worktree base branch/ref."),
) -> None:
    """Run the orchestrator for a single plan."""
    if follow is not None:
        _follow_run(follow)
        return

    try:
        resolved = resolve_plan_arg(plan_file)
    except ValueError as exc:
        typer.echo(f"⛔ {exc}", err=True)
        raise typer.Exit(1) from exc

    run_id = _generate_run_id()
    flags = _build_orchestrator_flags(on_failure, task_timeout, cli_bin, base)
    flags.extend(["--run-id", run_id, "--log-file", str(_run_log_file(run_id))])
    argv = ["--plan-file", resolved, *flags]
    _spawn_detached(argv, run_id)
    raise typer.Exit(_wait_for_run(run_id))


def main() -> int:
    _ensure_aet_importable()
    try:
        app()
    except SystemExit as exc:
        if isinstance(exc.code, int):
            return exc.code
        return 0
    return 0


# Runs under ``python -m aet.cli.main``, which is a supported invocation
# (``Makefile`` validate targets, and several subprocess tests). Without this
# the module is imported, nothing dispatches, and the process exits 0 — turning
# every ``-m`` caller into a silent no-op. The direct-script mode is what this
# module dropped: there is no shebang and no interpreter bootstrap, so an
# interpreter that cannot import ``aet`` now fails loudly at import.
if __name__ == "__main__":
    sys.exit(main())
