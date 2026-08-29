"""Triage prompt builder and structured-verdict parser for --on-failure=triage.

Pure, testable helpers. The orchestrator owns session spawning and the state
transition; this module only describes the request and interprets the response.
"""

from __future__ import annotations

import json
import re

TRIAGE_ACTIONS = frozenset({"requeue", "quarantine"})


def has_sufficient_evidence(
    tail: str | None = None,
    signature: str | None = None,
) -> bool:
    """Return True when *tail* or *signature* carries enough evidence to triage.

    A triage decision requires at least one non-empty evidence signal: either a
    non-empty failure tail or a failure signature. When neither is present,
    spawning a triage session is skipped and the caller falls back to the
    deterministic classifier default.
    """
    return bool((tail and tail.strip()) or (signature and signature.strip()))


def build_triage_prompt(
    *,
    task_id: str,
    stage: str,
    failure_class: str,
    tail: str,
    signature: str,
) -> str:
    """Return a prompt that asks a triage session for a structured verdict.

    The verdict must be a single JSON object with an ``action`` field set to
    either ``requeue`` (transient failure, retry the task) or ``quarantine``
    (design/code defect, needs human review).
    """
    return (
        "You are a failure-triage agent for an unattended batch runner.\n"
        "A task failed; decide whether to requeue it for retry or quarantine "
        "it for human review.\n\n"
        f"Task: {task_id}\n"
        f"Stage: {stage}\n"
        f"Failure class: {failure_class}\n"
        f"Signature: {signature}\n\n"
        "Failure tail:\n"
        "---\n"
        f"{tail}\n"
        "---\n\n"
        "Respond with exactly one line of JSON:\n"
        '{"class": "<failure_class>", "action": "requeue"|"quarantine"}\n'
    )


def parse_triage_verdict(output: str) -> dict | None:
    """Parse a structured triage verdict from *output*.

    Looks for a JSON object containing an ``action`` key. Accepts the object
    inside a Markdown code block and tolerates surrounding chatter by using
    the last JSON object in the output.

    Returns ``{"action": "requeue"|"quarantine"}`` on success, or ``None``
    when the output is unparseable or the action is not one of the allowed
    values. ``None`` signals that the orchestrator should fall back to the
    deterministic classifier default (fail-closed).
    """
    if not output:
        return None

    # Strip Markdown code fences if present.
    cleaned = re.sub(r"^```(?:json)?\s*", "", output, flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```\s*$", "", cleaned, flags=re.MULTILINE)

    # Try each JSON-ish object in reverse order (last verdict wins).
    for match in reversed(list(re.finditer(r"\{[^{}]*\}", cleaned, re.DOTALL))):
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            action = payload.get("action")
            if action in TRIAGE_ACTIONS:
                return {"action": action}

    return None
