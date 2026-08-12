"""Missing-verdict recovery and builder-mode stage prompts.

A checking stage that did its work but never wrote its verdict used to cost the
whole stage: the gate failed closed after the session had already run. The gate
still never softens — a missing verdict that stays missing fails exactly as
before — but "missing" now buys one narrow session that writes the file, while
`fail` and `invalid` (judgments, not omissions) are never retried.

The prompts assert the other half: agents are pointed at `aet gate submit`
builder mode, so no session has to reproduce schema fields it cannot see.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest

from aet import evidence, telemetry
from aet.workflow import ExecutionPolicy, Routing, Workflow, WorkflowStage

_ORCHESTRATOR_PY = Path(__file__).parents[2] / "src" / "aet" / "cli" / "orchestrator.py"
_spec = importlib.util.spec_from_loader(
    "orchestrator",
    importlib.machinery.SourceFileLoader("orchestrator", str(_ORCHESTRATOR_PY)),
)
orchestrator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(orchestrator)

TASK = "vrc-01"
SLUG = "demo/project"


class FakeAdapter:
    """Minimal adapter: records the prompt it was asked to build a command for."""

    name = "fake"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def build_cmd(self, prompt, workdir=None, headless=False):
        self.prompts.append(prompt)
        return ["fake-cli", "-p", prompt]


@pytest.fixture
def gate_env(tmp_path, monkeypatch):
    """Point the evidence archive and telemetry at a temp dir."""
    reports = tmp_path / "reports"
    monkeypatch.setenv("AET_REPORTS_DIR", str(reports))
    monkeypatch.setenv("AET_PROJECT_ID", SLUG)
    repo_root = tmp_path / "repo"
    (repo_root / ".agents").mkdir(parents=True)
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    logger = telemetry.RunLogger(str(repo_root), run_id="r-vrc")
    return {
        "repo_root": str(repo_root),
        "worktree": str(worktree),
        "logger": logger,
        "reports": reports,
    }


def _verdict_path() -> Path:
    return evidence.evidence_path(task_id=TASK, kind="qa", project_slug=SLUG)


def _write_qa_verdict(verdict: str = "pass", **overrides) -> Path:
    record = {
        "task_id": TASK,
        "stage": "qa-complete",
        "skill": "aet-qa",
        "verdict": verdict,
        "summary": "suite green",
        "generated_at": "2026-08-12T00:00:00Z",
        "tree_hash": "deadbeef",
        "test_command": "pytest -q",
        "tests_total": 12,
        "tests_passed": 12,
        "tests_failed": 0,
    }
    record.update(overrides)
    path = _verdict_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def _run_gate(env, adapter=None, **kwargs):
    """Call the gate, returning ``(passed, stdout)``."""
    buf = io.StringIO()
    call_kwargs = dict(kwargs)
    if adapter is not None:
        call_kwargs.update(adapter=adapter, worktree_dir=env["worktree"])
    with redirect_stdout(buf):
        passed = orchestrator._require_passing_verdict(
            TASK,
            "qa",
            env["repo_root"],
            "docs/plans/vrc-01.md",
            "qa-complete",
            env["logger"],
            **call_kwargs,
        )
    return passed, buf.getvalue()


def _spawn_stub(calls, *, writes_verdict: bool, exit_code: int = 0):
    """Stand in for the recovery session; optionally write the verdict it owed."""

    def _spawn(adapter, cmd, worktree_dir, env, stall_timeout=None):
        calls.append({"cmd": cmd, "env": env, "worktree": worktree_dir})
        if writes_verdict:
            _write_qa_verdict()
        return exit_code, None, None, ""

    return _spawn


# --- Recovery is attempted for omissions only ---


def test_missing_verdict_is_recovered_by_one_session(gate_env):
    calls: list[dict] = []
    with patch.object(
        orchestrator,
        "_spawn_session_with_tail",
        _spawn_stub(calls, writes_verdict=True),
    ):
        passed, out = _run_gate(gate_env, adapter=FakeAdapter())

    assert passed is True
    assert len(calls) == 1
    assert "verdict recovered" in out


def test_recovery_that_writes_nothing_still_fails_closed(gate_env):
    calls: list[dict] = []
    with patch.object(
        orchestrator,
        "_spawn_session_with_tail",
        _spawn_stub(calls, writes_verdict=False),
    ):
        passed, out = _run_gate(gate_env, adapter=FakeAdapter())

    assert passed is False
    assert len(calls) == 1, "recovery is attempted once, never in a loop"
    assert "Gate fail-closed" in out
    assert str(_verdict_path()) in out


def test_failing_verdict_is_never_recovered(gate_env):
    """A declared failure is a judgment; asking again would be asking to lie."""
    _write_qa_verdict(verdict="fail")
    calls: list[dict] = []
    with patch.object(
        orchestrator,
        "_spawn_session_with_tail",
        _spawn_stub(calls, writes_verdict=True),
    ):
        passed, out = _run_gate(gate_env, adapter=FakeAdapter())

    assert passed is False
    assert calls == []
    assert "verdict is 'fail'" in out


def test_invalid_verdict_is_never_recovered(gate_env):
    path = _verdict_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"task_id": TASK, "verdict": "pass"}), encoding="utf-8")
    calls: list[dict] = []
    with patch.object(
        orchestrator,
        "_spawn_session_with_tail",
        _spawn_stub(calls, writes_verdict=True),
    ):
        passed, out = _run_gate(gate_env, adapter=FakeAdapter())

    assert passed is False
    assert calls == []
    assert "invalid" in out


def test_without_an_adapter_the_gate_behaves_exactly_as_before(gate_env):
    calls: list[dict] = []
    with patch.object(
        orchestrator,
        "_spawn_session_with_tail",
        _spawn_stub(calls, writes_verdict=True),
    ):
        passed, out = _run_gate(gate_env)

    assert passed is False
    assert calls == []
    assert str(_verdict_path()) in out


# --- The recovery session is narrow, addressed, and attributable ---


def test_recovery_prompt_asks_only_for_the_verdict(gate_env):
    adapter = FakeAdapter()
    calls: list[dict] = []
    with patch.object(
        orchestrator,
        "_spawn_session_with_tail",
        _spawn_stub(calls, writes_verdict=True),
    ):
        _run_gate(gate_env, adapter=adapter)

    prompt = adapter.prompts[0]
    assert "aet gate submit --stage qa" in prompt
    assert "--from-pytest" in prompt
    assert "$AET_EVIDENCE_PATH" in prompt
    assert "Do not modify" in prompt
    assert "--verdict fail" in prompt, "recovery must not coerce a pass"
    assert "--evidence <payload-file>" not in prompt


def test_recovery_session_carries_task_and_evidence_path(gate_env):
    calls: list[dict] = []
    with patch.object(
        orchestrator,
        "_spawn_session_with_tail",
        _spawn_stub(calls, writes_verdict=True),
    ):
        _run_gate(gate_env, adapter=FakeAdapter())

    env = calls[0]["env"]
    assert env["AET_TASK_ID"] == TASK
    assert env["AET_EVIDENCE_PATH"] == str(_verdict_path())
    assert env["AET_EXECUTION_MODE"] == "unattended"


def test_recovery_is_visible_in_telemetry(gate_env):
    """Recovery cost is attributable, so a stage that always needs it is legible."""
    calls: list[dict] = []
    with patch.object(
        orchestrator,
        "_spawn_session_with_tail",
        _spawn_stub(calls, writes_verdict=True),
    ):
        _run_gate(gate_env, adapter=FakeAdapter())

    records = telemetry.read_jsonl(gate_env["logger"].task_log_path(TASK))
    stages = [r for r in records if r.get("type") == "stage"]
    assert len(stages) == 1
    assert stages[0]["stage"] == "qa-complete"


# --- Stage prompts route to builder mode (no hand-authored payloads) ---


def test_stage_prompt_uses_builder_mode(gate_env):
    prompt = orchestrator.build_prompt(
        ["aet-qa"], "docs/plans/vrc-01.md", "implemented", "qa-complete",
        verdict_kind="qa",
    )
    assert "aet gate submit --stage qa --verdict pass --from-pytest" in prompt
    assert "$AET_EVIDENCE_PATH" in prompt
    assert "--evidence <payload-file>" not in prompt
    for key in evidence.QA_REPORT_MINIMAL_KEYS:
        assert key in prompt


def _workflow() -> Workflow:
    stages = [
        WorkflowStage(
            name="implemented", skills=["aet-qa"], evidence="qa", gate_key=None
        ),
        WorkflowStage(
            name="qa-complete",
            skills=["aet-sync-docs"],
            evidence="sync-docs",
            gate_key=None,
        ),
    ]
    return Workflow(
        version=1,
        name="test",
        done_state="done",
        stages=stages,
        stage_map={s.name: s for s in stages},
        execution_policy=ExecutionPolicy(
            session_groups=[["implemented", "qa-complete"]]
        ),
        routing=Routing(default={"harness": "test", "model": None}, by_stage={}),
    )


def test_group_prompt_uses_builder_mode_per_kind(gate_env):
    workflow = _workflow()
    prompt = orchestrator.build_stage_group_prompt(
        "docs/plans/vrc-01.md", workflow.stages, workflow
    )
    assert "aet gate submit --stage qa --verdict pass --from-pytest" in prompt
    assert "aet gate submit --stage sync-docs --verdict pass" in prompt
    assert "--divergence" in prompt
    assert "$AET_EVIDENCE_PATH_QA" in prompt
    assert "$AET_EVIDENCE_PATH_SYNC_DOCS" in prompt
    assert "--evidence <payload-file>" not in prompt


def test_builder_command_is_single_sourced_from_evidence():
    """The prompt must not carry its own copy of the invocation."""
    assert evidence.submit_command("qa", "pass") in orchestrator.build_prompt(
        ["aet-qa"], "p.md", "implemented", "qa-complete", verdict_kind="qa"
    )
    with pytest.raises(evidence.VerdictValidationError):
        evidence.submit_command("not-a-kind")


def test_every_schema_kind_has_a_builder_invocation():
    """A new verdict kind cannot ship without a documented way to submit it."""
    assert set(evidence.BUILDER_FLAGS) == set(evidence.SCHEMAS)
    for kind in evidence.SCHEMAS:
        assert evidence.submit_command(kind).startswith(
            f"aet gate submit --stage {kind} "
        )


def test_qa_minimal_report_keys_match_the_schema(tmp_path):
    """The four keys the skills document must actually satisfy the qa builder."""
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "test_command": "pytest -q",
                "tests_total": 3,
                "tests_passed": 3,
                "tests_failed": 0,
            }
        ),
        encoding="utf-8",
    )
    from aet.cli import gate as gate_cli

    record = gate_cli._build_payload(
        stage="qa",
        verdict="pass",
        summary="green",
        from_pytest=report,
        divergences=[],
        task_id=TASK,
        test_command=None,
    )
    record["tree_hash"] = "deadbeef"
    evidence.validate_verdict(record, "qa")
    assert set(evidence.QA_REPORT_MINIMAL_KEYS) <= set(record)


def test_os_environ_is_untouched_by_recovery(gate_env):
    """The recovery session gets a copy; the orchestrator's own env is unchanged."""
    before = dict(os.environ)
    calls: list[dict] = []
    with patch.object(
        orchestrator,
        "_spawn_session_with_tail",
        _spawn_stub(calls, writes_verdict=True),
    ):
        _run_gate(gate_env, adapter=FakeAdapter())
    assert dict(os.environ) == before
