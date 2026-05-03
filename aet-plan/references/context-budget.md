# Context Budget for aet-plan

## clarify-goal
- **Expected consumption:** 20–60k tokens
- **Strategy:** Free-form conversation is OK. This is the one phase where context accumulation is expected. Stop when shared understanding is clear, not after an arbitrary question count.
- **Clear before:** create-prd if the conversation is >80k tokens

## create-prd
- **Expected consumption:** 10–20k tokens (reads clarify-goal history + template)
- **Strategy:** Summarize clarify-goal conversation before reading if >50k tokens
- **Clear after:** Yes, before create-stories

## create-stories
- **Expected consumption:** 10–15k tokens (reads PRD)
- **Strategy:** PRD should be the only input
- **Clear after:** Yes, before plan

## plan
- **Expected consumption:** 15–30k tokens (reads ticket + PRD section + codebase exploration)
- **Strategy:** Use sub-agents for codebase exploration. Load only relevant files.
- **Clear after:** Yes, before implement. This is the critical handoff.

## Warning Signs of Context Exhaustion

- Agent starts repeating itself
- Agent ignores recently stated requirements
- Agent proposes solutions that contradict the PRD
- Agent forgets constraints mentioned 10 messages ago

**Action:** Clear context immediately and restart with a concise summary.
