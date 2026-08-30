"""Plan-quality validation suite for ``aet plan validate``.

The suite composes four check families on top of the existing structural
intake validator:

- structural — delegated to ``plan_parser.intake_validation_errors``
- rtrace — PRD requirement coverage in the task list
- acceptance — validation strategy names tests for every new source file
  and acceptance criteria do not restate tasks
- scope — ADR and domain-term references resolve

Each failing check can be overridden by an explicit inline marker:

    ⚠️ VALIDATE ACK: <check-id> — <reason>

A reason-less ack is ignored (fail-safe), mirroring the
``⚠️ ATOMIC OVERSIZED`` convention.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aet import plan_parser


@dataclass(frozen=True)
class Finding:
    """One validation failure for a single plan file."""

    check_id: str
    plan: Path
    message: str
    acked: bool = False
    ack_reason: str = ""


# ---------------------------------------------------------------------------
# Ack escape hatch
# ---------------------------------------------------------------------------

_ACK_RE = re.compile(
    r"^⚠️[^\S\n]*VALIDATE[^\S\n]+ACK:[^\S\n]*([\w\-]+)[^\S\n]*[\u2014-][^\S\n]*(.+)$",
    re.MULTILINE,
)


def find_acks(text: str) -> dict[str, str]:
    """Return a mapping ``check_id -> reason`` for explicit ack markers.

    A marker without a non-empty reason is not an override; the regex's
    ``.+`` requirement naturally enforces that.
    """
    return {check_id: reason.strip() for check_id, reason in _ACK_RE.findall(text)}


def apply_acks(findings: list[Finding], plan_texts: dict[Path, str]) -> list[Finding]:
    """Mark findings as ``acked`` when the plan carries a matching ack marker."""
    out: list[Finding] = []
    for finding in findings:
        acks = find_acks(plan_texts.get(finding.plan, ""))
        reason = acks.get(finding.check_id)
        if reason:
            out.append(
                Finding(
                    finding.check_id,
                    finding.plan,
                    finding.message,
                    acked=True,
                    ack_reason=reason,
                )
            )
        else:
            out.append(finding)
    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _section_body(text: str, heading: str) -> str | None:
    """Return the body under a ``## Heading`` if present."""
    pattern = (
        r"(?m)^##\s+"
        + re.escape(heading)
        + r"\s*\n(.*?)"
        + r"(?=\n## |\n---|\Z)"
    )
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1) if match else None


def _list_items(section: str) -> list[str]:
    """Return list-item text stripped of bullets/numbers/checkboxes."""
    items: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not re.match(r"^[\-\*\d]+\.?\s+", stripped):
            continue
        item = re.sub(r"^[\-\*\d]+\.?\s+", "", stripped)
        # Strip leading checkbox markers.
        item = re.sub(r"^\[\s*[xX ]\s*\]\s*", "", item)
        if item:
            items.append(item)
    return items


def _repo_root_for(plan: Path) -> Path:
    """Best-effort repository root for resolving relative references."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=plan.parent,
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        # Fall back to the canonical layout ``docs/plans/active/<plan>.md`` or ``docs/plans/<plan>.md``.
        if plan.parent.name in ("active", "archive") and plan.parent.parent.name == "plans" and plan.parent.parent.parent.name == "docs":
            return plan.parent.parent.parent.parent
        if plan.parent.name == "plans" and plan.parent.parent.name == "docs":
            return plan.parent.parent.parent
        return plan.parent.parent


# ---------------------------------------------------------------------------
# (a) Structural
# ---------------------------------------------------------------------------


def structural_findings(
    plan_files: list[Path],
    limit_to: set[Path] | None = None,
    extra_known_ids: set[str] | None = None,
) -> list[Finding]:
    """Delegate structural intake validation to ``plan_parser``."""
    errors = plan_parser.intake_validation_errors(
        plan_files, limit_to=limit_to, extra_known_ids=extra_known_ids
    )
    return [Finding("structural", path, message) for path, message in errors]


# ---------------------------------------------------------------------------
# (b) R-trace coverage
# ---------------------------------------------------------------------------

# Reading the task store is an optimization on top of the authoring corpus:
# these are the failures that mean "no store here", not "validation is
# broken". Anything else propagates.
_STORE_ERRORS = (OSError, RuntimeError, ValueError, subprocess.SubprocessError)

_RID_RE = re.compile(r"\bR-\d+\b")
_TASK_TRACE_RE = re.compile(r"\(\s*traces:\s*([^)]+)\)")


def _prd_path_for_plan(plan: Path, repo_root: Path | None = None) -> Path | None:
    """Resolve the PRD file referenced from a plan's context."""
    root = repo_root if repo_root is not None else _repo_root_for(plan)
    return plan_parser.prd_path_for_plan(plan, repo_root=root)


