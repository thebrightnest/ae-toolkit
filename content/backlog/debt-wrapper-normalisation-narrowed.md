---
type: debt
status: accepted
recorded: 2026-07-27
source: tap-02-shared-runner-registry
initiative: Telemetry adapter parity (tap-01…tap-06)
trigger: >-
  Telemetry showing those command shapes actually occur in the tracked projects.
depends_on: []
blocks: []
---

# Wrapper normalisation narrowed for `npm run`, `yarn`, `pnpm`

The locked design in `docs/prds/telemetry-adapter-parity-prd.md` unwrapped these
as generic wrappers, so `yarn vitest` would normalise to `vitest`. As built,
only their `test` forms are runner-table entries (`npm run test` → `npm test`,
`yarn test`, `pnpm test`); arbitrary runners are not unwrapped, so `yarn vitest`
and `npm run vitest` do not match and their runs go unrecorded.

**Why accepted:** this is the conservative direction under the plan's own
false-positive-avoidance rule — a missed run costs telemetry volume, a wrong
match records a fabricated one.

**Trigger to fix:** telemetry showing those command shapes actually occur in the
tracked projects. Widening is a small registry change in `src/aet/test_runners.py`.
