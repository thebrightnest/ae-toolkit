"""Identity-conflation lens — dual identifiers for one entity must be declared.

When a diff adds two or more identifier-shaped symbols for the same entity
stem (e.g. ``projectPath`` and ``projectId``), the lens requires the plan to
carry an ``identity:`` entry that names both identifiers and designates which
one persists.  The check is fail-closed: an undeterminable diff yields an
indeterminate finding, and a missing or malformed declaration blocks the
review verdict.

Identifier shapes recognised by the default scan:
  * camelCase/PascalCase suffixes: ``*Id``, ``*ID``, ``*Uuid``, ``*UUID``,
    ``*Path``
  * snake_case suffixes: ``*_id``, ``*_uuid``
  * route / path parameter bindings: ``{fooId}``, ``:foo_id``, etc.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aet import change_scope, plan_parser, telemetry

# Suffix groups.  The camel/Pascal regex tries shorter suffixes first, but
# case prevents ``Id`` from matching ``ID`` and vice-versa.  A negative
# lookbehind for ``\\`` avoids treating the ``n`` of ``\\n`` (an escaped
# newline in a string literal) as the start of an identifier.
_WORD_RE = re.compile(r"(?<!\\)\b[A-Za-z_][A-Za-z0-9_]*\b")

# camelCase/PascalCase identifier suffixes, longest first to avoid ``UUID``
# being parsed as ``ID``.
_CAMEL_SUFFIXES = ("UUID", "Uuid", "ID", "Id", "Path")
_SNAKE_SUFFIXES = ("_id", "_uuid")

_KIND_MAP: dict[str, str] = {
    "Id": "id",
    "ID": "id",
    "Uuid": "uuid",
    "UUID": "uuid",
    "Path": "path",
    "id": "id",
    "uuid": "uuid",
}


@dataclass
class IdentityResult:
    """Outcome of an identity-conflation check."""

    tripped: bool
    reason: str
    findings: list[dict[str, Any]] = field(default_factory=list)
    indeterminate: bool = False
    declaration_valid: bool = True
    declaration_errors: list[str] = field(default_factory=list)


@dataclass
class _RawIdentifier:
    """A single identifier occurrence before normalization."""

    name: str
    stem: str
    kind: str


def _git(*args: str, cwd: str | Path | None = None) -> tuple[int, str, str]:
    """Run a git command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return (127, "", "git not found")
    return (result.returncode, result.stdout, result.stderr)


def _added_lines_from_diff(diff_text: str) -> list[str]:
    """Return added content lines from a unified diff.

    Lines beginning with ``+`` are additions, except for the ``+++`` file
    header produced by ``git diff``.
    """
    added: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])
    return added


def _diff_added_lines(
    paths: list[str],
    base_ref: str,
    cwd: str | Path,
) -> tuple[list[str] | None, str | None]:
    """Return added lines for ``paths`` since the merge base with ``base_ref``.

    Returns ``(lines, None)`` on success, or ``(None, error)`` when the diff
    cannot be determined.  The working-tree comparison includes both commits
    already on the current branch and uncommitted changes.
    """
    rc, out, err = _git("merge-base", "HEAD", base_ref, cwd=cwd)
    if rc != 0:
        return None, f"cannot find merge base with {base_ref}: {err.strip()}"
    base = out.strip()
    if not base:
        return None, f"empty merge base with {base_ref}"

    rc, out, err = _git("diff", base, "--", *paths, cwd=cwd)
    if rc != 0:
        return None, f"git diff failed: {err.strip()}"

    return _added_lines_from_diff(out), None


def _extract_identifiers(lines: list[str]) -> list[_RawIdentifier]:
    """Scan lines for identifier-shaped symbols."""
    found: list[_RawIdentifier] = []
    for line in lines:
        for match in _WORD_RE.finditer(line):
            word = match.group(0)
            for suffix in _CAMEL_SUFFIXES:
                if len(word) > len(suffix) and word.endswith(suffix):
                    stem = word[: -len(suffix)]
                    found.append(
                        _RawIdentifier(
                            name=word,
                            stem=stem.lower(),
                            kind=_KIND_MAP[suffix],
                        )
                    )
                    break
            else:
                for suffix in _SNAKE_SUFFIXES:
                    if len(word) > len(suffix) and word.endswith(suffix):
                        stem = word[: -len(suffix)]
                        found.append(
                            _RawIdentifier(
                                name=word,
                                stem=stem.lower(),
                                kind=_KIND_MAP[suffix[1:]],
                            )
                        )
                        break
    return found


def _conflated_entities(
    identifiers: list[_RawIdentifier],
) -> list[dict[str, Any]]:
    """Group identifiers by stem and return entities with >=2 distinct kinds.

    Two identifiers are considered distinct when their normalized kind differs
    (``id``, ``uuid``, ``path``).  Casing variants such as ``Id`` and ``ID``
    collapse to the same kind, so the lens fires on semantic conflation rather
    than spelling.
    """
    by_stem: dict[str, dict[str, _RawIdentifier]] = {}
    for ident in identifiers:
        by_stem.setdefault(ident.stem, {})[ident.kind] = ident

    entities: list[dict[str, Any]] = []
    for stem, kinds in sorted(by_stem.items()):
        if len(kinds) < 2:
            continue
        idents = list(kinds.values())
        entities.append(
            {
                "entity": stem,
                "identifiers": sorted({i.name for i in idents}),
                "kinds": sorted({i.kind for i in idents}),
            }
        )
    return entities


