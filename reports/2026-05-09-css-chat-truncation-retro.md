# Retrospective: Chat UI Message Truncation Bug

**Date:** 2026-05-09
**Participants:** Agent (Kimi Code CLI), User (Pedro Rocha)
**Trigger:** Post-incident — agent made 4 failed attempts to fix a CSS truncation bug

## What Went Well

- The user provided a precise, reproducible observation: "removing `flex items-start gap-3` from the message row fixes the width"
- Agent eventually pivoted from flexbox to grid layout based on this observation
- Typecheck and lint passed on all attempts

## What Didn't Go Well

- **4 attempts without validation:** The agent applied CSS changes (min-w-0 → block w-fit → grid) and declared each "fixed" without any way to verify the rendered result
- **Flying blind on computed styles:** The agent never asked for the computed width, `overflow` status, or actual DOM structure of the truncated element before guessing at fixes
- **Theory-driven debugging:** The agent spent thousands of tokens on CSS spec analysis instead of asking "what is the computed width of `.prose` inside the bubble?"
- **User frustration:** The user had to correct the agent 3 times and explicitly asked "How can you improve your own validation?"

## Root Causes

| Issue                                            | Root Cause                                                                        | Recurrence Risk           |
| ------------------------------------------------ | --------------------------------------------------------------------------------- | ------------------------- |
| Agent declared fixes without visual verification | No process for validating visual/UI bugs when the agent cannot render the browser | High — any CSS/layout bug |
| Agent guessed at CSS fixes                       | No reference doc for CSS debugging workflow; agent relied on theoretical analysis | High — any layout bug     |
| Agent didn't ask for computed styles             | AGENTS.md has no rule requiring diagnostic data collection before UI fixes        | Medium — any visual bug   |

## Action Items

| Action                                                                                       | Owner | Due        | Status      |
| -------------------------------------------------------------------------------------------- | ----- | ---------- | ----------- |
| Create `.agents/reference/css-debugging.md` with a diagnostic checklist                      | Agent | 2026-05-09 | In progress |
| Add AGENTS.md rule: "For visual/layout bugs, collect computed styles before proposing fixes" | Agent | 2026-05-09 | In progress |
| Log learning to `.agents/learnings.jsonl`                                                    | Agent | 2026-05-09 | In progress |

## Learnings to Capture

> Added to `.agents/learnings.jsonl`:

```json
{
  "date": "2026-05-09",
  "category": "process",
  "summary": "For visual/layout bugs, collect computed styles before guessing at fixes",
  "detail": "When a UI element renders incorrectly (truncation, overflow, misalignment), the agent cannot see the rendered result. The agent must ask the user to share computed width/height, overflow status, and containing block dimensions from browser dev tools BEFORE proposing any CSS changes. Theory-driven CSS debugging without computed styles leads to 'fix and hope' loops that frustrate users."
}
```
