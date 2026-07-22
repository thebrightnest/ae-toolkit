#!/usr/bin/env python3
"""aet — single Typer app entry point for the AE Toolkit.

All subcommands register directly on the ``app`` object below. The legacy
``SUBCOMMANDS`` spec, os.exec dispatch, and multi-binary symlink pruning have
been removed. ``aet install`` and ``_ensure_path_link`` remain because
single-name PATH ownership is still required.
"""

from __future__ import annotations

# Bootstrap guard: when this script is invoked directly from a source checkout,
# the interpreter may be system Python which lacks the AE Toolkit dependencies.
# Re-exec under the repo's virtual environment when available.
import os
import secrets
import string
import subprocess
import sys
import time
from pathlib import Path

_REQUIRED_IMPORTS = ("filelock", "yaml", "aet")


def _can_import_aet() -> bool:
    for name in _REQUIRED_IMPORTS:
        try:
            __import__(name)
        except Exception:
            return False
    return True


if not _can_import_aet():
    here = Path(__file__).resolve()
    candidate_roots = [
        here.parent.parent.parent.parent,
        Path.cwd(),
    ]
    venv_path = os.environ.get("VIRTUAL_ENV")
    if venv_path:
        candidate_roots.insert(0, Path(venv_path))
    for root in candidate_roots:
        venv_python = root / ".venv" / "bin" / "python"
        if not venv_python.exists():
            venv_python = root / "bin" / "python"
        if venv_python.exists():
            os.execv(str(venv_python), [str(venv_python), str(here)] + sys.argv[1:])

import importlib  # noqa: E402

import typer  # noqa: E402

# Import subcommand modules. Each module exposes an ``app`` attribute that is a
# ``typer.Typer()`` instance registered under a top-level name below.
# isort: off
from aet.cli import (  # noqa: E402
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
    sprint,
    status,
    sync,
    validate_workflows,
)
# isort: on

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
app.add_typer(sprint.app, name="sprint", help="Sprint queue management.")

# Top-level single-word commands.
app.add_typer(configure_backend.app, name="configure-backend")
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


# ---------------------------------------------------------------------------
# PATH ownership helpers (kept from the legacy dispatcher)
# ---------------------------------------------------------------------------


def _running_script() -> Path:
    """Return the resolved path of this running copy."""
    return Path(__file__).resolve()


def _is_worktree_copy(script: Path) -> bool:
    """True when the running copy lives under a ``.worktrees`` directory."""
    return ".worktrees" in script.parts


def _bin_dir() -> Path:
    """Return the link target dir: ``AET_BIN_DIR`` or ``~/.local/bin``."""
    override = os.environ.get("AET_BIN_DIR")
    return Path(override) if override else Path.home() / ".local" / "bin"


def _link_target_resolves_to(link: Path, script: Path) -> bool:
    """True when ``link`` is a symlink already pointing at ``script``."""
    target = Path(os.readlink(link))
    if not target.is_absolute():
        target = link.parent / target
    return target.resolve() == script


def _ensure_path_link() -> None:
    """Silently create or repair the AET-managed ``aet`` symlink.

    Best-effort and never fatal. Skipped on worktree copies and non-symlink
    collisions.
    """
    try:
        bin_dir = _bin_dir()
        link = bin_dir / "aet"
        script = _running_script()
        if _is_worktree_copy(script):
            return
        if link.is_symlink():
            if _link_target_resolves_to(link, script):
                return
            link.unlink()
        elif link.exists():
            return
        else:
            bin_dir.mkdir(parents=True, exist_ok=True)
        link.symlink_to(script)
    except OSError:
        pass


def _version_callback(value: bool) -> None:
    if value:
        from importlib.metadata import version as get_version

        typer.echo(f"aet {get_version('aet')}")
        raise typer.Exit()


@app.callback()
def _main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        help="Show the version and exit.",
        is_eager=True,
        callback=_version_callback,
    ),
) -> None:
    """On every non-install invocation, verify/repair the ``aet`` symlink."""
    if ctx.invoked_subcommand != "install":
        _ensure_path_link()


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


def _follow_run(run_id: str) -> int:
    """Tail the log for ``run_id`` until the process exits."""
    rdir = _run_dir(run_id)
    log_file = rdir / "output.log"
    pid_file = rdir / "pid"
    rc_file = rdir / "returncode"

    if not rdir.is_dir():
        typer.echo(f"error: unknown run id '{run_id}'", err=True)
        raise typer.Exit(1)

    if log_file.is_file():
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                typer.echo(line, nl=False)

    if rc_file.is_file():
        raise typer.Exit(int(rc_file.read_text(encoding="utf-8").strip() or "0"))

    pid: int | None = None
    if pid_file.is_file():
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
        except ValueError:
            pid = None

    with open(log_file, "r", encoding="utf-8", errors="replace") as f:
        if log_file.is_file():
            f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if line:
                typer.echo(line, nl=False)
                continue
            if pid is not None and not _is_process_alive(pid):
                for _ in range(20):
                    if rc_file.is_file():
                        break
                    time.sleep(0.1)
                if rc_file.is_file():
                    raise typer.Exit(int(rc_file.read_text(encoding="utf-8").strip() or "0"))
                raise typer.Exit(1)
            if pid is None and rc_file.is_file():
                raise typer.Exit(int(rc_file.read_text(encoding="utf-8").strip() or "0"))
            time.sleep(0.1)


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
    max_jobs: int,
    isolation: str,
    on_failure: str | None,
    task_timeout: int | None,
    stall_timeout: int | None,
    cli_bin: str | None,
) -> list[str]:
    """Build the forwarded flag list for the orchestrator."""
    flags = ["--max-jobs", str(max_jobs), "--isolation", isolation]
    if on_failure is not None:
        flags.extend(["--on-failure", on_failure])
    if task_timeout is not None:
        flags.extend(["--task-timeout", str(task_timeout)])
    if stall_timeout is not None:
        flags.extend(["--stall-timeout", str(stall_timeout)])
    if cli_bin is not None:
        flags.extend(["--cli-bin", cli_bin])
    return flags


