---
type: debt
status: accepted
recorded: 2026-08-28
source: docs/bugs/20260828-context-digest-absolute-paths-under-symlink.md
trigger: >-
  Any pre-existing failure found by a scope widening rather than by the change
  that introduced it — the second occurrence makes this a pattern, not an
  incident.
depends_on: []
blocks: []
---

# An impact-scoped gate reports green over a standing red

`make validate` runs the target set `aet.change_scope` resolves for the current
diff. A test outside that set is not run, so a failure that already exists on
`main` is invisible until some unrelated change happens to select it.

That happened on 2026-08-28. Four `make validate` runs passed during a session of
orchestrator, breaker and ship changes. The fifth, whose diff touched `AGENTS.md`
and `docs/CONVENTIONS.md`, widened the scope to the full suite and surfaced
`test_context_hook_json_matches_golden_fixture` — which had been failing on
`main` since before the session began (verified at `568b1807`).

**Why accepted:** impact scoping is the deliberate trade recorded in ADR-051 and
the telemetry work, and it is what makes the gate usable on a large suite. The
alternative — a full suite on every change — was measured and rejected. Nothing
about this occurrence argues the trade is wrong; it argues the trade has a blind
spot nobody had named.

**What would close it:** a periodic full-suite run whose only job is to catch a
standing red — nightly, or on merge to `main` — so a pre-existing failure is
attributed to the change that introduced it rather than to the unrelated change
that widened the scope. The scoped gate stays as it is.

**Trigger to fix:** the second time a pre-existing failure is discovered by a
scope widening. One occurrence is an incident; two is the pattern that justifies
the extra run.
