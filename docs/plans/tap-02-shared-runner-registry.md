---
id: tap-02-shared-runner-registry
size: M
blocked_by: [tap-01-factory-metrics-stage-records-only]
pipeline: standard
status: queued
security_review: skipped
security_review_reason: parses command strings already recorded in the agent's own session log for classification only; no execution, no new input surface, and the parser never runs or shells out to what it matches
docs_sync: required
docs_sync_reason: the runner registry becomes the documented answer to "what counts as a test run"; docs/telemetry-guide.md describes the current anchored-match behaviour
---

# Plan: One Shared Runner Registry Behind Detection and Scope Classification

## Context

- PRD: `docs/prds/telemetry-adapter-parity-prd.md` (R-1, R-2, R-3)
- Measured motivation: `reports/2026-07-25-aet-performance-observability-review.md` — 2,074 of
  3,453 test invocations missed across 950 kimi session logs; telemetry sees 49% of test time
  overall (aiskills 50%, blueocean 5%, manager 0%). In Claude Code transcripts, 7 of 170
  test-shaped Bash calls are detected.
- Verified current behaviour (2026-07-26): `wirelog._TEST_RUNNER_RES`
  (`src/aet/wirelog.py:29-38`) is 8 regexes, **all** anchored `^\s*` — pytest,
  `python3? -m pytest`, vitest, jest, `make (test|validate)`, `npm test`, `cargo test`,
  `go test`. The dominant missed shape is `cd <worktree> && <test>` (n=85, 145.0 min in the
  Claude corpus alone), followed by `.venv/bin/python` (n=21), `php` (n=21), `npx` (n=5).
- `telemetry._test_runner_args` (`src/aet/telemetry.py:62`) carries a **second** copy of the same
  list — its docstring says so: "The recognized runners mirror the wire-extraction match list
  (v1)". Two lists, one concept, already drifting.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
  — the anchoring gap is a defect, but the deliverable is the shared registry (a module boundary
  and a new runner set), which `aet-bug-report`'s targeted-fix path cannot produce.

## Locked design

- **One registry module owns the runner set.** Both `wirelog.is_test_command` and
  `telemetry.classify_test_scope` resolve commands through it. Neither keeps a private list, and
  the duplicated docstring note in `_test_runner_args` goes away with the duplication.
