"""CLI adapter for spawning agent sessions."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aet import session_log_agy, session_log_claude
from aet import usage as usage_lib

# Flags each usage mode needs appended to a headless invocation. Modes absent
# from this map (e.g. kimi's "wire-file", read post-exit from on-disk session
# files) need no flags — the tee already captures what they parse from.
_USAGE_MODE_FLAGS: dict[str, tuple[str, ...]] = {
    "json-envelope": ("--output-format", "json"),
}


@dataclass(frozen=True)
class CLIAdapter:
    """Configuration for invoking an AI coding agent CLI.

    The orchestrator handles the working directory via ``subprocess.run(cwd=...)``,
    so ``workdir_flag`` is ``None`` for CLIs that do not expose a dedicated
    work-directory flag (e.g. kimi, claude). ``usage_mode`` names the CLI's
    machine-readable usage output mode (parsed by ``usage.parse_usage``), or
    ``None`` when the CLI emits no usage data.

    ``stall_timeout`` and ``wall_backstop`` are supervision defaults for this
    adapter: how long a headless session may show no liveness signal before
    the watchdog kills it, and the coarse wall-clock ceiling above that
    interval. With hybrid liveness these values are uniform across adapters
    because the stall timeout is a backstop for true death, not a proxy for
    per-CLI output cadence (ADR-053, superseded in part by the liveness
    redesign). They are adapter data, not configuration.
    """

    name: str
    bin: str
    prompt_flag: str
    workdir_flag: str | None
    headless_flag: str | None
    usage_mode: str | None = None
    stall_timeout: float = 7200.0
    wall_backstop: float = 7200.0

    def build_cmd(
        self,
        prompt: str,
        workdir: str | None = None,
        headless: bool = True,
    ) -> list[str]:
        """Build the CLI invocation list."""
        cmd = [self.bin]
        if headless and self.headless_flag is not None:
            cmd.append(self.headless_flag)
        if headless and self.usage_mode is not None:
            # Before the prompt flag: some CLIs consume the token after -p as
            # the prompt value, so trailing flags would break the invocation.
            cmd.extend(_USAGE_MODE_FLAGS.get(self.usage_mode, ()))
        if self.name == "agy":
            model = os.environ.get("AET_AGY_MODEL", "gemini-3.7-flash")
            effort = os.environ.get("AET_AGY_EFFORT", "high")
            if model:
                cmd.extend(["--model", model])
            if effort:
                cmd.extend(["--effort", effort])
        if self.prompt_flag:
            cmd.extend([self.prompt_flag, prompt])
        else:
            cmd.append(prompt)
        if workdir and self.workdir_flag:
            cmd.extend([self.workdir_flag, workdir])
        return cmd

    def resolve_session_ref(
        self, output: str, workdir: str | None = None
    ) -> str | None:
        """Return an identifier for this adapter's session log, or ``None``.

        The identifier is adapter-defined: a session id for both kimi and
        Claude, or conversation id for Antigravity. It is intentionally not
        a filesystem path — paths go stale when an archive moves; the
        identifier plus the documented resolution rule in
        ``docs/telemetry-guide.md`` survives relocation (ADR-031).

        An unresolvable session returns ``None``; the orchestrator turns that
        into zero observed ``test_run`` records and a null
        ``session_identifier`` on the stage record.
        """
        if self.name == "kimi":
            return usage_lib.resolve_kimi_session_id_from_output(output)
        if self.name == "claude":
            return _resolve_claude_session_id(output, workdir)
        if self.name == "agy":
            return _resolve_agy_session_id(output)
        return None


ADAPTERS: dict[str, CLIAdapter] = {
    "kimi": CLIAdapter(
        name="kimi",
        bin="kimi",
        prompt_flag="-p",
        workdir_flag=None,
        headless_flag=None,
        # Usage lives in ~/.kimi-code session wire files (verified 0.23.6),
        # read post-exit via the resume hint in captured stdout.
        usage_mode="wire-file",
        # Hybrid liveness uses process-tree activity and run-log writes, so the
        # stall timeout is the same uniform backstop for every adapter.
        stall_timeout=7200.0,
        wall_backstop=7200.0,
    ),
    "claude": CLIAdapter(
        name="claude",
        bin="claude",
        prompt_flag="-p",
        workdir_flag=None,
        headless_flag="--dangerously-skip-permissions",
        usage_mode="json-envelope",
        # Hybrid liveness uses process-tree activity and run-log writes, so the
        # stall timeout is the same uniform backstop for every adapter.
        stall_timeout=7200.0,
        wall_backstop=7200.0,
    ),
    "agy": CLIAdapter(
        name="agy",
        bin="agy",
        prompt_flag="-p",
        workdir_flag=None,
        headless_flag="--dangerously-skip-permissions",
        usage_mode="json-envelope",
        stall_timeout=7200.0,
        wall_backstop=7200.0,
    ),
}


def resolve_cli_adapter(cli_bin: str | None = None) -> CLIAdapter:
    """Resolve the CLI adapter using explicit bin or environment."""
    if cli_bin:
        for adapter in ADAPTERS.values():
            if adapter.bin == cli_bin or cli_bin.endswith(adapter.bin):
                return adapter
        raise ValueError(f"Unsupported CLI: {cli_bin}")

    env_bin = os.environ.get("AET_CLI_BIN")
    if env_bin:
        return resolve_cli_adapter(env_bin)

    for adapter in ADAPTERS.values():
        if shutil.which(adapter.bin):
            return adapter

    raise RuntimeError("No supported AI coding agent CLI found on PATH.")


def _resolve_claude_session_id(output: str, workdir: str | None) -> str | None:
    """Resolve a Claude session id from the JSON envelope.

    The envelope's ``session_id`` is the identifier; the transcript's own
    ``cwd`` record confirms the match. A missing workdir, unparseable envelope,
    missing transcript, or cwd mismatch all resolve to ``None`` — never a
    guessed identifier (ADR-031).
    """
    if not output or not workdir:
        return None
    session_id = _extract_claude_session_id(output)
    if session_id is None:
        return None
    # Claude writes transcripts under the cwd slug. A symlinked worktree
    # (e.g. ``.worktrees/foo`` -> real path) must resolve to the real cwd
    # before slugging, or the transcript lookup misses.
    resolved_workdir = str(Path(workdir).resolve())
    candidate = session_log_claude.transcript_path_for(resolved_workdir, session_id)
    try:
        with candidate.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                if len(line) > usage_lib._MAX_WIRE_LINE_CHARS:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if isinstance(record, dict) and _cwd_matches(
                    record.get("cwd"), workdir
                ):
                    return session_id
    except OSError:
        pass
    return None


def _cwd_matches(recorded_cwd: Any, workdir: str) -> bool:
    """Return True when ``recorded_cwd`` resolves to the same path as ``workdir``.

    Symlinked worktrees (e.g. ``.worktrees/foo`` pointing elsewhere) must not
    silently fail the cwd confirmation because the CLI logged the real path.
    """
    if not isinstance(recorded_cwd, str):
        return False
    try:
        return Path(recorded_cwd).resolve() == Path(workdir).resolve()
    except OSError:
        return False


def _extract_claude_session_id(output: str) -> str | None:
    """Extract the session id from Claude's JSON envelope, or ``None``."""
    text = output
    if len(text) > usage_lib.TAIL_SCAN_BYTES:
        text = text[-usage_lib.TAIL_SCAN_BYTES:]
    stripped = text.strip()
    if stripped:
        try:
            doc = json.loads(stripped)
        except ValueError:
            doc = None
        if isinstance(doc, list):
            for element in reversed(doc):
                if isinstance(element, dict):
                    sid = element.get("session_id")
                    if isinstance(sid, str) and sid:
                        return sid
        elif isinstance(doc, dict):
            sid = doc.get("session_id")
            if isinstance(sid, str) and sid:
                return sid
    result = usage_lib._find_result_element(text)
    if isinstance(result, dict):
        sid = result.get("session_id")
        if isinstance(sid, str) and sid:
            return sid
    return None


def _resolve_agy_session_id(output: str) -> str | None:
    """Resolve an Antigravity conversation id from the JSON envelope.

    The envelope's ``conversation_id`` is the identifier; confirmed by checking
    that the transcript exists on disk.
    """
    if not output:
        return None
    conv_id = usage_lib.resolve_agy_conversation_id_from_output(output)
    if conv_id is None or not session_log_agy.is_conversation_id(conv_id):
        return None
    transcript_path = session_log_agy.transcript_path_for(conv_id)
    if transcript_path.is_file():
        return conv_id
    return None
