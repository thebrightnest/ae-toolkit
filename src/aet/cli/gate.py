"""aet-work gate — fail-closed verdict writer for the checking skills.

``gate submit`` is the sole sanctioned writer of gate evidence verdicts
(G1). It schema-validates the payload against the stage schema, resolves
the destination through the canonical ``resolve_verdict_path`` precedence
(ADR-023), and delegates the write to ``evidence.write_verdict``. Every
failure path prints a named error to stderr and exits 1 — never a silent
or partial write.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
from aet import evidence  # noqa: E402


class _GateParser(argparse.ArgumentParser):
    """ArgumentParser that fails closed: named error on stderr, exit 1.

    Argument errors are fail-closed exit-1 conditions like every other
    ``gate submit`` failure (R-2), not argparse's default exit 2.
    """

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        print(f"error: {message}", file=sys.stderr)
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = _GateParser(
        prog="gate",
        description="Fail-closed gate verdict writer.",
    )
    sub = parser.add_subparsers(
        dest="command", required=True, parser_class=_GateParser
    )
    submit = sub.add_parser(
        "submit",
        help="Validate and write a stage verdict",
        description="Validate a verdict payload against its stage schema "
        "and write it to the canonical verdict path.",
    )
    submit.add_argument(
        "--stage",
        required=True,
        help="Verdict stage: qa, review, cso, or sync-docs",
    )
    submit.add_argument(
        "--verdict",
        required=True,
        choices=["pass", "fail"],
        help="Declared verdict; must match the payload's verdict field",
    )
    submit.add_argument(
        "--evidence",
        required=True,
        help="Path to the verdict JSON payload file",
    )
    return parser


def _fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def _submit(args: argparse.Namespace) -> int:
    stage = args.stage
    if stage not in evidence.SCHEMAS:
        known = ", ".join(sorted(evidence.SCHEMAS))
        return _fail(f"unknown stage {stage!r} (expected one of: {known})")

    evidence_file = Path(args.evidence)
    try:
        raw = evidence_file.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _fail(f"evidence file not found: {evidence_file}")
    except OSError as exc:
        return _fail(f"cannot read evidence file {evidence_file}: {exc}")

    try:
        record = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _fail(f"evidence file is not valid JSON ({evidence_file}): {exc}")

    if not isinstance(record, dict):
        return _fail(f"evidence payload must be a JSON object ({evidence_file})")

    # Stamp tree_hash before validating so the skill writer contract (which
    # does not require tree_hash) stays unchanged — ADR-025.
    if "tree_hash" not in record:
        root = evidence.telemetry.resolve_repo_root()
        record = {**record, "tree_hash": evidence.verifier.working_tree_hash(str(root))}

    try:
        evidence.validate_verdict(record, stage)
    except (evidence.VerdictValidationError, evidence.VerdictValueError) as exc:
        return _fail(f"invalid {stage!r} verdict payload: {exc}")

    if record["verdict"] != args.verdict:
        return _fail(
            f"--verdict {args.verdict!r} does not match payload verdict "
            f"{record['verdict']!r}"
        )

    task_id = os.environ.get("AET_TASK_ID") or record["task_id"]
    try:
        dest = evidence.resolve_verdict_path(task_id=task_id, kind=stage)
        written = evidence.write_verdict(task_id, stage, record, path=dest)
    except OSError as exc:
        return _fail(f"cannot write verdict: {exc}")

    print(f"✓ {stage} verdict written: {written}")
    return 0


def main(argv: list[str] | None = None):
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1
    if args.command == "submit":
        return _submit(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
