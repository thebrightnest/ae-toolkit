---
type: debt
status: accepted
recorded: 2026-07-27
source: tap-02-shared-runner-registry
initiative: Telemetry adapter parity (tap-01…tap-06)
trigger: >-
  When tap-06 lands and the PRD is synced as a whole.
depends_on: []
blocks: 
  - tap-06
---

# Stale code anchors in the parity PRD

`docs/prds/telemetry-adapter-parity-prd.md` cites file/line anchors that the
tap-02 implementation has already moved. `aet-sync-docs` reads those anchors, so
they will drift further with each of tap-03…tap-06.

**Why accepted:** the PRD spans tap-01…tap-06 and only tap-02 is built;
rewriting anchors mid-sprint would churn them again on every subsequent plan.

**Trigger to fix:** when tap-06 lands and the PRD is synced as a whole.
