"""`aet setup` subcommand group."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import typer

from aet.backends.factory import (
    resolve_config_with_source,
    resolve_integration_mode_with_provenance,
)
from aet.branch_ref import resolve_integration_branch, resolve_trunk_branch
from aet.worktree import AET_IGNORED_PATHS

app = typer.Typer(help="Setup and bootstrap commands.")


def _format_branch_provenance(provenance: str, config_source: str) -> str:
    """Render a branch resolver provenance, annotating config with its layer."""
    if provenance == "config":
        return f"config ({config_source})"
    return provenance


def _repo_root() -> Path:
    """Return the absolute path to the AE Toolkit repository root.

    The ``AET_REPO_ROOT`` environment variable overrides filesystem
    inference so that the command works when ``aet`` is installed into a
    dedicated venv (where ``__file__`` resolves to site-packages) and when
    invoked from a git worktree (where ``__file__`` resolves to the
    ephemeral worktree copy).
    """
    env_root = os.environ.get("AET_REPO_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    return Path(__file__).resolve().parent.parent.parent.parent


def write_aet_gitignore_entries(repo_root: str | Path) -> list[str]:
    """Idempotently write AET ignore entries to ``repo_root/.gitignore``.

    Reads the shared ``AET_IGNORED_PATHS`` constant so the hygiene gate and
    setup command always agree. Existing lines are preserved; duplicate
    entries are never appended.
    """
    gitignore = Path(repo_root) / ".gitignore"
    existing_lines: set[str] = set()
    if gitignore.exists():
        existing_lines = {
            line.strip() for line in gitignore.read_text(encoding="utf-8").splitlines()
        }

    added: list[str] = []
    for entry in AET_IGNORED_PATHS:
        if entry not in existing_lines:
            added.append(entry)

    if added:
        with gitignore.open("a", encoding="utf-8") as f:
            for entry in added:
                f.write(f"{entry}\n")

    return added


def _bin_dir() -> Path:
    """Return the link target dir: ``AET_BIN_DIR`` or ``~/.local/bin``."""
    override = os.environ.get("AET_BIN_DIR")
    return Path(override) if override else Path.home() / ".local" / "bin"


def _link_target() -> Path | None:
    """Return the ``aet`` console script installed next to the interpreter.

    ADR-041 makes the console script the only supported entry point, so there
    is no fallback: linking a module file instead produces a link that cannot
    execute (no shebang, not executable), which is the defect class this
    command exists to remove. ``None`` means "refuse", not "guess".

    Resolved, because ``_link_target_resolves_to`` compares against a resolved
    readlink; leaving it unresolved makes an already-correct link compare
    unequal whenever any path component is a symlink (``/tmp`` on macOS), so
    every run would report a stale-link repair it did not need to make.
    """
    console_script = Path(sys.executable).parent / "aet"
    if console_script.exists():
        return console_script.resolve()
    return None


def _is_worktree_copy(script: Path) -> bool:
    """True when the running copy lives under a ``.worktrees`` directory."""
    return ".worktrees" in script.parts


def _link_target_resolves_to(link: Path, script: Path) -> bool:
    """True when ``link`` is a symlink already pointing at ``script``."""
    target = Path(os.readlink(link))
    if not target.is_absolute():
        target = link.parent / target
    return target.resolve() == script


def _agent_skills_dirs() -> list[Path]:
    """Return detected agent skills directories."""
    home = Path.home()
    candidates = [
        home / ".claude" / "skills",
        home / ".kimi" / "skills",
        home / ".cursor" / "skills",
        home / ".agents" / "skills",
    ]
    return [p for p in candidates if p.is_dir()]


def _resolve_target_dirs(
    skills_dir: str | None,
    agent: str | None,
) -> list[Path]:
    """Resolve the target skills directories from explicit flags or auto-detection."""
    if skills_dir is not None:
        return [Path(skills_dir).expanduser().resolve()]

    if agent is not None:
        home = Path.home()
        mapping = {
            "claude-code": home / ".claude" / "skills",
            "kimi": home / ".kimi" / "skills",
            "cursor": home / ".cursor" / "skills",
            "generic": home / ".agents" / "skills",
        }
        if agent not in mapping:
            typer.echo(f"error: unknown agent '{agent}'", err=True)
            raise typer.Exit(1)
        return [mapping[agent]]

    detected = _agent_skills_dirs()
    if detected:
        return detected
    return [Path.home() / ".agents" / "skills"]


def _link_skill(
    skill_path: Path,
    target_dir: Path,
    *,
    dry_run: bool,
    force: bool,
) -> str:
    """Ensure ``target_dir/<skill-name>`` symlinks to ``skill_path``.

    Returns a human-readable status line.
    """
    link = target_dir / skill_path.name
    repo_skill = skill_path.resolve()

    if link.is_symlink():
        try:
            if link.resolve() == repo_skill:
                return f"= {skill_path.name} already linked"
        except OSError:
            pass
        if dry_run:
            return f"~ {skill_path.name} would repoint"
        link.unlink()
        link.symlink_to(repo_skill)
        return f"~ {skill_path.name} repointed"

    if link.exists():
        if not force:
            return f"! {skill_path.name} exists but is not a symlink (skipping)"
        if dry_run:
            return f"+ {skill_path.name} would replace with symlink"
        link.unlink()
        link.symlink_to(repo_skill)
        return f"+ {skill_path.name} replaced with symlink"

    if dry_run:
        return f"+ {skill_path.name} would link"
    link.symlink_to(repo_skill)
    return f"+ {skill_path.name} linked"


@app.command("link")
def setup_link(
    bin_dir: str | None = typer.Option(None, "--bin-dir", envvar="AET_BIN_DIR", help="Target bin directory."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print actions without executing."),
) -> None:
    """Link ``aet`` into the bin dir."""
    target_dir = Path(bin_dir) if bin_dir else _bin_dir()

    script = _link_target()
    if script is None:
        typer.echo(
            f"  ⚠ no aet console script next to {Path(sys.executable).parent};"
            " install the package first (e.g. `pip install -e .`), then re-run"
            " setup link.",
            err=True,
        )
        raise typer.Exit(1)

    if _is_worktree_copy(script):
        typer.echo(
            f"  ⚠ refusing to link from an ephemeral worktree copy ({script});"
            " run setup link from the main checkout.",
            err=True,
        )
        raise typer.Exit(1)

    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)

    link = target_dir / "aet"
    if link.is_symlink():
        if _link_target_resolves_to(link, script):
            typer.echo(f"  = aet already linked -> {script}")
        else:
            if dry_run:
                typer.echo(f"  ~ aet -> {script} (would update stale symlink)")
            else:
                link.unlink()
                link.symlink_to(script)
                typer.echo(f"  ✓ aet -> {script} (updated stale symlink)")
    elif link.exists():
        if dry_run:
            typer.echo(f"  ! aet exists in {target_dir} and is not a symlink (would skip)")
        else:
            typer.echo(
                f"  ⚠ aet exists in {target_dir} and is not a symlink. Skipping.",
                err=True,
            )
    else:
        if dry_run:
            typer.echo(f"  + aet -> {script} (would create symlink)")
        else:
            link.symlink_to(script)
            typer.echo(f"  ✓ aet -> {script}")

    if str(target_dir) not in os.environ.get("PATH", "").split(os.pathsep):
        typer.echo(f"\n⚠ {target_dir} is not on your PATH. Add it to your shell profile:")
        typer.echo(f'    export PATH="{target_dir}:$PATH"')


@app.command("skills")
def setup_skills(
    skills_dir: str | None = typer.Option(
        None, "--skills-dir", envvar="AET_SKILLS_DIR", help="Target skills directory."
    ),
    agent: str | None = typer.Option(
        None, "--agent", envvar="AGENT", help="Target agent: claude-code, kimi, cursor, generic."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print actions without executing."),
    force: bool = typer.Option(False, "--force", help="Replace non-symlink collisions with symlinks."),
) -> None:
    """Symlink AE Toolkit skills into agent skills directories."""
    target_dirs = _resolve_target_dirs(skills_dir, agent)
    repo_root = _repo_root()
    skill_root = repo_root / "skills"
    skills = sorted([p for p in skill_root.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()])

    if not skills:
        typer.echo("warning: no skills found in repository", err=True)
        raise typer.Exit(0)

    for target_dir in target_dirs:
        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)
        for skill in skills:
            status = _link_skill(skill, target_dir, dry_run=dry_run, force=force)
            typer.echo(f"  {status}")

    summary = "would link" if dry_run else "linked"
    typer.echo(f"✓ {summary} {len(skills)} skill(s) to {len(target_dirs)} director(y/ies)")


@app.command("verify")
def setup_verify(
    bin_dir: str | None = typer.Option(None, "--bin-dir", envvar="AET_BIN_DIR", help="Target bin directory."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print actions without executing."),
) -> None:
    """Verify that the installed `aet` on PATH matches the expected link.

    Resolves what `aet` actually runs on PATH and reports when it is not the
    copy just installed. Also prints the resolved trunk branch and how it was
    derived (config, detected from ``refs/remotes/origin/HEAD``, or fallback
    to ``main``). Read-only: never edits PATH, shell profiles, or the link
    itself. Exits 0 even when shadowed — the install succeeded, but the user
    will experience a different copy.
    """
    target_dir = Path(bin_dir) if bin_dir else _bin_dir()
    expected = _link_target()
    link = target_dir / "aet"

    if dry_run:
        typer.echo("  (dry run — would verify aet link against PATH)")

    if expected is None:
        typer.echo(
            f"  ⚠ no aet console script next to {Path(sys.executable).parent};"
            " install the package first.",
            err=True,
        )
        raise typer.Exit(1)

    repo_root = _repo_root()
    config_path = str(repo_root / ".agents" / "aet-work.json")
    try:
        config, config_source = resolve_config_with_source(config_path)
        mode, mode_provenance = resolve_integration_mode_with_provenance(config_path)
        integration = resolve_integration_branch(repo_root, config)
        trunk = resolve_trunk_branch(repo_root, config)
    except FileNotFoundError:
        typer.echo(
            "  ⚠ could not resolve config: git is not available on PATH",
            err=True,
        )
    else:
        typer.echo(f"  integration_mode: {mode} ({mode_provenance})")
        integration_provenance = _format_branch_provenance(
            integration.provenance, config_source
        )
        typer.echo(f"  integration_branch: {integration.ref} ({integration_provenance})")
        trunk_provenance = _format_branch_provenance(trunk.provenance, config_source)
        typer.echo(f"  trunk: {trunk.ref} ({trunk_provenance})")

    path_aet = shutil.which("aet", path=os.environ.get("PATH"))

    if link.is_symlink():
        try:
            link_target = link.resolve(strict=True)
        except OSError:
            typer.echo(f"  ⚠ {link} is dangling (target does not exist)", err=True)
            if path_aet and Path(path_aet).resolve() != expected:
                typer.echo(f"  ⚠ PATH `aet` resolves to {path_aet}, not {expected}", err=True)
            elif path_aet:
                typer.echo(f"  = PATH `aet` resolves to {expected}")
            else:
                typer.echo("  ⚠ no `aet` found on PATH", err=True)
            raise typer.Exit(0)

        if link_target == expected:
            if path_aet and Path(path_aet).resolve() != expected:
                typer.echo(f"  = {link} -> {expected}")
                typer.echo(
                    f"  ⚠ another `aet` on PATH shadows this install: {path_aet}",
                    err=True,
                )
            else:
                typer.echo(f"  = aet already linked -> {expected}")
            raise typer.Exit(0)

        # Link exists but points elsewhere.
        typer.echo(f"  ⚠ {link} -> {link_target}, expected {expected}", err=True)
        if path_aet and Path(path_aet).resolve() != expected:
            typer.echo(f"  ⚠ PATH `aet` resolves to {path_aet}", err=True)
        raise typer.Exit(0)

    if link.exists():
        typer.echo(
            f"  ⚠ {link} exists and is not a symlink; cannot verify",
            err=True,
        )
        if path_aet:
            typer.echo(f"  = PATH `aet` resolves to {path_aet}")
        raise typer.Exit(0)

    # No link in target dir; just report what PATH resolves to.
    if path_aet is None:
        typer.echo("  ⚠ no `aet` found on PATH", err=True)
    elif Path(path_aet).resolve() == expected:
        typer.echo(f"  = PATH `aet` resolves to {expected}")
    else:
        typer.echo(f"  = PATH `aet` resolves to {path_aet}")
        typer.echo(
            f"  ⚠ PATH `aet` is not the expected install at {expected}",
            err=True,
        )
    raise typer.Exit(0)


@app.command("bootstrap")
def setup_bootstrap(
    path: str | None = typer.Option(
        None,
        "--path",
        help="Project root to write .gitignore into (default: current directory).",
    ),
) -> None:
    """Write AET ignore entries to the project ``.gitignore``."""
    repo_root = Path(path).expanduser().resolve() if path else Path.cwd()
    added = write_aet_gitignore_entries(repo_root)
    if added:
        for entry in added:
            typer.echo(f"  + {entry}")
        typer.echo(f"✓ wrote {len(added)} AET ignore entries to .gitignore")
    else:
        typer.echo("= all AET ignore entries already present")
