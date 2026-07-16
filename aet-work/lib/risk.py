"""Pure, deterministic risk scoring for the aet-work desk view.

The score is a weighted sum over signals already recorded by the pipeline.
Weights live in a module-level table so they can be tuned without changing
 the scoring contract.
"""

from __future__ import annotations

from typing import Any

WEIGHTS: dict[str, Any] = {
    "work_class": {
        "critical": 40,
        # Unknown risk needs eyes, not a free pass.
        "unclassified": 30,
        "normal": 20,
        "trivial": 10,
    },
    "size": {
        "L": 30,
        "M": 20,
        "S": 10,
        "": 0,
    },
    "review_findings": 5,
    "cso_findings": 5,
    "sync_docs_divergences": 5,
    "failed_verdict": 25,
    "missing_required_verdict": 20,
    "files_modified": 2,
    "tests_failed": 15,
}


def score(signals: dict[str, Any]) -> tuple[int, list[str]]:
    """Return a deterministic risk score and the factors that produced it.

    ``signals`` is a plain dict.  Unknown keys are ignored so callers may pass
    a superset of inputs.  The returned factors are short, human-readable
    strings that explain the score; they are also the raw material for the
    desk's risk table and JSON projection.
    """
    total = 0
    factors: list[str] = []

    work_class = signals.get("work_class") or "unclassified"
    wc_weight = WEIGHTS["work_class"].get(
        work_class, WEIGHTS["work_class"]["unclassified"]
    )
    total += wc_weight
    factors.append(f"work_class={work_class}")

    size = signals.get("size") or ""
    size_weight = WEIGHTS["size"].get(size, WEIGHTS["size"][""])
    total += size_weight
    factors.append(f"size={size}")

    for key in ("review_findings", "cso_findings", "sync_docs_divergences"):
        count = int(signals.get(key, 0) or 0)
        if count:
            total += count * WEIGHTS[key]
            factors.append(f"{key}={count}")

    failed = signals.get("failed_verdicts") or []
    if failed:
        total += WEIGHTS["failed_verdict"] * len(failed)
        for kind in failed:
            factors.append(f"failed:{kind}")

    missing = signals.get("missing_required_verdicts") or []
    if missing:
        total += WEIGHTS["missing_required_verdict"] * len(missing)
        for kind in missing:
            factors.append(f"missing:{kind}")

    files_modified = int(signals.get("files_modified", 0) or 0)
    if files_modified:
        total += files_modified * WEIGHTS["files_modified"]
        factors.append(f"files_modified={files_modified}")

    tests_failed = signals.get("tests_failed", 0) or 0
    if isinstance(tests_failed, bool):
        tests_failed = int(tests_failed)
    if tests_failed > 0:
        total += WEIGHTS["tests_failed"]
        factors.append("tests_failed>0")

    if not factors:
        factors.append("no signals")

    return total, factors