def _exec_orchestrator(argv: list[str]) -> int:
    """Exec the orchestrator with the current Python interpreter."""
    try:
        os.execvp(sys.executable, [sys.executable, str(_orchestrator_path()), *argv])
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0
    return 0


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
    foreground: bool = typer.Option(False, "--foreground", help="Run in foreground."),
    follow: str | None = typer.Option(None, "--follow", help="Follow an existing run id."),
    max_jobs: int = typer.Option(4, "--max-jobs", help="Max parallel tasks."),
    isolation: str = typer.Option("standard", "--isolation", help="Isolation level."),
    on_failure: str | None = typer.Option(None, "--on-failure", help="triage|continue|halt"),
    task_timeout: int | None = typer.Option(None, "--task-timeout", help="Per-task timeout (s)."),
    stall_timeout: int | None = typer.Option(None, "--stall-timeout", help="Silence timeout (s)."),
    cli_bin: str | None = typer.Option(None, "--cli-bin", help="Agent CLI binary path."),
) -> None:
    """Run the orchestrator in batch mode."""
    if follow is not None:
        _follow_run(follow)
        return

    flags = _build_orchestrator_flags(max_jobs, isolation, on_failure, task_timeout, stall_timeout, cli_bin)
    argv = ["--queue-file", ".agents/work-queue.json", *flags]

    if foreground:
        raise typer.Exit(_exec_orchestrator(argv))

    run_id = _generate_run_id()
    flags.extend(["--run-id", run_id, "--log-file", str(_run_log_file(run_id))])
    argv = ["--queue-file", ".agents/work-queue.json", *flags]
    raise typer.Exit(_spawn_detached(argv, run_id))


@app.command("run-one")
def run_one(
    plan_file: str = typer.Argument(..., help="Plan file to run."),
    foreground: bool = typer.Option(False, "--foreground", help="Run in foreground."),
    follow: str | None = typer.Option(None, "--follow", help="Follow an existing run id."),
    max_jobs: int = typer.Option(4, "--max-jobs", help="Max parallel tasks."),
    isolation: str = typer.Option("standard", "--isolation", help="Isolation level."),
    on_failure: str | None = typer.Option(None, "--on-failure", help="triage|continue|halt"),
    task_timeout: int | None = typer.Option(None, "--task-timeout", help="Per-task timeout (s)."),
    stall_timeout: int | None = typer.Option(None, "--stall-timeout", help="Silence timeout (s)."),
    cli_bin: str | None = typer.Option(None, "--cli-bin", help="Agent CLI binary path."),
) -> None:
    """Run the orchestrator for a single plan."""
    if follow is not None:
        _follow_run(follow)
        return

    flags = _build_orchestrator_flags(max_jobs, isolation, on_failure, task_timeout, stall_timeout, cli_bin)
    argv = ["--plan-file", plan_file, *flags]

    if foreground:
        raise typer.Exit(_exec_orchestrator(argv))

    run_id = _generate_run_id()
    flags.extend(["--run-id", run_id, "--log-file", str(_run_log_file(run_id))])
    argv = ["--plan-file", plan_file, *flags]
    raise typer.Exit(_spawn_detached(argv, run_id))


# ---------------------------------------------------------------------------
# install command (kept in main.py)
# ---------------------------------------------------------------------------


@app.command()
def install(
    bin_dir: str | None = typer.Option(None, "--bin-dir", help="Target bin directory."),
) -> None:
    """Link ``aet`` into the bin dir."""
    target_dir = Path(bin_dir) if bin_dir else _bin_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    script = _running_script()
    if _is_worktree_copy(script):
        typer.echo(
            f"  ⚠ refusing to link from an ephemeral worktree copy ({script});"
            " run install from the main checkout.",
            err=True,
        )
        raise typer.Exit(1)

    link = target_dir / "aet"
    if link.is_symlink():
        if _link_target_resolves_to(link, script):
            typer.echo(f"  = aet already linked -> {script}")
        else:
            link.unlink()
            link.symlink_to(script)
            typer.echo(f"  ✓ aet -> {script} (updated stale symlink)")
    elif link.exists():
        typer.echo(
            f"  ⚠ aet exists in {target_dir} and is not a symlink. Skipping.",
            err=True,
        )
    else:
        link.symlink_to(script)
        typer.echo(f"  ✓ aet -> {script}")

    if str(target_dir) not in os.environ.get("PATH", "").split(os.pathsep):
        typer.echo(f"\n⚠ {target_dir} is not on your PATH. Add it to your shell profile:")
        typer.echo(f'    export PATH="{target_dir}:$PATH"')


def main() -> int:
    _ensure_aet_importable()
    try:
        app()
    except SystemExit as exc:
        if isinstance(exc.code, int):
            return exc.code
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
