"""Closure and settled plan archival helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def archive_plan_file(
    task_id: str,
    repo_root: str | Path | None = None,
) -> Path | None:
    """Move an active or legacy plan file to ``docs/plans/archive/`` at closure.

    Checks if ``docs/plans/active/<task_id>.md`` or ``docs/plans/<task_id>.md``
    exists on disk.

    If present:
      - Creates ``docs/plans/archive/`` if needed.
      - Moves the plan file to ``docs/plans/archive/<task_id>.md``.
      - Stages the destination into git if not git-ignored.
      - Logs: ``✓ Plan archived: docs/plans/archive/<task_id>.md``.
      - Returns the destination :class:`Path`.

    If absent:
      - Logs: ``ℹ Plan archival: No local plan file found at docs/plans/active/<task_id>.md; ``
        ``archive move skipped (spec preserved in task record)``.
      - Returns ``None`` cleanly without failing closure.
    """
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    active_path = root / "docs" / "plans" / "active" / f"{task_id}.md"
    legacy_path = root / "docs" / "plans" / f"{task_id}.md"

    if active_path.is_file():
        src = active_path
    elif legacy_path.is_file():
        src = legacy_path
    else:
        src = None

    if src is None:
        print(
            f"ℹ Plan archival: No local plan file found at docs/plans/active/{task_id}.md; "
            "archive move skipped (spec preserved in task record)"
        )
        return None

    archive_dir = root / "docs" / "plans" / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    dest = archive_dir / f"{task_id}.md"

    shutil.move(str(src), str(dest))

    dest_rel = f"docs/plans/archive/{task_id}.md"
    try:
        check = subprocess.run(
            ["git", "-C", str(root), "check-ignore", "-q", dest_rel],
            capture_output=True,
            text=True,
            check=False,
        )
        is_ignored = check.returncode == 0
    except OSError:
        is_ignored = True

    if not is_ignored:
        try:
            subprocess.run(
                ["git", "-C", str(root), "add", str(dest)],
                capture_output=True,
                text=True,
                check=False,
            )
            if src != dest:
                subprocess.run(
                    ["git", "-C", str(root), "add", "-u", str(src)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
        except OSError:
            pass

    print(f"✓ Plan archived: docs/plans/archive/{task_id}.md")
    return dest
