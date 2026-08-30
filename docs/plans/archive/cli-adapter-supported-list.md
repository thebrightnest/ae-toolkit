---
id: cli-adapter-supported-list
size: S
work_class: normal
blocked_by: []
pipeline: minimal
security_review: skipped
security_review_reason: Pure internal helper function; no auth, data-model, API, or dependency surface.
docs_sync: skipped
docs_sync_reason: Internal helper function; no public documentation change.
---

# Plan: Supported CLI Adapters Helper

## Context

- PRD: `docs/prds/agy-adapter-prd.md`

AET supports multiple agent CLIs (`kimi`, `claude`, `agy`) registered in `src/aet/cli_adapter.py`. Currently, callers inspect `ADAPTERS` directly or iterate over keys. Adding a public `supported_adapters()` query helper provides a clean, encapsulated API for tooling, telemetry, and diagnostics.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] Adds a clean query interface to `src/aet/cli_adapter.py`

## Task List

1. Implement `supported_adapters() -> list[str]` in `src/aet/cli_adapter.py` returning the registered adapter keys — S
2. Add unit tests in `tests/cli/test_cli_adapter.py` asserting `supported_adapters()` returns `["kimi", "claude", "agy"]` in registration order — S
3. Verify test suite and lint — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 150 expected diff lines
- **M**: ≤ 1 day human time / ≤ 600 expected diff lines

### Floor Check

- [x] Expected diff is below the calibrated floor threshold (≤ 50 headline lines)
- [x] The change is limited to one subsystem and maintains no architectural invariant
- [ ] `Files to Modify` substantially overlaps a sibling this plan is linearly ordered against
- [ ] This is docs-only and its sole consumer is a single sibling

## Rejected Alternatives

- **Export raw `ADAPTERS` dict directly** — rejected: encapsulating behind `supported_adapters()` prevents accidental external mutation of the adapter registry.

## Files to Modify

- `src/aet/cli_adapter.py`
- `tests/cli/test_cli_adapter.py`

## Validation Steps

- [ ] Lint passes: `make lint-py`
- [ ] Tests pass: `pytest tests/cli/test_cli_adapter.py`
- [ ] All checks pass: `make validate`

## Rollback Plan

Revert the commit if issues occur.

## Pipeline

`minimal` — S-sized, internal helper function with no architectural invariant.

---

_Stage: plan-approved_
