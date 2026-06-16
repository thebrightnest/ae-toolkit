"""CLI adapter for spawning agent sessions."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class CLIAdapter:
    """Configuration for invoking an AI coding agent CLI.

    The orchestrator handles the working directory via ``subprocess.run(cwd=...)``,
    so ``workdir_flag`` is ``None`` for CLIs that do not expose a dedicated
    work-directory flag (e.g. kimi, claude).
    """

    name: str
    bin: str
    prompt_flag: str
    workdir_flag: str | None
    headless_flag: str

    def build_cmd(
        self,
        prompt: str,
        workdir: str | None = None,
        headless: bool = True,
    ) -> list[str]:
        """Build the CLI invocation list."""
        cmd = [self.bin]
        if headless and self.headless_flag:
            cmd.append(self.headless_flag)
        if self.prompt_flag:
            cmd.extend([self.prompt_flag, prompt])
        else:
            cmd.append(prompt)
        if workdir and self.workdir_flag:
            cmd.extend([self.workdir_flag, workdir])
        return cmd


ADAPTERS: dict[str, CLIAdapter] = {
    "kimi": CLIAdapter(
        name="kimi",
        bin="kimi",
        prompt_flag="-p",
        workdir_flag=None,
        # kimi's -p mode is already non-interactive and cannot be combined
        # with --yolo or --auto; AET_EXECUTION_MODE=unattended handles gates.
        headless_flag=None,
    ),
    "claude": CLIAdapter(
        name="claude",
        bin="claude",
        prompt_flag="-p",
        workdir_flag=None,
        headless_flag="--dangerously-skip-permissions",
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
