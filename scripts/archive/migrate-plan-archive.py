#!/usr/bin/env python3
"""One-time migration: copy legacy docs/plans/archive/ into ~/.aet/<slug>/plans/archive/.

R-5 relocates settled plans out of the repository. Historical metrics still
need the 264 legacy plan files, so this migration copies them once. The legacy
in-repo directory is left tracked and inert; untracking it is the operator's
call.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from aet import telemetry
from aet.project_id import derive_project_slug, resolve_repo_root


def copy_legacy_plan_archive(
    repo_root: Path,
    dest_root: Path,
    *,
    dry_run: bool = False,
) -> dict[str, object]:
    """Copy every file under ``docs/plans/archive/`` to the plans archive.

    Returns a dict with ``copied``, ``skipped``, ``source_exists``, and ``dest``.
    Existing destination files are skipped so the migration is idempotent.
    """
    src = repo_root / "docs" / "plans" / "archive"
    if not src.exists():
        return {
            "copied": 0,
            "skipped": 0,
            "source_exists": False,
            "dest": str(dest_root),
        }

    if not dry_run:
        dest_root.mkdir(parents=True, exist_ok=True)

    copied = 0
    skipped = 0
    for path in sorted(p for p in src.rglob("*") if p.is_file()):
        rel = path.relative_to(src)
        dest = dest_root / rel
        if dest.exists():
            skipped += 1
            continue
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
        copied += 1

    return {
        "copied": copied,
        "skipped": skipped,
        "source_exists": True,
        "dest": str(dest_root),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Copy legacy docs/plans/archive/ to the machine-local plans archive."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root; defaults to the current git work-tree.",
    )
    parser.add_argument(
        "--project-slug",
        default=None,
        help="Project slug; derived from the repo root when omitted.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be copied without writing anything.",
    )
    args = parser.parse_args(argv)

    repo_root = resolve_repo_root(args.repo_root)
    slug = args.project_slug or derive_project_slug(repo_root)
    dest = telemetry.plans_archive_dir(slug)

    result = copy_legacy_plan_archive(repo_root, dest, dry_run=args.dry_run)

    if not result["source_exists"]:
        print(
            f"Source archive does not exist: {repo_root / 'docs' / 'plans' / 'archive'}",
            file=sys.stderr,
        )
        return 0

    prefix = "[dry-run] Would copy" if args.dry_run else "Copied"
    print(
        f"{prefix} {result['copied']} plan(s) to {result['dest']}; "
        f"skipped {result['skipped']} already present."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
