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
from dataclasses import dataclass
from pathlib import Path

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
        # Fall back to the canonical layout ``docs/plans/<plan>.md``.
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

_PRD_REF_RE = re.compile(r"\b(docs/prds/[\w./\-]+\.md)\b")
_RID_RE = re.compile(r"\bR-\d+\b")
_TASK_TRACE_RE = re.compile(r"\(\s*traces:\s*([^)]+)\)")


def _prd_path_for_plan(plan: Path, repo_root: Path | None = None) -> Path | None:
    """Resolve the PRD file referenced from a plan's context."""
    text = plan.read_text(errors="ignore")
    match = _PRD_REF_RE.search(text)
    if not match:
        return None
    root = repo_root if repo_root is not None else _repo_root_for(plan)
    return root / match.group(1)


def _requirements_rids(prd: Path) -> set[str]:
    """Collect R-ids declared under the PRD's Requirements section."""
    text = prd.read_text(errors="ignore")
    section = _section_body(text, "Requirements") or text
    return set(_RID_RE.findall(section))


def _task_trace_rids(plan: Path) -> set[str]:
    """Collect R-ids cited in the plan's task list."""
    text = plan.read_text(errors="ignore")
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
        all_plans = sorted(
            p for p in corpus.glob("*.md") if not plan_parser.is_settled_plan(p)
        )
    else:
        all_plans = live_plans
    findings.extend(
        structural_findings(all_plans, limit_to=limit_to, extra_known_ids=extra_known_ids)
    )

    # R-trace coverage is a whole-plan-set property: one PRD decomposes into
    # many atomic plans, so a requirement is covered when any live sibling
    # traces it. Build the union from the live plan set, then report per plan.
    coverage = _prd_coverage(all_plans, repo_root)

    for plan in live_plans:
        findings.extend(rtrace_findings(plan, repo_root=repo_root, coverage=coverage))
        findings.extend(acceptance_findings(plan))
        if repo_root:
            findings.extend(scope_findings(plan, repo_root))

    return findings
