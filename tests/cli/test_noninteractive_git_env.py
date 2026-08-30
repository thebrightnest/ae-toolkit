"""The CLI entry point stops git from blocking on a prompt nobody can answer.

Filed from a 2026-08-30 incident: in an agent container with an SSH `origin` and
no key loaded, `aet state transition` and `aet gate submit` hung for 180s because
git was free to ask for a passphrase. Every git call the toolkit makes is a
subprocess of the CLI process, so the fix is environmental and applies at
`main()`.

Each test constructs the divergent case rather than the agreeing one: an
operator at a terminal, and a runner with its own ssh invocation, must both come
out unchanged.
"""

from __future__ import annotations

import subprocess
from unittest.mock import patch

from aet.cli.main import _ensure_git_is_noninteractive


def _apply(env: dict, *, isatty: bool, configured_ssh: str = "") -> dict:
    """Run the hook against a controlled environment and return it."""
    completed = subprocess.CompletedProcess(
        args=["git"], returncode=0 if configured_ssh else 1, stdout=configured_ssh, stderr=""
    )
    with (
        patch.dict("os.environ", env, clear=True),
        patch("aet.cli.main.sys.stdin.isatty", return_value=isatty),
        patch("aet.cli.main.subprocess.run", return_value=completed),
    ):
        _ensure_git_is_noninteractive()
        import os

        return dict(os.environ)


def test_terminal_prompt_is_disabled_everywhere() -> None:
    """GIT_TERMINAL_PROMPT is set with or without a terminal: a prompt is never answerable."""
    assert _apply({}, isatty=True)["GIT_TERMINAL_PROMPT"] == "0"
    assert _apply({}, isatty=False)["GIT_TERMINAL_PROMPT"] == "0"


def test_batch_mode_is_forced_without_a_terminal() -> None:
    """No TTY means nobody can answer ssh, so BatchMode can only shorten the failure."""
    env = _apply({}, isatty=False)
    assert "BatchMode=yes" in env["GIT_SSH_COMMAND"]
    assert "ConnectTimeout=5" in env["GIT_SSH_COMMAND"]


def test_batch_mode_is_not_forced_at_a_terminal() -> None:
    """With a terminal there is someone to answer; forcing BatchMode would break them."""
    assert "GIT_SSH_COMMAND" not in _apply({}, isatty=True)


def test_an_explicit_ssh_command_is_left_alone() -> None:
    """A caller that set GIT_SSH_COMMAND outranks the default."""
    env = _apply({"GIT_SSH_COMMAND": "ssh -i /keys/deploy"}, isatty=False)
    assert env["GIT_SSH_COMMAND"] == "ssh -i /keys/deploy"


def test_a_configured_core_sshcommand_is_left_alone() -> None:
    """GIT_SSH_COMMAND outranks core.sshCommand, so setting it would discard a deploy key."""
    env = _apply({}, isatty=False, configured_ssh="ssh -i /keys/deploy")
    assert "GIT_SSH_COMMAND" not in env


def test_an_explicit_terminal_prompt_value_wins() -> None:
    """setdefault, not assignment: a caller that wants prompts keeps them."""
    assert _apply({"GIT_TERMINAL_PROMPT": "1"}, isatty=False)["GIT_TERMINAL_PROMPT"] == "1"
