---
type: debt
status: accepted
recorded: 2026-07-27
source: tap-02-shared-runner-registry
initiative: Telemetry adapter parity (tap-01…tap-06)
trigger: >-
  The first detection miss found in production telemetry that the synthetic fixture did not predict.
depends_on: []
blocks: []
---

# Superset-replay fixture is synthetic, not captured

The superset-replay test builds its input by hand instead of replaying a real
captured wire log. It therefore proves the registry's behaviour against the
shapes the author thought of, not against the shapes the field actually emits.

**Why accepted:** non-blocking review flag; the synthetic fixture still covers
every runner-table entry and the review passed on it.

**Trigger to fix:** the first detection miss found in production telemetry that
the synthetic fixture did not predict — replace it with a captured log then.
