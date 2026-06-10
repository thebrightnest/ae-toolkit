#!/usr/bin/env python3
"""Assemble SKILL.md files from templates and shared partials.

Usage:
    python3 build-skills.py \
        --template path/to/template.md \
        --partials-dir path/to/partials/ \
        --output path/to/output.md \
        --skill-name my-skill \
        --next-step "aet-implement"

Placeholders in the template (e.g. {preamble}, {guardrails}) are replaced
with the contents of the corresponding file in the partials directory.
Builtin placeholders {skill_name} and {next_step} are also substituted.
"""

import argparse
import re
import sys
from pathlib import Path


def read_partial(partials_dir: Path, name: str) -> str:
    """Read a partial file, returning empty string if missing.

    Tries the exact name first, then a kebab-case variant
    (e.g. 'stage_table' → 'stage-table').
    """
    for candidate in (name, name.replace("_", "-")):
        path = partials_dir / f"{candidate}.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
    return ""


def substitute_placeholders(template: str, partials_dir: Path, extras: dict) -> str:
    """Replace {placeholder} with partial content or extra value."""

    def replacer(match: re.Match) -> str:
        key = match.group(1)
        if key in extras:
            return extras[key]
        partial = read_partial(partials_dir, key)
        if partial:
            return partial
        # Leave unknown placeholders intact so the caller can see them.
        return match.group(0)

    return re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", replacer, template)


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble skills from shared partials")
    parser.add_argument("--template", required=True, help="Path to skill template")
    parser.add_argument("--partials-dir", required=True, help="Directory containing .md partials")
    parser.add_argument("--output", required=True, help="Path to write assembled SKILL.md")
    parser.add_argument("--skill-name", required=True, help="Value for {skill_name} placeholder")
    parser.add_argument("--next-step", default="", help="Value for {next_step} placeholder")
    args = parser.parse_args()

    template_path = Path(args.template)
    partials_dir = Path(args.partials_dir)
    output_path = Path(args.output)

    if not template_path.exists():
        print(f"Error: template not found: {template_path}", file=sys.stderr)
        return 1

    if not partials_dir.exists():
        print(f"Error: partials directory not found: {partials_dir}", file=sys.stderr)
        return 1

    template = template_path.read_text(encoding="utf-8")
    extras = {
        "skill_name": args.skill_name,
        "next_step": args.next_step,
    }
    assembled = substitute_placeholders(template, partials_dir, extras)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(assembled, encoding="utf-8")
    print(f"✓ Assembled {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
