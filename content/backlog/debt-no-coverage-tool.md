---
type: debt
status: accepted
recorded: 2026-07-27
source: tap-02-shared-runner-registry
trigger: >-
  Any plan that wants a coverage threshold as a gate, or the next time a QA stage has to hand-roll `trace` to answer the coverage question.
depends_on: []
blocks: []
---

# No coverage tool is configured

`pyproject.toml` declares no `coverage` or `pytest-cov` dependency, and the
`.coverage` file at the repo root is stale. The aet-qa stage requires a
coverage check on new modules, so it fell back to the standard-library `trace`
module to prove `src/aet/test_runners.py` was exercised (77/77 lines, 0 missed).

That fallback works but is per-run, per-file, and manual — it produces no
project-wide number and no regression signal.

**Why accepted:** the QA skill's own instruction is to flag a missing coverage
tool as a setup gap rather than silently skip the check, which is what happened.
The gap predates tap-02 and is out of that plan's scope.

**Trigger to fix:** any plan that wants a coverage threshold as a gate, or the
next time a QA stage has to hand-roll `trace` to answer the coverage question.
