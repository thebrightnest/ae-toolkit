# `TestWireTestRunEmission` flake — a test stub reimplementing the slug rule

**Date:** 2026-08-23
**Status:** fixed
**Source:** `content/bugs/open-items.md` item 7 (residual)

## Symptom

`TestWireTestRunEmission::test_orchestrated_claude_stage_writes_observed_test_run`
failed intermittently at roughly **1 in 5 runs, in isolation** — not only under
full-suite load, as previously recorded. It failed two ways:
`AssertionError: None != 'r6-e2e-session'` on `session_ref`, and on the
non-null duration assertion.

The flake was load-bearing: it made every full-suite result ambiguous, and
during the item-1 fix it caused a clean change to be misread as a regression.

## Reproduction

Running the test 15 times in a loop reproduced it 3 times. A probe harness
around `run_stage` captured, on each failure, the full stdout, the extracted
session id, and both candidate transcript paths.

## Root cause

Not timing. Not the subprocess. A **string rule reimplemented in the test**.

Claude Code stores transcripts under a slug of the working directory.
Production computes it with `cwd_slug` (`src/aet/session_log_claude.py:36`):

```python
_SLUG_UNSAFE = re.compile(r"[^A-Za-z0-9-]")
return _SLUG_UNSAFE.sub("-", cwd.rstrip("/"))
```

Every character outside `[A-Za-z0-9-]` becomes `-`, including `.` and `_`.

The test's stub `claude` binary reimplemented that rule as:

```python
slug = cwd.rstrip("/").replace("/", "-")
```

which handles only `/`. The two agree for most paths and diverge whenever the
temp path contains any other unsafe character. Python's `tempfile` name
alphabet is `ascii_letters + digits + "_"`, so an underscore appears in a given
8-character suffix about 12% of the time; the test builds two such names, which
lands the observed ~1-in-5.

Captured divergence from a failing run:

```
stub slug: ...-T-tmpiu2j6_f2-repo
real slug: ...-T-tmpiu2j6-f2-repo
candidate: .../projects/-...-tmpiu2j6-f2-repo/r6-e2e-session.jsonl  exists: False
```

The envelope was present in stdout and the transcript was written — just to a
directory the reader never looked in. `_resolve_claude_session_id` then
returned `None`, exactly as designed: it refuses to guess an identifier
(ADR-031).

The irony is on record: `cwd_slug`'s own docstring documents this bug class —
*"Replacing only `/` — as this did until the fix — silently missed every
orchestrated session."* Production was fixed. The test stub kept the old rule.

## Fix

The stub no longer computes a slug. The test resolves the transcript directory
with `transcript_path_for` and bakes the literal path into the stub, so
production owns the rule and there is one source of truth.

A repo-wide grep confirms this was the only reimplementation.

File: `tests/orchestrator/test_orchestrator.py`.

## Validation

- The test passes **20/20** where ~4 failures were expected (p ≈ 1% by chance).
- `tests/orchestrator/` — **256 passed, 0 failed**.

## Lesson

A test that reimplements the rule it is testing against does not test that
rule; it tests a copy that can drift. The drift here was invisible for as long
as the random inputs happened to avoid the difference, and it degraded into
"that test is just flaky" — which then masked real signal.
