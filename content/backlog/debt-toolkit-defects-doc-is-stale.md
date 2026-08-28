---
type: debt
status: accepted
recorded: 2026-08-28
source: docs/retros/2026-08-28-aet-run-retro.md
trigger: >-
  The next operator session that follows the checklist, or the next release that changes any path it names.
depends_on: []
blocks: []
---

# `aet-toolkit-defects.md` describes a 1.8.0 tree

The root-level `aet-toolkit-defects.md` is the document an operator loads before
`aet run`. It was written on 2026-08-12 against ae-toolkit 1.8.0 in a consuming
project, and its line numbers, several statuses, and its operating checklist have
drifted. D3 (`_record_stage` no-ops under `git-refs`) is fixed in the current
source — `_record_stage` resolves the task ref and routes through
`aet state set-stage` — and the checklist predates the 2026-08-28 fixes.

**Why accepted:** re-verifying thirteen items against the current tree is its own
task, and each one wrongly marked open is a false alarm rather than a hazard.

**Trigger to fix:** the next operator session that follows the checklist, or the
next release that changes any path it names.
