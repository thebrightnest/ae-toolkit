#!/usr/bin/env python3
"""Verify the editable aet install matches the current repo state.

Exits 0 if the install is current, 1 otherwise. Prints a reason on stderr.
"""
import importlib.metadata
import pathlib
import re
import subprocess
import sys


def main() -> int:
    repo_dir = pathlib.Path(__file__).resolve().parents[1]
    try:
        import aet
    except ImportError:
        print("aet is not importable", file=sys.stderr)
        return 1

    installed_root = pathlib.Path(aet.__file__).resolve().parents[2]
    if installed_root != repo_dir:
        print(f"wrong path: {installed_root} (expected {repo_dir})", file=sys.stderr)
        return 1

    installed_version = importlib.metadata.version("aet")

    head_proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        cwd=repo_dir,
    )
    if head_proc.returncode != 0:
        print("unable to determine git HEAD", file=sys.stderr)
        return 1
    head = head_proc.stdout.strip()

    tag_proc = subprocess.run(
        ["git", "describe", "--tags", "--exact-match", "HEAD"],
        capture_output=True,
        text=True,
        cwd=repo_dir,
    )
    if tag_proc.returncode == 0:
        expected = tag_proc.stdout.strip().lstrip("v")
        if installed_version != expected:
            print(
                f"expected {expected}, got {installed_version}",
                file=sys.stderr,
            )
            return 1
    else:
        match = re.search(r"\+g([0-9a-f]+)", installed_version)
        if not match or not head.startswith(match.group(1)):
            print(
                f"head {head[:8]} not in version {installed_version}",
                file=sys.stderr,
            )
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
