---
type: debt
status: accepted
recorded: 2026-08-28
source: docs/bugs/20260828-fetch-discards-unpushed-record-writes.md
trigger: >-
  A third writer, or a field whose write needs validation the CLI already performs.
depends_on: []
blocks: []
---

# The orchestrator writes task records directly instead of through `aet state`

ADR-055 and `_record_stage`'s docstring both describe `aet state` as the sole
writer of a task record. The orchestrator is a second writer at eight sites
(failure signatures, gap analysis, integration failure, merge commit, delivered
size, three cost roll-ups). They are correct now — each replicates — but the
single-writer rule the fetch refspec assumes is still not true.

**Why accepted:** routing them through `aet state` needs CLI surface for each
field, which is a larger change than the defect required, and the helper makes
the current arrangement honest.

**Trigger to fix:** a third writer, or a field whose write needs validation the
CLI already performs.
