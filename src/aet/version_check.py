"""Version currency awareness: is a newer ``aet`` release available?

Compares the installed version against the newest stable release tag on the
toolkit remote. Remote lookups use ``git ls-remote`` (no API token, no rate
limit) and are cached on disk for 24 hours so everyday commands never pay for
a network round trip.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_REMOTE_URL = "https://github.com/thebrightnest/ae-toolkit"
REMOTE_TIMEOUT_SECONDS = 5.0
CACHE_TTL_SECONDS = 24 * 60 * 60
CACHE_SOURCE = "git-ls-remote"

_VERSION_RE = re.compile(
    r"^v?(\d+)\.(\d+)\.(\d+)"
    r"(?:-(?P<semver_pre>[0-9A-Za-z.-]+)|(?P<pep440_pre>(?:\.?(?:a|b|rc|dev)\d*)+))?"
    r"(?:\+[0-9A-Za-z.-]+)?$"
)


def parse_semver(value: str) -> tuple | None:
    """Return a comparable key for *value* (``1.2.3`` or ``v1.2.3``), or None.

    A release sorts above any of its prereleases (``1.2.0-rc.1 < 1.2.0``).
    PEP 440 pre/dev suffixes from source installs (``1.2.1.dev4+gabc``) also
    count as prereleases; build metadata after ``+`` is ignored.
    """
    match = _VERSION_RE.match(value.strip())
    if match is None:
        return None
    major, minor, patch = (int(part) for part in match.groups()[:3])
    prerelease = match.group("semver_pre") or match.group("pep440_pre")
    if prerelease is None:
        pre_key: tuple = (1,)
    else:
        parts = re.findall(r"\d+|[A-Za-z]+", prerelease)
        pre_key = (0, tuple((0, int(part), "") if part.isdigit() else (1, 0, part) for part in parts))
    return (major, minor, patch, pre_key)


def is_newer_version(latest: str, current: str) -> bool:
    """True when *latest* is a strictly newer SemVer than *current*."""
    latest_key = parse_semver(latest)
    current_key = parse_semver(current)
    if latest_key is None or current_key is None:
        return False
    return latest_key > current_key


def fetch_latest_remote_tag(
    remote_url: str = DEFAULT_REMOTE_URL, *, timeout: float = REMOTE_TIMEOUT_SECONDS
) -> str | None:
    """Return the newest stable release version tagged on *remote_url*.

    The ``v`` prefix is stripped (``v1.20.0`` -> ``1.20.0``); prerelease and
    non-SemVer tags are ignored. Returns None when git is unavailable, the
    remote is unreachable, the query times out, or no release tag exists.
    """
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--tags", "--sort=-v:refname", remote_url],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None

    best: tuple | None = None
    best_version: str | None = None
    for line in result.stdout.splitlines():
        _, _, ref = line.partition("\t")
        if not ref.startswith("refs/tags/") or ref.endswith("^{}"):
            continue
        tag = ref[len("refs/tags/") :]
        key = parse_semver(tag)
        if key is None or key[3] != (1,):
            continue
        if best is None or key > best:
            best, best_version = key, tag.removeprefix("v")
    return best_version


def cache_path() -> Path:
    """Location of the version cache, alongside the managed install data."""
    data_dir = os.environ.get("AET_DATA_DIR") or str(Path.home() / ".local" / "share" / "ae-toolkit")
    return Path(data_dir) / "version-cache.json"


def read_version_cache(
    *, path: Path | None = None, now: float | None = None, ttl: float = CACHE_TTL_SECONDS
) -> dict[str, Any] | None:
    """Return the cached lookup if it is fresher than *ttl*, else None.

    A missing, unreadable, or malformed cache reads as None. ``latest_version``
    is None when the last lookup failed (offline, no release tags).
    """
    path = path or cache_path()
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(entry, dict):
        return None
    checked_at = entry.get("checked_at")
    latest = entry.get("latest_version")
    if not isinstance(checked_at, (int, float)) or not (latest is None or isinstance(latest, str)):
        return None
    current_time = time.time() if now is None else now
    if current_time - checked_at > ttl:
        return None
    return entry


def write_version_cache(latest_version: str | None, *, path: Path | None = None, now: float | None = None) -> None:
    """Record a lookup result. Write failures are ignored: the cache is advisory."""
    path = path or cache_path()
    entry = {
        "latest_version": latest_version,
        "checked_at": time.time() if now is None else now,
        "source": CACHE_SOURCE,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(entry), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


_FALSY_FLAG_VALUES = {"", "0", "false", "no", "off"}


def _flag_set(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() not in _FALSY_FLAG_VALUES


def _stdout_is_tty() -> bool:
    try:
        return sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def update_check_suppressed() -> bool:
    """True when ``AET_NO_UPDATE_CHECK`` or ``CI`` is set, or stdout is not a TTY."""
    return _flag_set("AET_NO_UPDATE_CHECK") or _flag_set("CI") or not _stdout_is_tty()


@dataclass(frozen=True)
class VersionStatus:
    """Installed version and the newest known release (None when unknown)."""

    current: str
    latest: str | None

    @property
    def update_available(self) -> bool:
        return self.latest is not None and is_newer_version(self.latest, self.current)


def version_status(
    current: str, *, refresh: bool = False, remote_url: str = DEFAULT_REMOTE_URL
) -> VersionStatus | None:
    """Return the currency of *current*, or None when checks are suppressed.

    With ``refresh=False`` only the on-disk cache is consulted, so the call
    never touches the network. With ``refresh=True`` a missing or expired
    cache is repopulated from the remote (bounded by a short timeout).
    """
    if update_check_suppressed():
        return None
    entry = read_version_cache()
    if entry is not None:
        return VersionStatus(current=current, latest=entry["latest_version"])
    if not refresh:
        return VersionStatus(current=current, latest=None)
    latest = fetch_latest_remote_tag(remote_url)
    write_version_cache(latest)
    return VersionStatus(current=current, latest=latest)