def _requirements_rids(prd: Path) -> set[str]:
    """Collect R-ids declared under the PRD's Requirements section."""
    text = prd.read_text(errors="ignore")
    section = _section_body(text, "Requirements") or text
    return set(_RID_RE.findall(section))


def _task_trace_rids(plan: Path) -> set[str]:
    """Collect R-ids cited in the plan file's task list."""
    return _trace_rids_in(plan.read_text(errors="ignore"))


def _trace_rids_in(text: str) -> set[str]:
    """Collect R-ids cited by ``(traces: ...)`` in a task list."""
    section = _section_body(text, "Task List") or text
    rids: set[str] = set()
    for match in _TASK_TRACE_RE.finditer(section):
        rids.update(_RID_RE.findall(match.group(1)))
    return rids


def _prd_coverage(
    all_plans: list[Path], repo_root: Path | None
) -> dict[Path, set[str]]:
    """Union of task-traced R-ids per referenced PRD across the plan set.

    AET decomposes one PRD into many atomic plans, so requirement coverage is
    a property of the whole set, not of any single plan: this maps each PRD to
    every R-id traced by any plan referencing it, letting ``rtrace_findings``
    credit a requirement covered by a sibling plan.
    """
    coverage: dict[Path, set[str]] = {}
    for plan in all_plans:
        prd = _prd_path_for_plan(plan, repo_root)
        if prd is None:
            continue
        coverage.setdefault(prd, set()).update(_task_trace_rids(plan))
    return coverage


@dataclass(frozen=True)
class RecordCoverage:
    """Per-PRD coverage recovered from task records, and what could not be.

    ``unreadable`` names the records that carry no spec to read, and
    ``source_error`` the reason the record store could not be read at all.
    Both are reported rather than skipped: a record contributing nothing is
    indistinguishable from a plan that traced nothing, and the difference
    decides whether an uncovered requirement is real (ADR-059).
    """

    coverage: dict[Path, set[str]]
    unreadable: tuple[str, ...]
    source_error: str = ""


def record_coverage(
    records: Iterable[dict[str, Any]], repo_root: Path | None
) -> RecordCoverage:
    """Union of task-traced R-ids per PRD, read from task records.

    A plan file is an authoring artifact; after intake the record carries the
    spec (ADR-061). Coverage is the one r-trace property that outlives
    authoring — the siblings that already delivered a PRD's requirements have
    left ``docs/plans/`` — so it is read from the record, while the structural
    checks stay on the authoring corpus.

    Each record contributes the R-ids its ``spec.tasks`` cites to the PRD its
    ``spec.body`` references. A record with neither is named in ``unreadable``.
    """
    coverage: dict[Path, set[str]] = {}
    unreadable: list[str] = []
    for record in records:
        task_id = str(record.get("id") or "<unidentified>")
        spec = record.get("spec")
        if not isinstance(spec, dict):
            unreadable.append(task_id)
            continue
        body = spec.get("body") or ""
        tasks = spec.get("tasks") or ""
        if isinstance(tasks, list):
            tasks = "\n".join(str(item) for item in tasks)
        if not body and not tasks:
            unreadable.append(task_id)
            continue
        prd = plan_parser.prd_path_from_text(body, repo_root=repo_root)
        if prd is None:
            unreadable.append(task_id)
            continue
        coverage.setdefault(prd, set()).update(_trace_rids_in(tasks or body))
    return RecordCoverage(coverage, tuple(sorted(unreadable)))


def coverage_from_backend(backend: Any, repo_root: Path | None) -> RecordCoverage:
    """Read r-trace coverage from a task backend's live and settled records.

    Sealed tombstones (``refs/aet/sealed/<id>``) are the complete, pushed
    source: they are written in every posture, unlike the history JSONL, which
    shadow posture does not write. They are a git-refs capability rather than
    part of the backend interface, so a backend without them contributes what
    its history log holds and says the source was partial.

    A store that cannot be read yields empty coverage and a named reason rather
    than raising — validation must still run without a reachable store, it just
    credits fewer siblings, and the caller says so instead of reporting the
    shortfall as the plan's fault.
    """
    records: list[dict[str, Any]] = []
    settled_ids = getattr(backend, "settled_ids", None)
    read_sealed = getattr(backend, "read_sealed", None)
    partial = ""
    try:
        data = backend.load()
        records.extend(data.get("queue", []))
        if callable(settled_ids) and callable(read_sealed):
            for task_id in sorted(settled_ids()):
                record = read_sealed(task_id)
                if record is not None:
                    records.append(record)
        else:
            records.extend(data.get("history", []))
            partial = (
                f"{type(backend).__name__} exposes no sealed tombstones; "
                "settled coverage comes from the history log only"
            )
    except _STORE_ERRORS as exc:
        return RecordCoverage({}, (), f"{type(exc).__name__}: {exc}")
    result = record_coverage(records, repo_root)
    if partial:
        return RecordCoverage(result.coverage, result.unreadable, partial)
    return result