def _load_identity_declarations(
    plan_path: Path,
) -> tuple[list[dict[str, Any]] | None, str | None]:
    """Read the ``identity:`` block from a plan's YAML frontmatter.

    Returns ``(declarations, None)`` when the block is present and well-formed,
    ``(None, None)`` when it is absent, and ``(None, error)`` when it is
    malformed.
    """
    data = plan_parser.parse_frontmatter(plan_path)
    raw = data.get("identity")
    if raw is None:
        return None, None
    if not isinstance(raw, list):
        return None, "identity: must be a list"

    declarations: list[dict[str, Any]] = []
    for idx, entry in enumerate(raw):
        if not isinstance(entry, dict):
            return None, f"identity[{idx}] must be a mapping"
        entity = entry.get("entity")
        if not isinstance(entity, str) or not entity.strip():
            return None, f"identity[{idx}].entity must be a non-empty string"
        idents = entry.get("identifiers")
        if (
            not isinstance(idents, list)
            or len(idents) < 2
            or not all(isinstance(i, str) for i in idents)
        ):
            return (
                None,
                f"identity[{idx}].identifiers must be a list of at least two strings",
            )
        persists = entry.get("persists")
        if not isinstance(persists, str) or not persists.strip():
            return None, f"identity[{idx}].persists must be a non-empty string"
        if persists not in idents:
            return (
                None,
                f"identity[{idx}].persists must be one of the listed identifiers",
            )
        declarations.append(
            {
                "entity": entity.strip().lower(),
                "identifiers": [str(i) for i in idents],
                "persists": str(persists),
            }
        )
    return declarations, None


def _validate_declarations(
    plan_path: Path,
    entities: list[dict[str, Any]],
) -> tuple[bool, list[str], list[dict[str, Any]]]:
    """Match conflated entities against the plan's ``identity:`` declarations.

    Returns ``(valid, errors, enriched_findings)``.  ``enriched_findings``
    copies each conflated entity and adds the declared ``persists`` value when
    a valid declaration exists for that stem.
    """
    declarations, parse_error = _load_identity_declarations(plan_path)
    if parse_error is not None:
        return False, [parse_error], [_enrich(e, None) for e in entities]
    if declarations is None:
        if not entities:
            return True, [], []
        return False, ["identity conflation detected but plan has no identity: block"], [
            _enrich(e, None) for e in entities
        ]

    decl_by_entity: dict[str, dict[str, Any]] = {
        d["entity"]: d for d in declarations
    }
    errors: list[str] = []
    enriched: list[dict[str, Any]] = []

    for entity in entities:
        stem = entity["entity"]
        decl = decl_by_entity.get(stem)
        if decl is None:
            errors.append(
                f"identity conflation detected for '{stem}' but no declaration exists"
            )
            enriched.append(_enrich(entity, None))
            continue

        conflated_names = {name.lower() for name in entity["identifiers"]}
        declared_names = {name.lower() for name in decl["identifiers"]}
        missing = conflated_names - declared_names
        if missing:
            errors.append(
                f"identity declaration for '{stem}' omits identifiers: "
                f"{', '.join(sorted(missing))}"
            )
        persists = decl["persists"]
        if persists.lower() not in conflated_names:
            errors.append(
                f"identity declaration for '{stem}' persists '{persists}' "
                f"which is not among the detected identifiers"
            )
        enriched.append(_enrich(entity, persists))

    return (not errors), errors, enriched


def _enrich(entity: dict[str, Any], persists: str | None) -> dict[str, Any]:
    """Copy a conflated entity dict and attach the persists designation."""
    return {**entity, "persists": persists}


def check(
    paths: list[str] | None,
    repo_root: Path | str | None = None,
    task_id: str | None = None,
    base_ref: str | None = None,
) -> IdentityResult:
    """Run the identity-conflation lens over the supplied changed paths.

    Args:
        paths: Changed paths, typically from ``change_scope.changed_paths()``.
            ``None`` or empty means the lens does not fire.
        repo_root: Repository root used to run git and locate the plan file.
            Defaults to the resolved repo root.
        task_id: Plan identifier used to locate ``docs/plans/<task_id>.md`` for
            declaration validation.  When omitted and the lens fires, the
            declaration is treated as missing.
        base_ref: Git ref to diff against.  Defaults to
            ``change_scope.BASE_REF``.

    Returns:
        An :class:`IdentityResult`.  ``tripped`` is ``True`` when the diff is
        indeterminate or when conflation is detected without a valid plan
        declaration.
    """
    if not paths:
        return IdentityResult(
            tripped=False,
            reason="no changed paths to analyze",
        )

    if base_ref is None:
        base_ref = change_scope.BASE_REF

    try:
        root = Path(repo_root) if repo_root is not None else telemetry.resolve_repo_root()
    except Exception as exc:
        return IdentityResult(
            tripped=True,
            reason=f"cannot resolve repo root: {exc}",
            indeterminate=True,
        )

    added_lines, error = _diff_added_lines(paths, base_ref, root)
    if added_lines is None:
        return IdentityResult(
            tripped=True,
            reason=f"cannot determine diff: {error}",
            indeterminate=True,
        )

    identifiers = _extract_identifiers(added_lines)
    entities = _conflated_entities(identifiers)

    if not entities:
        return IdentityResult(
            tripped=False,
            reason="no identity conflation detected",
        )

    plan_path = root / "docs" / "plans" / f"{task_id}.md" if task_id else None
    if plan_path is not None and not plan_path.exists():
        plan_path = None

    if plan_path is not None:
        valid, errors, findings = _validate_declarations(plan_path, entities)
    else:
        valid = False
        errors = ["identity conflation detected but plan declaration is missing"]
        findings = [_enrich(e, None) for e in entities]

    if not valid:
        return IdentityResult(
            tripped=True,
            reason="; ".join(errors),
            findings=findings,
            declaration_valid=False,
            declaration_errors=errors,
        )

    return IdentityResult(
        tripped=False,
        reason="identity conflation declared",
        findings=findings,
    )
