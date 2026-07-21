"""Declarative documentation governance rule engine for ``aet docs lint``.

Rules are data, parsed with ``yaml.safe_load``, and evaluated against the
checkout. The evaluator never executes rule content.
"""

from __future__ import annotations

from pathlib import Path

import yaml

VALID_RULE_TYPES = frozenset({"must_contain", "must_not_contain", "path_exists", "path_absent"})


class DocsLintError(Exception):
    """Raised for unrecoverable rule-file errors."""


class RuleError(DocsLintError):
    """Raised when a single rule is malformed."""

    def __init__(self, index: int, message: str) -> None:
        self.index = index
        super().__init__(f"rule {index}: {message}")


def _relative(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return path


def _load_rules(rules_file: Path) -> list[dict]:
    """Load and return the raw rule list from *rules_file*."""
    if not rules_file.exists():
        raise DocsLintError(f"rules file not found: {rules_file}")
    try:
        data = yaml.safe_load(rules_file.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise DocsLintError(f"invalid YAML: {exc}") from exc
    if data is None:
        return []
    if not isinstance(data, dict):
        raise DocsLintError("top-level must be a mapping")
    rules = data.get("rules")
    if rules is None:
        return []
    if not isinstance(rules, list):
        raise DocsLintError("'rules' must be a list")
    return rules


def _normalize_values(value: object) -> list[str]:
    """Return *value* as a list of strings."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise DocsLintError("'value' must be a string or list of strings")


def _extract_section(text: str, section: str) -> str | None:
    """Return the body under the first ATX heading matching *section*.

    The body runs from the line after the heading until the next heading of
    equal or higher level (fewer ``#`` characters).
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped.startswith("#"):
            continue
        hashes = stripped.split()[0]
        if not hashes or not all(ch == "#" for ch in hashes):
            continue
        level = len(hashes)
        title = stripped[level:].strip()
        if title == section:
            body_lines: list[str] = []
            for j in range(i + 1, len(lines)):
                next_line = lines[j]
                next_stripped = next_line.lstrip()
                if next_stripped.startswith("#"):
                    next_hashes = next_stripped.split()[0]
                    if next_hashes and all(ch == "#" for ch in next_hashes):
                        next_level = len(next_hashes)
                        if next_level <= level:
                            break
                body_lines.append(next_line)
            return "\n".join(body_lines)
    return None


def _validate_rule(raw: object, index: int) -> dict:
    """Validate and normalize a single rule mapping."""
    if not isinstance(raw, dict):
        raise RuleError(index, "must be a mapping")
    rule = dict(raw)
    missing = [k for k in ("type", "target", "reason") if k not in rule]
    if missing:
        raise RuleError(index, f"missing required fields: {', '.join(missing)}")
    rtype = rule["type"]
    if rtype not in VALID_RULE_TYPES:
        raise RuleError(index, f"unknown type '{rtype}'")
    if rtype in ("must_contain", "must_not_contain"):
        if "value" not in rule:
            raise RuleError(index, f"'value' is required for {rtype}")
        rule["value"] = _normalize_values(rule["value"])
    return rule


def lint_docs(rules_file: Path, repo_root: Path) -> list[tuple[Path, str]]:
    """Evaluate the documentation rules file against the checkout.

    Returns a list of ``(relative_path, message)`` violations. An empty list
    means every rule passed.
    """
    rel_rules = _relative(rules_file, repo_root)
    try:
        raw_rules = _load_rules(rules_file)
    except DocsLintError as exc:
        return [(rel_rules, f"cannot load rules: {exc}")]

    rules: list[tuple[int, dict]] = []
    for idx, raw in enumerate(raw_rules, start=1):
        try:
            rule = _validate_rule(raw, idx)
        except DocsLintError as exc:
            return [(rel_rules, str(exc))]
        rules.append((idx, rule))

    violations: list[tuple[Path, str]] = []
    for _idx, rule in rules:
        target = Path(rule["target"])
        if target.is_absolute():
            target_path = target
            rel_target = _relative(target_path, repo_root)
        else:
            target_path = repo_root / target
            rel_target = target

        rtype = rule["type"]
        reason = rule["reason"]

        if rtype in ("path_exists", "path_absent"):
            exists = target_path.exists()
            if rtype == "path_exists" and not exists:
                violations.append((rel_target, f"{reason} (expected path to exist: {target})"))
            elif rtype == "path_absent" and exists:
                violations.append((rel_target, f"{reason} (expected path to be absent: {target})"))
            continue

        if not target_path.exists():
            violations.append((rel_target, f"{reason} (target file missing: {target})"))
            continue
        try:
            text = target_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            violations.append((rel_target, f"{reason} (cannot read file: {exc})"))
            continue

        section = rule.get("section")
        haystack = text
        section_note = ""
        if section:
            section_body = _extract_section(text, section)
            if section_body is None:
                violations.append((rel_target, f"{reason} (section not found: {section})"))
                continue
            haystack = section_body
            section_note = f" in section '{section}'"

        values = rule["value"]
        if rtype == "must_contain":
            missing = [v for v in values if v not in haystack]
            if missing:
                detail = f"expected {missing!r}{section_note}"
                violations.append((rel_target, f"{reason} ({detail})"))
        elif rtype == "must_not_contain":
            present = [v for v in values if v in haystack]
            if present:
                detail = f"found forbidden substring{'' if len(present) == 1 else 's'} {present!r}{section_note}"
                violations.append((rel_target, f"{reason} ({detail})"))

    return violations
