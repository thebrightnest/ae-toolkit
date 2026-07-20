"""aet harness merge guard — detect the active harness and generate a per-provider guard.

The guard blocks ``gh pr merge`` at the harness's own tool-call layer, which is the
only surface that can refuse the command under session auto/bypass mode. The
precedent is ``aet-setup/bin/hooks``: a self-contained, idempotent, non-clobbering
generator that writes harness-local config (Mode-1 non-invasive).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Marker embedded in every artifact this module generates. Idempotent rewrites
# and non-clobbering checks rely on it, mirroring the pre-push shim generator.
GUARD_MARKER = "aet:generated merge guard"

# Filesystem markers that map to a harness adapter. Keep detection as a pure
# function over repo/home markers; extend here for Phase 6 providers.
_HARNESS_MARKERS = {
    ".claude": "claude-code",
    ".kimi-code": "kimi",
}


class _ClaudeAdapter:
    """Claude Code PreToolUse guard adapter.

    Generates a guard script plus a ``.claude/settings*.json`` hook entry that
    refuses Bash tool calls matching ``gh pr merge``. PreToolUse hooks run even
    under session auto/bypass mode, so this closes the incident hole.
    """

    name = "Claude Code"

    # Guard script embedded so the generated artifact is self-contained and
    # runnable without importing this module from the operator's harness config.
    # Uses __AET_MARKER__ substitution (not str.format) because the script body
    # contains JSON braces that would be misinterpreted as format placeholders.
    _GUARD_SCRIPT = '''#!/usr/bin/env python3
# __AET_MARKER__ — regenerate with `aet harness-guard install`; do not edit by hand.
import json
import re
import sys

BLOCK_RE = re.compile(r"^\\s*gh\\s+pr\\s+merge\\b")
BLOCK_MESSAGE = (
    "AET merge guard: refusing `gh pr merge`. "
    "Use the sanctioned merge path (`aet desk merge` or the GitHub UI)."
)


def main() -> int:
    payload = json.load(sys.stdin)
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("input", {})
    if tool_name != "Bash":
        return 0
    command = tool_input.get("command", "")
    if BLOCK_RE.match(command):
        print(BLOCK_MESSAGE, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

    def generate_merge_guard(self, repo_root: Path) -> int:
        """Write the Claude Code PreToolUse merge guard; idempotent, non-clobbering."""
        claude_dir = repo_root / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)

        script_path = claude_dir / "harness-merge-guard.py"
        settings_path = claude_dir / "settings.json"

        # Write / overwrite only our own generated script.
        script_body = self._GUARD_SCRIPT.replace("__AET_MARKER__", GUARD_MARKER)
        script_path.write_text(script_body, encoding="utf-8")
        script_path.chmod(0o755)

        hook_entry = {
            "hooks": {
                "PreToolUse": [
                    str(script_path.relative_to(repo_root)),
                ],
            },
        }

        if settings_path.exists():
            existing = settings_path.read_text(encoding="utf-8", errors="ignore")
            if GUARD_MARKER not in existing:
                print(
                    f"warning: an existing non-AET .claude/settings.json is present at "
                    f"{settings_path}; leaving it in place. Merge the PreToolUse hook "
                    f"entry manually or move the file aside and re-run "
                    f"`aet harness-guard install`.",
                    file=sys.stderr,
                )
                return 1
            # Prior AET settings: rewrite in place (idempotent).
        else:
            settings_path.parent.mkdir(parents=True, exist_ok=True)

        settings_path.write_text(
            json.dumps(hook_entry, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"installed claude-code merge guard -> {settings_path}")
        return 0


# Lightweight registry. Deliberately a dict + protocol, not a class hierarchy.
ADAPTERS: dict[str, object] = {
    "claude-code": _ClaudeAdapter(),
}


def detect_harness(repo_root: Path, override: str | None = None) -> str | None:
    """Detect the operating harness from workspace markers.

    Args:
        repo_root: project root to inspect.
        override: explicit harness id that beats filesystem detection.

    Returns:
        The harness id, or None when no recognized marker is found.
    """
    if override:
        return override
    for marker, harness_id in _HARNESS_MARKERS.items():
        if (repo_root / marker).exists():
            return harness_id
    return None


def install_merge_guard(repo_root: Path, harness_id: str | None = None) -> int:
    """Install the merge guard for the detected (or explicit) harness.

    Fail-safe: an undetected or unsupported harness prints a named gap message
    and exits non-zero — never silently passes.
    """
    harness_id = harness_id or detect_harness(repo_root)
    if harness_id is None:
        print(
            "no merge-guard adapter for unknown harness — deferred to Phase 6",
            file=sys.stderr,
        )
        return 1
    adapter = ADAPTERS.get(harness_id)
    if adapter is None:
        print(
            f"no merge-guard adapter for {harness_id} — deferred to Phase 6",
            file=sys.stderr,
        )
        return 1
    return adapter.generate_merge_guard(repo_root)


def check_merge_guard(repo_root: Path) -> int:
    """Report what merge guard is installed for the detected harness."""
    harness_id = detect_harness(repo_root)
    if harness_id is None:
        print("no harness detected; no merge guard installed")
        return 0
    adapter = ADAPTERS.get(harness_id)
    if adapter is None:
        print(
            f"detected harness '{harness_id}' but no merge-guard adapter — "
            "deferred to Phase 6"
        )
        return 0
    settings_path = repo_root / ".claude" / "settings.json"
    installed = settings_path.exists() and GUARD_MARKER in settings_path.read_text(
        encoding="utf-8", errors="ignore"
    )
    status = "installed" if installed else "not installed"
    print(f"{harness_id}: merge guard {status}")
    return 0


def _resolve_repo_root(repo_arg: str | None) -> Path:
    if repo_arg:
        return Path(repo_arg).resolve()
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        print("error: not inside a git repository", file=sys.stderr)
        sys.exit(2)
    return Path(out.stdout.strip())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aet harness-guard",
        description="Detect the active harness and generate a per-provider merge guard.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    install = sub.add_parser(
        "install", help="Detect the harness and install the matching merge guard."
    )
    install.add_argument(
        "--repo", default=None, help="Repo root (default: current git toplevel)."
    )
    install.add_argument(
        "--harness",
        default=None,
        help="Harness id override (default: auto-detect from workspace markers).",
    )

    check = sub.add_parser(
        "check", help="Report the installed merge guard for the detected harness."
    )
    check.add_argument(
        "--repo", default=None, help="Repo root (default: current git toplevel)."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = _resolve_repo_root(args.repo)
    if args.command == "install":
        return install_merge_guard(repo_root, harness_id=args.harness)
    if args.command == "check":
        return check_merge_guard(repo_root)
    return 2


if __name__ == "__main__":
    sys.exit(main())
