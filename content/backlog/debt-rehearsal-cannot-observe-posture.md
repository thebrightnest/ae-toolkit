---
type: debt
status: accepted
recorded: 2026-08-28
source: docs/retros/2026-08-28-aet-run-retro.md
trigger: >-
  The containment work in outcome-level-containment-testing, which needs this fixture anyway.
depends_on: []
blocks: []
---

# The end-to-end rehearsal cannot observe posture-dependent defects

`tests/orchestrator/test_nightshift_rehearsal.py` runs a real unattended batch
and asserts a breaker quarantine, which looks like coverage for the runaway-loop
class. It cannot see that class: its temp repo has no in-tree
`.agents/aet-config.json`, so the posture is `shadow`, pushes are suppressed, and
origin never carries `refs/aet/*`; and it patches `should_quarantine_task` to
`threshold=1`, so it never tests accumulation across attempts.

**Why accepted:** the two focused tests added on 2026-08-28
(`test_task_record_replication.py`, `test_stage_credit_on_failure.py`) cover the
mechanisms in shared posture at real thresholds. Reshaping the rehearsal is a
fixture change whose other assertions depend on the current single-run shape, and
a second real batch run costs wall-clock in every `make validate`.

**Trigger to fix:** the containment work in
`docs/ideas/outcome-level-containment-testing.md`, which needs this fixture
anyway.
