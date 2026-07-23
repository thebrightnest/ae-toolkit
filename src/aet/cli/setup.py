"""`aet setup` subcommand group."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import typer

app = typer.Typer(help="Setup and bootstrap commands.")


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


def _bin_dir() -> Path:
    """Return the link target dir: ``AET_BIN_DIR`` or ``~/.local/bin``."""
    override = os.environ.get("AET_BIN_DIR")
    return Path(override) if override else Path.home() / ".local" / "bin"


def _link_target() -> Path:
    """Return the canonical target of the ``aet`` symlink.

    The packaging system installs a console script next to the interpreter.
    When that script exists it is the only supported target. The fallback
    exists for source-checkouts that have not installed the console script.
    """
    console_script = Path(sys.executable).parent / "aet"
    if console_script.exists():
        return console_script
    return Path(__file__).resolve()


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
    bin_dir: str | None = typer.Option(None, "--bin-dir", help="Target bin directory."),
) -> None:
    """Link ``aet`` into the bin dir."""
    target_dir = Path(bin_dir) if bin_dir else _bin_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    script = _link_target()
    if _is_worktree_copy(script):
        typer.echo(
            f"  ⚠ refusing to link from an ephemeral worktree copy ({script});"
            " run setup link from the main checkout.",
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


@app.command("skills")
def setup_skills(
    skills_dir: str | None = typer.Option(None, "--skills-dir", help="Target skills directory."),
    agent: str | None = typer.Option(None, "--agent", help="Target agent: claude-code, kimi, cursor, generic."),
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
