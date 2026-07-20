#!/usr/bin/env python3
"""One-shot migration of telemetry/report project dirs from an old slug to a new one.

Renames ``{archive}/OLD_SLUG`` → ``{archive}/NEW_SLUG`` under both the
telemetry archive and the reports archive (gate evidence shares the slug).
Dry-run by default; use ``--apply`` to perform the renames.

Safe by construction:

- Slug args are validated (relative, no ``..``, at most 2 segments) and the
  resolved destination must stay under the archive root.
- If a destination run dir already exists, the move is refused and the script
  exits non-zero — it never clobbers existing run data.
- Idempotent: when OLD is absent and NEW is present there is nothing to do.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path, PurePosixPath

_SCRIPT_DIR = Path(__file__).resolve().parent
from aet.evidence import reports_dir  # noqa: E402
from aet.telemetry import archive_dir  # noqa: E402

MAX_SLUG_SEGMENTS = 2


class SlugError(ValueError):
    """Raised when a slug argument is unsafe."""


def validate_slug(slug: str, root: Path) -> Path:
    """Validate a slug and return its path relative to ``root``.

    Rejects absolute slugs, ``..`` traversal, empty slugs, and slugs deeper
    than two segments. The resolved destination must stay under ``root``.
    """
    posix = PurePosixPath(slug)
    if (
        not slug
        or posix.is_absolute()
        or ".." in posix.parts
        or len(posix.parts) > MAX_SLUG_SEGMENTS
    ):
        raise SlugError(
            f"Invalid slug {slug!r}: must be relative, contain no '..', "
            f"and have at most {MAX_SLUG_SEGMENTS} segments"
        )
    candidate = (root / Path(*posix.parts)).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise SlugError(f"Slug {slug!r} escapes the archive root {root}")
    return Path(*posix.parts)


def collect_moves(src: Path, dest: Path, moves: list, collisions: list) -> None:
    """Plan directory moves from ``src`` into ``dest``.

    Appends (old, new) pairs to ``moves`` for subtrees that can move whole.
    A directory that directly contains files is a leaf (a run dir or task
    dir); if its destination already exists the pair goes to ``collisions``
    instead — run contents are never merged or overwritten.
    """
    if not dest.exists():
        moves.append((src, dest))
        return
    if dest.is_file():
        collisions.append((src, dest))
        return
    entries = list(src.iterdir())
    if any(e.is_file() for e in entries):
        collisions.append((src, dest))
        return
    for child in sorted(entries):
        collect_moves(child, dest / child.name, moves, collisions)


def plan_root(root: Path, old_rel: Path, new_rel: Path, label: str) -> tuple[list, list, bool]:
    """Collect moves/collisions for one archive root.

    Returns (moves, collisions, skipped) where ``skipped`` means the old slug
    dir is absent under this root (fine — reports may not exist).
    """
    src = root / old_rel
    if not src.exists():
        return [], [], True
    moves: list = []
    collisions: list = []
    collect_moves(src, root / new_rel, moves, collisions)
    return moves, collisions, False


def remove_empty_parents(path: Path, stop: Path) -> None:
    """Remove empty parent dirs of ``path`` up to (not including) ``stop``."""
    parent = path.parent
    while parent != stop and parent.is_dir() and not any(parent.iterdir()):
        parent.rmdir()
        parent = parent.parent


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rename telemetry/report project dirs from OLD_SLUG to NEW_SLUG."
    )
    parser.add_argument("old_slug", help="existing project slug, e.g. thebrightnest/ae-toolkit")
    parser.add_argument("new_slug", help="new project slug, e.g. aiskills/main")
    parser.add_argument("--apply", action="store_true", help="perform the renames (default: dry-run)")
    parser.add_argument("--archive", type=Path, help="telemetry archive root (default: env or ~/.aet/telemetry)")
    parser.add_argument("--reports", type=Path, help="reports archive root (default: env or ~/.aet/reports)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    roots = [
        ("telemetry", args.archive.expanduser() if args.archive else archive_dir()),
        ("reports", args.reports.expanduser() if args.reports else reports_dir()),
    ]

    try:
        per_root = [
            (label, root, validate_slug(args.old_slug, root), validate_slug(args.new_slug, root))
            for label, root in roots
        ]
    except SlugError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    all_moves: list = []
    all_collisions: list = []
    for label, root, old_rel, new_rel in per_root:
        moves, collisions, skipped = plan_root(root, old_rel, new_rel, label)
        if skipped:
            print(f"[{label}] {root / old_rel} absent — skipping")
        all_moves.extend(moves)
        all_collisions.extend((label, src, dest) for src, dest in collisions)

    if all_collisions:
        for label, src, dest in all_collisions:
            print(f"[{label}] REFUSED: destination already exists: {src} → {dest}", file=sys.stderr)
        print("No changes applied.", file=sys.stderr)
        return 1

    if not all_moves:
        print("Nothing to do.")
        return 0

    for src, dest in all_moves:
        print(f"{src} → {dest}")

    if not args.apply:
        print(f"\nDry run: {len(all_moves)} move(s) pending. Re-run with --apply to execute.")
        return 0

    for src, dest in all_moves:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))

    # Clean up empty old parent dirs (e.g. the first slug segment).
    for label, root, old_rel, _new_rel in per_root:
        remove_empty_parents(root / old_rel, root)

    print(f"Applied {len(all_moves)} move(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
