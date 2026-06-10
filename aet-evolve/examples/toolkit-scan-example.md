# Example: aet-evolve --toolkit Output

This example shows the output of running `aet-evolve --toolkit` against a project with three toolkit-relevant retros.

## Input Retros

### retro-2026-05-11.md

```yaml
---
date: 2026-05-11
toolkit-relevant: true
---
```

**Problem:** Agent swallowed an error in a catch block and continued with undefined state.
**Root cause:** No rule in AGENTS.md requiring catch blocks to either re-throw or log explicitly.
**Fix:** Added explicit error-logging step in the affected service.
**Prevents:** An AGENTS.md rule: "Every catch block must either re-throw or write to a structured log."

### retro-2026-06-07a.md

```yaml
---
date: 2026-06-07
toolkit-relevant: true
---
```

**Problem:** Same error-swallowing pattern recurred in a different file.
**Root cause:** The previous retro's fix was project-local; the toolkit rule was never added.
**Fix:** Added local linter rule.
**Prevents:** Toolkit-level AGENTS.md rule + `aet-review` lens for catch-block completeness.

### retro-2026-06-07b.md

```yaml
---
date: 2026-06-07
toolkit-relevant: true
---
```

**Problem:** Agent used a mock of an internal collaborator instead of the real module.
**Root cause:** `aet-tdd` tracer bullet section does not explicitly ban internal mocks.
**Fix:** Replaced mock with real module in test.
**Prevents:** Add "no internal mocks" check to `aet-tdd` checklist.

## --toolkit Output

```
=== Toolkit Pattern Mining Report ===
Scanned: 3 toolkit-relevant retros
Patterns found: 2

--- Pattern A: Error Swallowing (2 occurrences) ---
Root-cause layer: AGENTS.md (missing rule)
Prevention type:   Global rule + review lens
Recurrence count:  2 (escalates at 3)

Proposed toolkit change:
  File: AGENTS.md
  Add: "Every catch block must either re-throw or write to a structured log."

Recommended gate:
  Add a "Catch Blocks" lens to aet-review that flags empty or silently-swallowing catch blocks.

Status: Ready for implementation

--- Pattern B: Internal Mock Abuse (1 occurrence) ---
Root-cause layer: aet-tdd skill (missing checklist item)
Prevention type:   Command checklist update
Recurrence count:  1

Proposed toolkit change:
  File: aet-tdd/SKILL.md
  Add: "[ ] No mocks of internal collaborators — only external boundaries" to Checklist Per Cycle

Recommended gate:
  None yet (insufficient recurrence). Monitor for second occurrence.

Status: Document and monitor

=== Summary ===
- 1 pattern ready for toolkit implementation
- 1 pattern queued for monitoring
- Next --toolkit run recommended after 2 more retros or in 30 days
```
