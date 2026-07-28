---
id: tap-07-claude-token-capture-verification
size: S
blocked_by: []
pipeline: standard
status: queued
security_review: skipped
security_review_reason: parses a JSON envelope the CLI already writes to captured stdout; no new input source, no credential handling, and the bounded tail scan that limits parse cost is unchanged
docs_sync: required
docs_sync_reason: the determination is a documentation deliverable on both branches — a defect updates the token-capture contract in docs/telemetry-guide.md, and a clean run commits the verification record explaining the three archived nulls, which is the only artifact this plan produces in that case
---

# Plan: Verify Claude Code Token Capture End to End

## Context

- PRD: `docs/prds/telemetry-adapter-parity-prd.md` (R-11)
- Measured motivation: `reports/2026-07-25-aet-performance-observability-review.md` — all three
  Claude Code stage records in the archive carry `token_count: null`, against 300 of 402 kimi
  stage records carrying a value. n=3 is far too small to call it a defect; it is also too
  suspicious to leave unexamined.
- Verified current code (2026-07-26): `usage.parse_usage`
  (`src/aet/usage.py:43`) dispatches to `_parse_claude` (`:67`), which finds the
  `type == "result"` element, sums
  `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`, adds `output_tokens`,
  and reads `total_cost_usd`. `cli_adapter` declares `usage_mode="json-envelope"`
  (`src/aet/cli_adapter.py:75`), which appends `--output-format json` (`:12-14`), and the
  orchestrator calls `parse_usage` whenever `adapter.usage_mode is not None`
  (`src/aet/cli/orchestrator.py:899-900`). Every link is unit-tested; the chain has never been
  verified end to end on a live session.
- Candidate causes worth ruling out, in order: the envelope not reaching the parser (the tee's
  `TAIL_SCAN_BYTES` window, or stdout interleaving under `--dangerously-skip-permissions`); flag
  ordering (`_USAGE_MODE_FLAGS` are inserted before the prompt flag, `:45-48`); an envelope shape
  drift since the unit fixtures were captured; and the `total == 0 and cost_usd is None` early
  return (`:92`) collapsing a real-but-empty usage block to `None`.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
  — deliberately: n=3 with no reproduction is not a demonstrable defect. This plan's first
  deliverable is the determination. If it finds a reproducible defect, the fix is small and lands
  here; if it does not, the verification itself is the deliverable and the null figures are
  explained rather than left hanging.

## Locked design

- **Verification first, fix second.** Run a live Claude Code stage session, capture the raw tee
  output alongside the emitted `stage` record, and compare. The question "does the envelope reach
  the parser?" is answered from evidence, not inferred.
- **The outcome is recorded either way.** A defect yields a fix plus a regression test built from
  the captured envelope. A clean run yields a committed note explaining why the archived nulls
  exist — most likely because those three sessions predate `--output-format json` being wired,
  or ran through a path that bypassed it.
- **No estimation, ever** (ADR-031). If tokens genuinely cannot be captured for a session, the
  record keeps `null`. Nothing here introduces a fallback figure.
- **Fixture from reality.** Any regression test uses an envelope captured from a live session,
  not a hand-written one — a hand-written fixture is what a drifted schema would still pass.

## Rejected Alternatives

- **Declare it a defect and fix it speculatively** — rejected: with n=3 and every unit test
  passing, a speculative fix would be a change with no failing case to prove it, and would
  obscure the real cause if the nulls turn out to be historical.
- **Widen the tail scan window preemptively** — rejected for the same reason; if the window is
  the cause, the verification shows it and the change is then evidence-backed.
- **Wait for more Claude sessions to accumulate** — rejected: the archive gains Claude sessions
  slowly, and `tap-04` makes Claude a first-class CLI. Verifying now avoids building parity work
  on an unverified usage path.

## Task List

1. Run a live Claude Code stage session with the tee output preserved; capture the raw envelope
   and the emitted `stage` record side by side — S (traces: R-11)
2. Determine which link fails, if any: envelope present in captured output → reaches
   `parse_usage` → parses → populates `token_count` — S (traces: R-11)
3. Write the verification record either way; if a defect is found, fix it and add a regression test
   built from the captured envelope — S (traces: R-11)
4. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 150 lines · M ≤ 1 day / ≤ 600 lines.

### Floor Check

- [x] Stands alone: one question, one live session, one determination. Independent of every other
  `tap-*` plan — it touches the usage path, not the session-log path.

## Files to Modify

- `src/aet/usage.py` (only if a defect is found)
- `src/aet/cli_adapter.py` (only if flag ordering is the cause)
- `tests/usage/test_usage_parsing.py` (regression test, or the captured-envelope fixture)
- `tests/fixtures/usage/claude_live_envelope.json` (new — captured, redacted)
- `docs/telemetry-guide.md` (only if the documented contract proves wrong)
- `reports/2026-07-26-claude-token-capture-verification.md` (new — the verification record, written
  on both branches: it states which link was checked at each step and what was found)

## Validation Steps

- [x] `make validate` passes
- [x] A live Claude Code stage session records a non-null `token_count`, **or** the verification
      records why it cannot, with a reproduction
- [x] If a defect was found: a regression test built from the captured live envelope fails before
      the fix and passes after (no defect found)
- [x] The committed verification record names the link that was verified at each step; when no
      defect was found it also explains the three archived nulls
- [x] Coverage:
  - `test_claude_live_captured_envelope_parses` (unit)
- [x] R-trace coverage: R-11 by tasks 1, 2, 3; no unknown R-ids
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

If no defect is found, there is nothing to roll back — the deliverable is a committed note and a
fixture. If a fix landed, revert the merge commit; `token_count` returns to null for Claude
sessions, which is the current behaviour and is null-honest either way (ADR-031).

---

*Stage: implemented*
*Next step: run `aet-qa`*
