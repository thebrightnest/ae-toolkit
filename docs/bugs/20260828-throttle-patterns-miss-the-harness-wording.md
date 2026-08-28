# Bug Report: `_THROTTLE_PATTERNS` misses the wording the Claude Code harness emits

## Metadata

- **Reported:** 2026-08-28
- **Severity:** high (a missed throttle costs a full requeue loop)
- **Status:** fixed 2026-08-28, after
  `docs/bugs/20260828-throttle-remedy-cannot-see-its-own-class.md`

## Symptoms

A session that ends against a provider session limit classifies as `flaky` and
is requeued, which is the outcome ADR-065 exists to prevent. Reported from the
consuming repository (`dhl-agentic-tot`, task `pub-03`): 22 attempts, 40 of them
ending in a session-limit `429` inside 0.5–2.6s with zero output tokens, at a
recorded cost of $23.77 for 34.6M tokens.

## Reproduction Steps

```python
classify(exit_code=1, tail="You've hit your session limit · resets 6pm",
         stage="plan-approved", verdict_recorded=False,
         shutdown=False, killed_by_timeout=False)
```

Observed: `FailureClass.FLAKY`. Expected: `FailureClass.THROTTLED`.

The miss is confirmed against the field data rather than inferred. Every one of
the 44 result envelopes in the `pub-03` run log classifies as `flaky`, 40 of them
carrying `"result":"You've hit your session limit · resets 6pm (Europe/Lisbon)"`
alongside `"api_error_status":429`; the run's telemetry independently records
`failure_class: flaky` for 21 stage sessions, all at `exit_code: 1`. The
classifier ran on the real tail every time and missed it every time.

Three real tails miss; two synthetic ones match:

| Tail | Class |
| --- | --- |
| `{"error":{"api_error_status":429}}` | `flaky` |
| `API Error: 429 {"type":"error"}` | `flaky` |
| `You've hit your session limit · resets 6pm` | `flaky` |
| `status: 429` | `throttled` |
| `session limit reached` | `throttled` |

## Root Cause

Only the classification is wrong; the remedy machinery around it is correct.
`orchestrator.py:2923-2935` stops the run on `THROTTLED` and deliberately
overrides `--on-failure continue`, and `breaker.append_failure_if_countable`
exempts the class from quarantine counting.

Two patterns in `failure.py:58-70` near-miss:

- `\b(?:HTTP|status(?:\s+code)?)\s*[:=]?\s*429\b` — `\bstatus` cannot match
  after `_`, which is a word character, so `"api_error_status":429` fails. The
  same pattern also rejects a bare `429` under any other qualifier, including
  `API Error: 429`.
- `\b(?:usage|session|token|message)\s+limit\s+(?:reached|exceeded)\b` — the
  harness says `hit` and `resets`, not `reached` or `exceeded`.

ADR-065 predicted this class of miss and priced the remedy in its Consequences:
"A limit that announces itself in wording none of the patterns cover still
classifies as `flaky` and is requeued once… widening the patterns is cheaper
than guessing." The prediction held; the ADR's premise that a miss costs one
requeue did not, for the reason recorded in the companion breaker report.

The gap survived a green suite because `THROTTLE_TAILS`
(`tests/failure/test_failure_taxonomy.py:153-164`) encodes invented wording —
`"session limit reached for this account"`, `"usage limit reached; resets at
18:00"` — rather than tails captured from a harness.

## Consequences

A closed provider window is indistinguishable from a flake, so the run keeps
spawning into the same wall until something else stops it. Where the breaker
also fails to count, nothing does.

## Fix Direction

Two patterns in `failure.py`: an unanchored `api_error_status"?\s*[:=]\s*429`
and a `session limit` form admitting `hit`/`resets`. A bare-word `429` remains
excluded on ADR-065's grounds — a qualifier is what separates a provider limit
from a test name.

Regression cases must be the verbatim observed tails, not paraphrases, and the
existing synthetic entries stay: they pin the patterns that already work.

**Landed as four patterns** (`failure.py:65-82`), one per observed wording plus
one for the reset form:

- `api_error_status"?\s*[:=]\s*429` — the JSON field, whose `_` defeats a
  `\bstatus` anchor
- `\bapi\s+error:?\s*429\b` — the bare form under a qualifier the HTTP/status
  pattern does not name
- `\b(?:hit|reached|exceeded)\s+(?:your|the|my)\s+(?:usage|session|token|message)\s+limit\b`
- `\b(?:usage|session|token|message)\s+limit\b[^\n]{0,40}?\bresets?\b`

Bare words stay excluded on ADR-065's grounds, and the exclusions are asserted:
`test_rate_limit_handling failed` and `AssertionError: session limit for user`
both still classify as `flaky`.

Regression cases are the verbatim envelope and message, not paraphrases
(`tests/failure/test_failure_taxonomy.py:165-172`). The synthetic entries stay:
they pin the patterns that already worked.

**Ordering.** This fix did not land first. Today a missed throttle is filed as
`flaky`, which is countable breaker evidence; a correct `throttled` classification
is deliberately *not* countable (`breaker.py:34-61`), and the remedy that should
replace the breaker cannot see the class at all — see the blocking report. Until
that was fixed, widening the patterns would have removed the only bound the loop
had; it landed first.

ADR-065 needs an amendment: its Consequences section asserts the 185-attempt
outcome "is no longer reachable", and the `pub-03` record is a counterexample —
34.6M tokens and $23.77 across 22 attempts.