def corpus_dir(repo_root: Path | None) -> Path | None:
    """Return the plan-set directory backing whole-set coverage, or ``None``.

    R-trace coverage is a property of the whole plan set (see
    ``_prd_coverage``). It is only available when the plan directory can be
    located; without it every plan is judged against its own traces alone,
    which reports fewer uncovered requirements than the plan set does. Callers
    that print results use this to name which of the two modes ran.
    """
    if repo_root is None:
        return None
    plans_dir = repo_root / "docs" / "plans"
    return plans_dir if plans_dir.is_dir() else None


def rtrace_findings(
    plan: Path,
    repo_root: Path | None = None,
    coverage: dict[Path, set[str]] | None = None,
) -> list[Finding]:
    """Check R-id coverage across the plan set and per-plan citation validity.

    Coverage — every PRD requirement traced by some task — is a whole-set
    property: a requirement is covered when *any* plan sharing the PRD traces
    it. ``coverage`` carries that plan-set union (see ``_prd_coverage``);
    without it a plan is judged against its own traces alone. Citation
    validity — no task cites an R-id absent from the PRD — stays per-plan.
    """
    prd = _prd_path_for_plan(plan, repo_root)
    if prd is None:
        return [Finding("rtrace", plan, "no PRD reference found in plan context")]
    if not prd.exists():
        return [Finding("rtrace", plan, f"PRD not found: {prd}")]

    required = _requirements_rids(prd)
    task_rids = _task_trace_rids(plan)

    covered = set(task_rids)
    if coverage is not None:
        covered |= coverage.get(prd, set())

    findings: list[Finding] = []
    for rid in sorted(required - covered):
        findings.append(
            Finding("rtrace", plan, f"requirement {rid} has no covering task")
        )
    for rid in sorted(task_rids - required):
        findings.append(Finding("rtrace", plan, f"task cites unknown requirement {rid}"))

    return findings


# ---------------------------------------------------------------------------
# (c) Acceptance-as-evidence
# ---------------------------------------------------------------------------

_NEW_FILE_RE = re.compile(r"`?([^`]+)`?\s*\(new\)")

# A named test *file* — ``test_x.py``, ``x_test.go``, ``x.test.ts``,
# ``x.spec.js`` — so the strategy is credited when it names a test for the
# behavior rather than echoing the source filename.
_TEST_FILE_RE = re.compile(
    r"\b(?:test[_-][\w-]+|[\w-]+[_-]test|[\w-]+\.(?:test|spec))\.\w+\b",
    re.IGNORECASE,
)


def _is_testable_source(ref: str) -> bool:
    """Whether a new ``Files to Modify`` deliverable is source a validation
    strategy should name a test for.

    Documentation write-ups (audit docs, ADRs, templates — anything under
    ``docs/`` or ending in ``.md``) and directory entries are deliverables
    but not testable source files, so they carry no named test.
    """
    ref = ref.strip()
    if ref.endswith("/"):
        return False
    if ref.lower().endswith(".md"):
        return False
    return "docs" not in Path(ref).parts


