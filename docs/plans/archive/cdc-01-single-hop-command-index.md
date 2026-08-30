---
id: cdc-01-single-hop-command-index
size: M
work_class: normal
blocked_by: []
pipeline: standard
security_review: skipped
security_review_reason: Presentation-only change to CLI help rendering; no auth, data-model, API, or dependency surface.
docs_sync: required
docs_sync_reason: Replaces `aet --help` output outright; `docs/CLI.md` and any AGENTS.md reference to the help surface must reflect it.
---

# Plan: Single-Hop Command Index

## Context

- PRD: `docs/prds/cli-discovery-cost-prd.md` (R-1, R-2)
- Taxonomy: ADR-039 (`aet <noun> <verb>`) — this plan changes presentation only,
  never command names or Typer groups in code. The presentation axis is called a
  **section**, deliberately not a "group": ADR-039 already uses *group* for a
  noun-scoped command group, and reusing the word invites the drift that ADR exists
  to prevent.

`aet --help` currently lists 35 implementation-module groups and no leaf
commands. Reaching an executable invocation costs three sequential invocations
totalling 8,244 bytes. Every hop already knows the answer; none of them shows it
first.

`src/aet/cli/docs.py` already walks the Typer tree for `aet docs generate`
(`_walk_commands`, `_format_command`, `generate_cli_reference`). This plan
renders that same walk to stdout under a task grouping. The tree walk is reused,
not rewritten.

R-2 is folded in here rather than split out: the non-TTY plain-text path is a
property of the renderer this plan introduces, and a separate plan would
substantially overlap this one's files while being linearly ordered against it
(two Floor Check signals).

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] Discovery cost is a design property, not unexpected behavior

## Task List

1. Extract the Typer tree walk in `src/aet/cli/docs.py` into a reusable helper that
   yields leaf commands with name, one-line description, and required arguments
   (arguments inline; options excluded, per the settled Open Question) — S (traces: R-1)
2. Add the static section map (5 sections covering all 35 top-level entries per the
   PRD table) and a resolver that assigns every leaf command to exactly one section,
   failing loudly on an unmapped command — M (traces: R-1)
3. Implement the flat index renderer and register it as the `aet --help` callback,
   replacing the Typer group listing — M (traces: R-1)
4. Add non-TTY detection so help renders plain text with no box-drawing characters,
   leaving TTY output unchanged — S (traces: R-2)
5. Add tests: full-tree coverage (zero omissions), one-hop assertion by construction,
   no box-drawing in non-TTY, every leaf command resolves to exactly one section, and
   a recorded before/after byte count against the 8,244-byte baseline — M (traces: R-1, R-2)
6. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 150 expected diff lines
- **M**: ≤ 1 day human time / ≤ 600 expected diff lines
- **L**: > 1 day OR > 600 lines

### Floor Check

- [ ] Expected diff is below the calibrated floor threshold
- [ ] The change is limited to one subsystem and maintains no architectural invariant
- [ ] `Files to Modify` substantially overlaps a sibling this plan is linearly ordered against
- [ ] This is docs-only and its sole consumer is a single sibling

No signals checked. This plan stands alone.

## Rejected Alternatives

- **Add a new `aet help` command, leaving `aet --help` unchanged** — rejected: the
  agent must first discover the new command exists, which is the discovery problem
  the PRD is solving. The reflex path has to be the correct path.
- **Add intent search (`aet help "promote a plan"`)** — rejected for this plan:
  needs a ranking layer and a defined miss behavior. Not required to collapse 3 hops
  to 1, and would enlarge this plan past one session.
- **Keep the module grouping and just add leaf commands under it** — rejected:
  the grouping is what makes the index scannable; module names (`sync`, `aet_state`)
  do not describe tasks, which is why the current surface fails.
- **Derive sections from per-command metadata instead of a static map** — rejected
  at scope validation: it is presentation config with one consumer, and metadata
  would scatter it across 35 modules for no gain.
- **A pty-based test for the TTY branch** — rejected: `CliRunner` output is
  byte-identical to a pipe, so the TTY branch cannot be evidenced without a pty, and
  pty tests are flaky across platforms for the value added. The TTY path is asserted
  unmodified by diff inspection instead.

## Files to Modify

- `src/aet/cli/main.py`
- `src/aet/cli/docs.py`
- `tests/` (new test module for the help index)
- `docs/CLI.md` (regenerated)

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: R-1 and R-2 each covered by ≥ 1 task
- [ ] New helper module named with its covering test
- [ ] Unit tests (renderer, section resolver) and CLI-boundary tests (invoked output) distinguished
- [ ] TTY rendering path confirmed unmodified by diff inspection
- [ ] Before/after byte count recorded in validation output
- [ ] `aet docs generate` regenerates `docs/CLI.md` without drift
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. The change is presentation-only — no command behavior, arguments,
defaults, or exit codes are touched, so revert restores the prior help surface with
no state or data implications.

## Pipeline

`standard` — M-sized change to the CLI entry point.

---

_Stage: plan-approved_