- **The registry resolves a command to a runner and its arguments**, so detection ("is this a
  test?") and classification ("what scope?") are two readings of one parse — a command the
  detector recognises is classifiable by construction (R-3).
- **Normalisation pipeline, applied before matching:** tokenise on `&&`, `;`, `|` and take the
  last segment; strip `cd … &&`, `source … &&`, `. … &&`; strip leading `VAR=value`
  assignments; strip interpreter path prefixes (`.venv/bin/`, `./vendor/bin/`, any
  `*/bin/` prefix on a recognised runner); unwrap runner wrappers (`poetry run`, `uv run`,
  `npx`, `npm run`, `yarn`, `pnpm`, `bundle exec`, `time`).
- **Runners added (R-2):** `rspec`, `phpunit`, `php artisan test`, `dotnet test`, `gradle test`,
  `python -m unittest` — alongside the v1 eight.
- **Anchoring is retained after normalisation, not abandoned.** The matcher still anchors; what
  changes is that it anchors on a *normalised* command. Substring matching anywhere in the raw
  string would match `grep pytest` and `echo "run pytest"`.
- **False positives are the failure to avoid.** The detector feeds telemetry, not a gate, but a
  wrong match records a fabricated test run. Where normalisation is ambiguous, do not match.
- `make` target scope is deliberately **not** fixed here — it needs `change_scope` output and is
  `tap-06`. This plan keeps the current `make` behaviour and moves it into the registry unchanged.

## Rejected Alternatives

- **Fix the regexes in place, leave the two lists** — rejected: `_test_runner_args`'s own
  docstring documents the duplication, and R-2's six new runners would have to be added twice.
- **Substring match anywhere in the command** — rejected: matches `grep -r pytest`, `git commit
  -m "fix pytest"`, and any command that merely mentions a runner.
- **Shell-parse with a real grammar (`bashlex` or similar)** — rejected per ADR-037's runtime
  dependency policy: a token-level normaliser covers the measured shapes, and the residue is
  recorded as unmatched rather than guessed.
- **Have the classifier call the detector** — rejected: it makes classification depend on a
  boolean that has already discarded the parse. One registry returning `(runner, args)` serves
  both without a call chain.

## Task List

1. Add the runner registry module: runner table, command normalisation (separator split, `cd`/
   `source`/`.` prefix stripping, env assignments, path prefixes, wrapper unwrapping), and a
   resolve function returning the matched runner plus its arguments — M (traces: R-1, R-3)
2. Extend the runner table with `rspec`, `phpunit`, `php artisan test`, `dotnet test`,
   `gradle test`, `python -m unittest` — S (traces: R-2)
3. Rewrite `wirelog.is_test_command` to delegate to the registry; delete `_TEST_RUNNER_RES` — S
   (traces: R-1, R-3)
4. Rewrite `telemetry._test_runner_args` to delegate to the registry, preserving current `make`
   behaviour verbatim (its correction is `tap-06`); delete the duplicated runner list and its
   docstring note — S (traces: R-3)
5. Tests (see Validation Steps) — M (traces: R-1, R-2, R-3)
6. Merge branch to main and verify integration — S

**Size definitions:** S ≤ 2 hr / ≤ 150 lines · M ≤ 1 day / ≤ 600 lines.

### Floor Check

- [x] Stands alone: the registry, both call sites, and the new runners are one coherent unit —
  splitting the registry from its two consumers would leave a module with no callers, and
  splitting R-2 from R-1 would add runners to a matcher that still cannot see them behind `cd`.

## Files to Modify

- `src/aet/test_runners.py` (new — the shared registry)
- `src/aet/wirelog.py`
- `src/aet/telemetry.py`
- `tests/test_runners/test_runner_registry.py` (new)
- `tests/wirelog/test_wirelog.py`
- `tests/telemetry/test_telemetry.py`
- `docs/telemetry-guide.md` (document what counts as a test run and the normalisation rules)

## Validation Steps

- [ ] `make validate` passes
- [ ] Coverage:
  - `test_detects_test_command_after_cd_and_separator` (unit) — `cd /path/to/wt && make validate`
  - `test_detects_test_command_after_source_and_dot_prefixes` (unit)
  - `test_detects_test_command_with_leading_env_assignments` (unit)
  - `test_detects_test_command_with_interpreter_path_prefix` (unit) —
    `.venv/bin/python -m pytest`
  - `test_detects_test_command_behind_wrapper` (unit, table-driven over `poetry run`, `uv run`,
    `npx`, `npm run`, `yarn`, `pnpm`, `bundle exec`, `time`)
  - `test_does_not_detect_runner_mentioned_in_unrelated_command` (unit) — `grep -r pytest .`,
    `git commit -m "fix pytest"`, `echo "run pytest"`
  - `test_each_new_runner_is_detected_and_classified` (unit, table-driven over the R-2 six)
  - `test_registry_removal_breaks_both_detection_and_classification` (unit) — the R-3 proof that
    there is one list, not two
  - `test_make_scope_classification_unchanged_by_registry_move` (unit) — pins current behaviour
    so `tap-06` owns the correction
- [ ] R-trace coverage: R-1 by tasks 1, 3, 5; R-2 by tasks 2, 5; R-3 by tasks 1, 3, 4, 5; no
      unknown R-ids
- [ ] For the new normalisation logic in `src/aet/test_runners.py`, tests above name the coverage
- [ ] Replaying a captured kimi session fixture through `extract_test_invocations` yields a
      superset of the pre-change invocations — nothing previously detected is lost
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the merge commit; `wirelog` and `telemetry` return to their private anchored lists. No
telemetry schema changes here, so records written under the wider detector remain valid and
readable — they are simply more numerous than a reverted detector would produce, which is
recorded in the `tap-01` re-baseline note.

---

*Stage: qa-complete*
*Next step: run `aet-review`*
