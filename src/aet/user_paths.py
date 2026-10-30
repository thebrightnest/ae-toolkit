"""User-level path resolvers for the AE Toolkit."""

from __future__ import annotations

import os
from pathlib import Path

_REAL_HOME: Path = Path.home()

# Fallback root when AET_HOME is unset. Tests patch this attribute so that
# operations under patch.dict(os.environ, clear=True) remain isolated.
_FALLBACK_AET_HOME: Path = _REAL_HOME / ".aet"


def aet_home() -> Path:
    """Return the AET home directory root, respecting ``AET_HOME``.

    When ``HOME`` is explicitly redirected to a test directory (distinct from
    the user's real home), paths resolve under ``$HOME/.aet`` unless ``AET_HOME``
    is explicitly placed within that redirected home. When running under the
    real home (or with ``HOME`` cleared), ``AET_HOME`` governs, falling back
    to ``_FALLBACK_AET_HOME``.
    """
    home_env = os.environ.get("HOME")
    if home_env:
        try:
            home_path = Path(home_env).expanduser().resolve()
            if home_path != _REAL_HOME.resolve():
                aet_home_env = os.environ.get("AET_HOME")
                if aet_home_env:
                    aet_path = Path(aet_home_env).expanduser().resolve()
                    if aet_path.is_relative_to(home_path):
                        return aet_path
                return home_path / ".aet"
        except (ValueError, RuntimeError):
            pass

    env = os.environ.get("AET_HOME")
    if env:
        return Path(env).expanduser()
    return Path(_FALLBACK_AET_HOME)


def telemetry_archive_dir() -> Path:
    """Return the telemetry archive root, respecting ``AET_TELEMETRY_ARCHIVE_DIR``."""
    env = os.environ.get("AET_TELEMETRY_ARCHIVE_DIR")
    if env:
        return Path(env).expanduser()
    return aet_home() / "telemetry"


def reports_dir() -> Path:
    """Return the gate-evidence reports archive root, respecting ``AET_REPORTS_DIR``."""
    env = os.environ.get("AET_REPORTS_DIR")
    if env:
        return Path(env).expanduser()
    return aet_home() / "reports"


def user_config_path(slug: str | Path) -> Path:
    """Return the external user config path for a project slug, respecting ``AET_USER_CONFIG``."""
    env = os.environ.get("AET_USER_CONFIG")
    if env:
        return Path(env).expanduser()
    return aet_home() / str(slug) / "config.json"
