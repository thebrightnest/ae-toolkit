"""`aet update` — update a managed install to the newest release tag.

A managed install is the layout ``scripts/install.sh`` creates under
``AET_DATA_DIR`` (default ``~/.local/share/ae-toolkit``): a git clone in
``repo/`` checked out at a release tag and a dedicated venv in ``venv/``.
Development checkouts are never touched; they update with ``git pull``.

The update re-runs the installer's steps against the existing clone: fetch
tags, check out the target tag, reinstall the package, then relink skills and
the binary using the newly installed ``aet``. If any step after the checkout
fails, the clone is restored to the previous commit and reinstalled, so a
failed update leaves the previous version in place (ADR-042).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import typer

from aet.version_check import fetch_latest_remote_tag, is_newer_version, parse_semver, write_version_cache

_STABLE = (1,)


@dataclass(frozen=True)
class ManagedInstall:
    """Paths of a managed install."""

    data_dir: Path

    @property
    def repo(self) -> Path:
        return self.data_dir / "repo"

    @property
    def venv(self) -> Path:
        return self.data_dir / "venv"

    @property
    def python(self) -> Path:
        return self.venv / "bin" / "python"

    @property
    def aet(self) -> Path:
        return self.venv / "bin" / "aet"


class UpdateError(Exception):
    """A step failed; the message is shown to the user."""


def _data_dir() -> Path:
    return Path(os.environ.get("AET_DATA_DIR") or Path.home() / ".local" / "share" / "ae-toolkit")


def _running_prefix() -> Path:
    """The environment the running ``aet`` was installed into."""
    return Path(sys.prefix)


def _source_checkout() -> Path | None:
    """The git working tree this package is running from, if any."""
    root = Path(__file__).resolve().parents[3]
    return root if (root / ".git").exists() else None


def _current_version() -> str:
    from importlib.metadata import version

    return version("aet")


def _interactive() -> bool:
    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def _run(cmd: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", **(env or {})},
    )


def _git(install: ManagedInstall, *args: str) -> subprocess.CompletedProcess:
    return _run(["git", "-C", str(install.repo), *args])


def _check(result: subprocess.CompletedProcess, step: str) -> str:
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise UpdateError(f"{step} failed" + (f": {detail}" if detail else ""))
    return result.stdout


def _resolve_install() -> ManagedInstall:
    """Return the managed install the running ``aet`` belongs to, or exit."""
    install = ManagedInstall(_data_dir())
    managed = (install.repo / ".git").exists() and _same_path(_running_prefix(), install.venv)
    if managed:
        return install
    checkout = _source_checkout()
    if checkout is not None:
        typer.echo(
            f"Development checkout detected at {checkout}. To update, use 'git pull && make install-skills'.",
            err=True,
        )
    else:
        typer.echo(
            f"No managed installation found at {install.data_dir}. Re-run the installer to update:\n"
            "  curl -fsSL https://raw.githubusercontent.com/thebrightnest/ae-toolkit/main/scripts/install.sh | bash",
            err=True,
        )
    raise typer.Exit(1)


def _same_path(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return False


def _latest_stable(tags: list[str]) -> str | None:
    """Return the newest stable SemVer tag name from *tags*."""
    best: tuple | None = None
    best_tag: str | None = None
    for tag in tags:
        key = parse_semver(tag)
        if key is None or key[3] != _STABLE:
            continue
        if best is None or key > best:
            best, best_tag = key, tag
    return best_tag


def _local_tag(install: ManagedInstall, requested: str) -> str | None:
    """Return the tag name in the clone matching *requested* (``v`` optional)."""
    candidates = [requested, f"v{requested}"] if not requested.startswith("v") else [requested, requested[1:]]
    for candidate in candidates:
        if _git(install, "rev-parse", "--verify", "--quiet", f"refs/tags/{candidate}^{{commit}}").returncode == 0:
            return candidate
    return None


def _install_command(install: ManagedInstall) -> list[str]:
    uv = shutil.which("uv")
    if uv:
        return [uv, "pip", "install", "--python", str(install.python), str(install.repo)]
    return [str(install.python), "-m", "pip", "install", str(install.repo)]


def _planned_steps(install: ManagedInstall, tag: str) -> list[str]:
    return [
        "git fetch --tags origin",
        f"git checkout tags/{tag}",
        " ".join(_install_command(install)),
        f"AET_REPO_ROOT={install.repo} {install.aet} setup skills",
        f"{install.aet} setup link",
        f"refresh {install.data_dir / 'version-cache.json'}",
    ]


def _display(version: str) -> str:
    return f"v{version.removeprefix('v')}"


def _run_check(install: ManagedInstall, current: str, tag: str | None) -> None:
    """Report current vs latest release and the steps an update would run."""
    remote = _git(install, "remote", "get-url", "origin").stdout.strip()
    latest = fetch_latest_remote_tag(remote) if remote else None
    if latest is None:
        typer.echo(f"error: could not reach {remote or 'origin'} to look up release tags", err=True)
        raise typer.Exit(1)

    typer.echo(f"current: {_display(current)}")
    typer.echo(f"latest:  {_display(latest)}")
    if tag is None and not is_newer_version(latest, current):
        typer.echo("aet is up to date.")
        return
    target = tag or (_local_tag(install, latest) or f"v{latest}")
    if tag is None:
        typer.echo("update available. `aet update` would run:")
    else:
        typer.echo(f"`aet update --tag {tag}` would run:")
    typer.echo(f"  (git commands run in {install.repo})")
    for step in _planned_steps(install, target):
        typer.echo(f"  {step}")


def _apply(install: ManagedInstall, target: str) -> None:
    """Check out *target*, reinstall, and relink. Raises UpdateError on failure."""
    _check(_git(install, "checkout", "--quiet", f"tags/{target}"), f"git checkout tags/{target}")
    _check(_run(_install_command(install)), "package install")
    _check(_run([str(install.aet), "setup", "skills"], env={"AET_REPO_ROOT": str(install.repo)}), "aet setup skills")
    _check(_run([str(install.aet), "setup", "link"]), "aet setup link")


def _rollback(install: ManagedInstall, previous_ref: str, previous_version: str) -> None:
    try:
        _check(_git(install, "checkout", "--quiet", previous_ref), "restoring the previous checkout")
        _check(_run(_install_command(install)), "reinstalling the previous version")
    except UpdateError as exc:
        typer.echo(f"error: rollback failed: {exc}", err=True)
        typer.echo("The install may be inconsistent; re-run the installer to repair it.", err=True)
        return
    typer.echo(f"rolled back to {_display(previous_version)}", err=True)


def update(
    check: bool = typer.Option(False, "--check", help="Show current vs latest release and the planned steps."),
    tag: str | None = typer.Option(None, "--tag", help="Update to this release tag instead of the latest."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt."),
) -> None:
    """Update a managed aet install (CLI and skills) to the latest release."""
    install = _resolve_install()
    current = _current_version()

    if check:
        _run_check(install, current, tag)
        return

    if _git(install, "status", "--porcelain", "--untracked-files=no").stdout.strip():
        typer.echo(f"error: {install.repo} has uncommitted changes; refusing to update.", err=True)
        raise typer.Exit(1)

    try:
        _check(_git(install, "fetch", "--quiet", "--tags", "origin"), "git fetch --tags origin")
    except UpdateError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from None

    tags = _git(install, "tag", "--list").stdout.split()
    latest_tag = _latest_stable(tags)
    if tag is not None:
        target = _local_tag(install, tag)
        if target is None:
            typer.echo(f"error: tag {tag} not found in {install.repo}", err=True)
            raise typer.Exit(1)
    else:
        if latest_tag is None:
            typer.echo("error: no release tags found on origin", err=True)
            raise typer.Exit(1)
        target = latest_tag
        if not is_newer_version(target, current):
            write_version_cache(latest_tag.removeprefix("v"))
            typer.echo(f"aet is already up to date ({_display(current)}).")
            return

    if not yes and _interactive() and not typer.confirm(
        f"Update aet {_display(current)} -> {_display(target)}?", default=True
    ):
        raise typer.Exit(1)

    previous_ref = _git(install, "rev-parse", "HEAD").stdout.strip()
    typer.echo(f"Updating aet {_display(current)} -> {_display(target)}...")
    try:
        _apply(install, target)
    except UpdateError as exc:
        typer.echo(f"error: {exc}", err=True)
        _rollback(install, previous_ref, current)
        raise typer.Exit(1) from None

    write_version_cache(latest_tag.removeprefix("v") if latest_tag else None)
    typer.echo(f"✓ aet updated: {_display(current)} -> {_display(target)}")
