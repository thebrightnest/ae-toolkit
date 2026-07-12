# Bug Report: queue integrity envelope bricks all state commands after external edit

## Metadata

- **Reported:** 2026-07-12
- **Severity:** high
- **Status:** resolved

## Symptoms

After any edit to `.agents/work-queue.json` made outside the CLI (manual
curation, migration scripts), every `aet state` command that loads the queue —
`audit`, `heal`, `transition`, `set-stage`, `record-merge`, plus `add`, `sync`,
and `init-queue` — crashed with an uncaught `QueueIntegrityError` traceback:

```
queue.QueueIntegrityError: queue modified outside aet state — run `aet state audit`
```

The message named `aet state audit` as the remedy, but audit died on the same
check before printing anything, and even had it run, audit never mutates so it
could not restamp the `content_hash`. `heal` was equally bricked. Only
`bin/status` tolerated the stale hash (`verify=False` fallback). Net effect:
once the file was touched externally, no command in the tool could recover it;
the only escapes were hand-recomputing the sha256 or deleting the
`content_hash` key.

## Reproduction Steps

1. Create a stamped queue (any wrapper write by the tool, e.g. `aet add`).
2. Edit the `tasks` array externally without updating `content_hash` (e.g.
   null a stale `worktree` field).
3. Run `aet state audit .agents/work-queue.json` → traceback at
   `JsonBackend.load()` → `read_queue()` raise.
4. Run `aet state heal .agents/work-queue.json` → identical traceback.

Reproduced verbatim before the fix; both commands exited 1 with the traceback.

## Root Cause

- `read_queue`'s fail-closed `verify=True` default is correct for mutating
  paths, but `TaskBackend.load()` exposed no way to opt out — the interface had
  no `verify` parameter, and `JsonBackend.load()` called
  `read_queue(self.queue_file)` with the default hard-coded
  (`aet-work/lib/backends/json_backend.py:30`).
- Recovery commands are precisely the ones that must load unverified state:
  they exist to inspect and repair exactly the condition the check detects.
  Routing them through the same verified load made the envelope a dead end.
- The error message compounded it: it named `audit`, a read-only command that
  could neither bypass the check nor restamp the hash.
- Existing tests (`tests/test_queue_guard.py`) covered detection
  (fail-closed read, monotonic revision, legacy stamping) but no test ever ran
  a _recovery_ command against a tampered queue.

## Fix Summary

- Files modified:
  - `aet-work/lib/backends/base.py` — `TaskBackend.load(verify: bool = True)`
  - `aet-work/lib/backends/json_backend.py` — pass `verify` to `read_queue`
  - `aet-work/lib/backends/github_backend.py` — same
  - `aet-work/lib/backends/git_refs_backend.py` — accept flag (no-op; its
    tamper-evidence is a separate work item)
  - `aet-work/lib/queue.py` — error message now names audit (inspect) and
    `heal --apply` (repair)
  - `aet-work/bin/aet-state` — `cmd_audit` loads unverified and warns;
    `cmd_heal` loads unverified and `--apply` restamps the envelope before
    applying fixes (even with zero state changes); `main()` catches the dual
    `QueueIntegrityError` classes and prints a one-line refusal
  - `aet-work/SKILL.md` — mutation-guard section documents the real recovery
    path
  - `tests/test_queue_guard.py` — 4 recovery regression tests
  - `docs/adr/024-queue-integrity-recovery.md` — contract decision record
- Key change: `audit` is the diagnostic (loads unverified, never mutates),
  `heal --apply` is the repair (restamps the envelope via a normal backend
  save, preserving the external edits themselves).
- Side effects: heal restamps without reverting — externally edited field
  values survive, only `revision`/`content_hash` are refreshed. Mutating
  commands remain fail-closed; the refusal is now a clean one-liner instead
  of a traceback. `queue.py` is loaded twice in-process (`aet_queue` /
  `queue`), so the exception class exists twice; `aet-state` catches both.

## Regression Test

`tests/test_queue_guard.py`, new "Integrity recovery" section:

- `test_audit_runs_on_tampered_queue_and_warns`
- `test_heal_dry_run_tolerates_tamper_without_restamping`
- `test_heal_apply_restamps_envelope_with_no_state_changes` (the reported
  scenario: states match git, only the envelope is stale)
- `test_heal_apply_restamps_and_applies_state_fix`

## Validation

- [x] Reproduction steps no longer trigger the bug — audit reports, heal
      dry-run reports without mutating, `heal --apply` restamps (revision
      1 → 2, external edit preserved), verified reads pass afterwards
- [x] Existing test suite passes with no new failures — 515 passed, 30
      subtests
- [x] No regressions observed — mutating commands still fail closed on a
      tampered queue (verified via `aet-state transition`)
- [x] `ruff`, markdownlint, prettier, workflow lint, skills-lint, and the
      skill-structure validator pass on all touched files (the only
      markdownlint failures in the tree are pre-existing in unrelated
      in-progress `docs/plans/ewl-*` drafts)

## Lessons Learned

- Pattern: fail-closed guard with no designed recovery path — every bypass
  was ad-hoc (hand-recompute the hash) until one was built. Tamper-evidence
  without a repair path turns legitimate external edits into self-DoS.
- Prevention: when a guard names a remedy in its error message, that remedy
  must be exercised against the triggering condition in a test. The original
  tests proved detection; none proved the named remedy ran.
- Reference: ADR-024 (`docs/adr/024-queue-integrity-recovery.md`).