def acceptance_findings(plan: Path) -> list[Finding]:
    """Check acceptance criteria and named-test coverage for new files."""
    text = plan.read_text(errors="ignore")

    task_section = _section_body(text, "Task List") or ""
    task_texts = [
        re.sub(r"\s*\(\s*traces:[^)]*\)", "", item).strip()
        for item in _list_items(task_section)
    ]

    ac_items: list[str] = []
    for heading in ("Acceptance Criteria", "Validation Steps"):
        section = _section_body(text, heading)
        if section:
            ac_items.extend(_list_items(section))

    findings: list[Finding] = []

    for ac in ac_items:
        ac_clean = re.sub(r"^\[\s*[xX ]\s*\]\s*", "", ac).strip()
        for task_text in task_texts:
            if len(task_text) >= 5 and task_text in ac_clean:
                findings.append(
                    Finding(
                        "acceptance",
                        plan,
                        f"acceptance criterion restates task: {task_text[:60]}",
                    )
                )
                break

    files_section = _section_body(text, "Files to Modify") or ""
    new_files: list[str] = []
    for item in _list_items(files_section):
        match = _NEW_FILE_RE.search(item)
        if match and _is_testable_source(match.group(1)):
            new_files.append(Path(match.group(1).strip()).name)

    val_names = [
        re.sub(r"^\[\s*[xX ]\s*\]\s*", "", it).strip("`- ")
        for it in ac_items
    ]

    # A validation strategy that names a test file (e.g. a "New source
    # coverage" block citing tests/test_*.py) evidences test coverage even
    # when the test is named for the behavior, not the source file. Only a
    # strategy naming no test at all leaves a new source file uncovered.
    names_test_file = any(_TEST_FILE_RE.search(it) for it in ac_items)

    for new_file in new_files:
        stem = Path(new_file).stem
        named_for_file = any(stem in name or new_file in name for name in val_names)
        if not named_for_file and not names_test_file:
            findings.append(
                Finding(
                    "acceptance",
                    plan,
                    f"new source file {new_file} has no named test in validation strategy",
                )
            )

    return findings


# ---------------------------------------------------------------------------
# (d) Scope-reference resolution
# ---------------------------------------------------------------------------

_ADR_REF_RE = re.compile(r"\b(docs/adr/[\w./\-]+\.md)\b")


def scope_findings(plan: Path, repo_root: Path) -> list[Finding]:
    """Check that ADR references resolve to existing files."""
    text = plan.read_text(errors="ignore")
    findings: list[Finding] = []
    for match in _ADR_REF_RE.finditer(text):
        ref = match.group(1)
        if not (repo_root / ref).exists():
            findings.append(Finding("scope", plan, f"ADR reference does not resolve: {ref}"))
    return findings


# ---------------------------------------------------------------------------
# (e) Status lifecycle
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Top-level validate
# ---------------------------------------------------------------------------


def validate(
    plans: list[Path],
    repo_root: Path | None = None,
    extra_known_ids: set[str] | None = None,
    extra_coverage: dict[Path, set[str]] | None = None,
) -> list[Finding]:
    """Run the full check suite over the requested live plan files.

    Settled plans (terminal ``status`` frontmatter or terminal footer stage)
    are ignored so validation does not degrade as finished work accumulates.

    ``plans`` is the set the user asked to validate, filtered to live work.
    Structural checks still parse every live plan in the directory (when a
    directory context is available) so that blocker references and duplicate-id
    detection remain accurate, but only report errors for files in ``plans``.

    ``extra_known_ids`` allows callers to include settled history ids as valid
    blocker references.

    ``extra_coverage`` is r-trace coverage from outside the authoring corpus,
    built by :func:`record_coverage` from task records. Without it a plan whose
    siblings have all settled is judged as though nothing had been delivered
    for its PRD. Callers that can reach the task store build it and pass it in;
    ``plan_validate`` itself stays free of a backend dependency.
    """
    if repo_root is None and plans:
        repo_root = _repo_root_for(plans[0])

    live_plans = [p for p in plans if not plan_parser.is_settled_plan(p)]
    limit_to = set(live_plans)
    findings: list[Finding] = []

    # Structural checks parse every live plan in the directory so that blocker
    # references and duplicate-id detection remain accurate.
    corpus = corpus_dir(repo_root)
    if corpus is not None:
        active_dir = corpus / "active"
        active_plans = (
            [p for p in active_dir.glob("*.md") if not plan_parser.is_settled_plan(p)]
            if active_dir.is_dir()
            else []
        )
        root_plans = [p for p in corpus.glob("*.md") if not plan_parser.is_settled_plan(p)]
        all_plans = sorted(set(active_plans + root_plans))
    else:
        all_plans = live_plans
    findings.extend(
        structural_findings(all_plans, limit_to=limit_to, extra_known_ids=extra_known_ids)
    )

    # R-trace coverage is a whole-plan-set property that outlives authoring:
    # one PRD decomposes into many atomic plans, and a requirement stays
    # covered once a sibling has delivered it. The authoring corpus holds only
    # the plans still on disk, so the record supplies the rest (ADR-061).
    coverage = _prd_coverage(all_plans, repo_root)
    for prd, rids in (extra_coverage or {}).items():
        coverage.setdefault(prd, set()).update(rids)

    for plan in live_plans:
        findings.extend(rtrace_findings(plan, repo_root=repo_root, coverage=coverage))
        findings.extend(acceptance_findings(plan))
        if repo_root:
            findings.extend(scope_findings(plan, repo_root))

    return findings
