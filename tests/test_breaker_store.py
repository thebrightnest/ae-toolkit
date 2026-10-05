"""Unit tests for breaker module."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from aet.breaker import BreakerStore


def _init_git_repo(path: Path) -> None:
    resolved = path.resolve()
    subprocess.run(["git", "init", "-q", str(resolved)], check=True)
    subprocess.run(
        ["git", "-C", str(resolved), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(resolved), "config", "user.name", "Test User"],
        check=True,
    )


def test_breaker_remove_task() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        _init_git_repo(repo)

        store = BreakerStore(repo)
        assert store.load() == {}

        # Removing from empty store returns False
        assert store.remove_task("t1") is False

        # Seed with multiple signatures and tasks
        store.save({
            "sig_err": {"t1", "t2"},
            "sig_timeout": {"t1", "t3"},
            "sig_flaky": {"t4"},
        })

        # Remove t1 which is in sig_err and sig_timeout
        removed = store.remove_task("t1")
        assert removed is True

        tally = store.load()
        assert tally == {
            "sig_err": {"t2"},
            "sig_timeout": {"t3"},
            "sig_flaky": {"t4"},
        }

        # Removing a non-existent task returns False and doesn't mutate
        assert store.remove_task("t1") is False
        assert store.load() == tally

        # Remove t2 and t3
        assert store.remove_task("t2") is True
        assert store.remove_task("t3") is True
        assert store.load() == {"sig_flaky": {"t4"}}

        # Remove last remaining task
        assert store.remove_task("t4") is True
        assert store.load() == {}
