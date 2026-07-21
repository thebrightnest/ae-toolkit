"""`aet setup` subcommand group."""

from __future__ import annotations

import os
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
