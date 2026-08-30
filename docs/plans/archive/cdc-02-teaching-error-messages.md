---
id: cdc-02-teaching-error-messages
size: S
work_class: normal
blocked_by:
  - cdc-01-single-hop-command-index
pipeline: minimal
security_review: skipped
security_review_reason: Error-message text only; no auth, data-model, API, or dependency surface.
docs_sync: skipped
docs_sync_reason: Adds example text to error output; no documented contract changes.
---

# Plan: Teaching Error Messages

## Context

- PRD: `docs/prds/cli-discovery-cost-prd.md` (R-3)

The error path is where an agent already is when it is confused, which makes it
the cheapest place to put the answer. Today it names the violated constraint and
stops:

```
aet sprint add
  → Missing argument 'target'.
```

The agent knows *what* is missing, not what a working call looks like, so it
spends another turn on `--help`. Adding one runnable example converts a dead end
into a resolution.

Unknown-command errors already carry Typer's "Did you mean 'add'?" suggestion.
That behavior is correct and is preserved; this plan adds to it rather than
replacing it.

Blocked by `cdc-01`, which establishes the non-TTY plain-text rendering path
this plan's output must use.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] The current error message is correct, just insufficient

## Task List

1. Add an example-invocation field to the command metadata, populated for every
   leaf command that takes a required argument — S (traces: R-3)
2. Extend the Typer error handler to append the canonical example to
   missing-argument and unknown-command errors, preserving the existing
   "Did you mean" suggestion — S (traces: R-3)
3. Add tests: missing-argument error contains a runnable example; unknown-command
   error retains its suggestion and gains an example; examples render plain text
   in non-TTY — S (traces: R-3)
4. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 150 expected diff lines
- **M**: ≤ 1 day human time / ≤ 600 expected diff lines

### Floor Check

- [x] Expected diff is below the calibrated floor threshold (≤ 50 headline lines)
- [ ] The change is limited to one subsystem and maintains no architectural invariant
- [x] `Files to Modify` substantially overlaps a sibling this plan is linearly ordered against
- [ ] This is docs-only and its sole consumer is a single sibling

Two signals checked — justification for keeping it separate from `cdc-01`:
the error path and the help path are distinct code paths with distinct failure
modes, and this change is independently reviewable and independently revertible.
Folding it into `cdc-01` would push that plan's diff past a single session and
mix a presentation change with a behavior change. **Flagged for scope validation
to confirm.**

## Rejected Alternatives

- **Print the full flat index on every error** — rejected: turns a 3-line error
  into a 1.5 KB dump, undoing the byte win R-1 buys. One targeted example is the
  cheaper answer.
- **Point the error at `aet --help`** — rejected: that is the extra turn this PRD
  exists to remove.

## Files to Modify

- `src/aet/cli/main.py`
- `tests/` (error-path tests)

## Validation Steps

- [ ] Lint passes
- [ ] Tests pass
- [ ] R-trace coverage: R-3 covered by ≥ 1 task
- [ ] Existing "Did you mean" behavior asserted as unchanged
- [ ] CLI-boundary tests distinguished from unit tests
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit. Errors return to naming only the violated constraint; no exit
codes or command behavior change, so nothing downstream depends on the added text.

## Pipeline

`minimal` — S-sized, single-file change with no architectural invariant.

---

_Stage: plan-approved_
