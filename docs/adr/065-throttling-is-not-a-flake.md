---
subject: throttle-classification
amends: [30]
relates: [60]
---

# Throttling Is Not a Flake

## Status

Accepted (2026-08-24). Amends ADR-030 (Night-Shift Failure Handling), whose
taxonomy is a fixed menu this adds one member to. Motivated by item OI-07 of
`docs/audits/2026-08-24-open-items.md`.

## Context

ADR-030's menu is `environment | flaky | design | timeout | canceled`. No
pattern in `_ENVIRONMENT_PATTERNS` matches a rate limit, a quota, or a session
limit, so an API 429 with a non-zero exit fell through to `flaky` and was
requeued. Nothing about a provider limit is transient within a retry interval:
the requeued task ran again inside the same window and failed for the same
reason.

The reported consequence was 185 attempts against one closed window. That
number is no longer reachable — signatures normalise timestamps, hex and paths,
and the per-task breaker quarantines at three — but the replacement outcome is
also wrong in two ways. Three attempts are still spent on a wall, and the task
that gets quarantined was never broken: the breaker exists to stop a task
failing for its own reasons, and a closed window is not one.

The taxonomy has no member whose remedy is "wait". `environment` means repair
something, `flaky` means try again now, `design` means fix the code, `timeout`
means the session ran too long, `canceled` means an operator stopped it. A
provider limit is none of these.

## Decision

**`throttled` is a sixth failure class, and its remedy is time.**

1. **Classification is qualified, and ahead of `environment`.** The patterns
   name provider limits explicitly — `429` with an HTTP or status qualifier,
   `too many requests`, `rate limit exceeded/reached/hit`, `quota
   exceeded/exhausted`, `usage|session|token|message limit reached/exceeded`,
   `retry-after`, `overloaded_error`, `resource_exhausted`,
   `insufficient_quota`. Bare words are excluded for the reason
   `_ENVIRONMENT_PATTERNS` already documents: `rate limit` on its own matches a
   pytest line for `test_rate_limit_handling` and would file a design failure
   as a throttle. The check runs before `environment` because a 429 body often
   carries an auth or network word too, and the wait-for-the-window remedy is
   the more specific one. `canceled` and `timeout` still take precedence.

2. **A throttle is not breaker evidence.** `append_failure_if_countable`
   excludes it on the same grounds as `canceled`: the breaker judges the task,
   and three attempts against a closed window say nothing about the task.

3. **The run stops and the task is requeued.** The limited resource is shared
   by every task in the run, so the next task meets the same wall. The task
   returns to `ready` — it did nothing wrong — and the shift stops spawning
   with the remedy named. No triage session is spent: the answer is known.

4. **This overrides `--on-failure continue`.** Continuing would burn the rest
   of the queue on one limit, which is the outcome the flag exists to avoid,
   not the one it asks for. `halt` already stops.

## Consequences

A shift that meets a provider limit costs one attempt and stops, instead of
three attempts, a wrongly quarantined task, and a drained queue. The task is
`ready` at the next run, so recovery is re-running rather than clearing a
quarantine.

The class is observable in the same places as the others — the failure
signature on the task record, the triage default table, and the
`_TRIAGE_DEFAULT_ACTIONS` entry — so no reader learns about it from prose alone.

A limit that announces itself in wording none of the patterns cover still
classifies as `flaky` and is requeued once. That is the pre-existing behaviour
and the failure is visible in the tail; widening the patterns is cheaper than
guessing, and a bare-word pattern would cost design-failure accuracy.
