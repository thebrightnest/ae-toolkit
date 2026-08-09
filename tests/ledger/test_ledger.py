"""Unit tests for the content-addressed provenance ledger."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aet.ledger import Ledger


def _ledger(tmp_path: Path) -> Ledger:
    return Ledger(tmp_path / "ledger.jsonl")


def test_deterministic_event_ids(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    event1 = ledger.write_event(
        source="sprint-add",
        task="slc-01",
        kind="cut",
        ref="abc123",
        ref_kind="plan-hash",
    )
    event2 = ledger.write_event(
        source="sprint-add",
        task="slc-01",
        kind="cut",
        ref="abc123",
        ref_kind="plan-hash",
    )
    assert event1["id"] == event2["id"]


def test_duplicate_write_is_no_op(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ledger.write_event(
        source="sprint-add",
        task="slc-01",
        kind="cut",
        ref="abc123",
        ref_kind="plan-hash",
    )
    ledger.write_event(
        source="sprint-add",
        task="slc-01",
        kind="cut",
        ref="abc123",
        ref_kind="plan-hash",
    )

    lines = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    stored = json.loads(lines[0])
    assert stored["kind"] == "cut"


def test_missing_occurred_at_rejected_when_no_ref(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    with pytest.raises(ValueError, match="explicit caller-supplied occurred_at"):
        ledger.write_event(
            source="aet-state",
            task="slc-01",
            kind="land",
        )


def test_ingest_backfill_source_rejected(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    with pytest.raises(ValueError, match="reserved source rejected"):
        ledger.write_event(
            source="ingest-backfill",
            task="slc-01",
            kind="cut",
            ref="abc123",
            ref_kind="plan-hash",
        )


def test_occurred_at_differs_from_created_at(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    event = ledger.write_event(
        source="aet-state",
        task="slc-01",
        kind="land",
        occurred_at="2026-01-01T00:00:00Z",
    )
    assert event["occurred_at"] == "2026-01-01T00:00:00Z"
    assert event["created_at"] != event["occurred_at"]
    assert event["created_at"].startswith("2026-08")


def test_ref_kind_required_when_ref_supplied(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    with pytest.raises(ValueError, match="ref_kind is required"):
        ledger.write_event(
            source="sprint-add",
            task="slc-01",
            kind="cut",
            ref="abc123",
        )


def test_unknown_kind_rejected(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    with pytest.raises(ValueError, match="unknown event kind"):
        ledger.write_event(
            source="sprint-add",
            task="slc-01",
            kind="claim",
        )


def test_read_events_filters(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ledger.write_event(
        source="sprint-add",
        task="slc-01",
        kind="cut",
        ref="abc",
        ref_kind="plan-hash",
    )
    ledger.write_event(
        source="aet-state",
        task="slc-01",
        kind="land",
        occurred_at="2026-01-01T00:00:00Z",
    )
    ledger.write_event(
        source="sprint-add",
        task="slc-02",
        kind="cut",
        ref="def",
        ref_kind="plan-hash",
    )

    assert len(ledger.read_events()) == 3
    assert len(ledger.read_events(task="slc-01")) == 2
    assert len(ledger.read_events(kind="land")) == 1
    assert len(ledger.read_events(source="sprint-add")) == 2
    assert len(ledger.read_events(task="slc-02", kind="cut")) == 1
