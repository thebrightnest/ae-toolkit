# Escalation Ladder

When a learning recurs, escalate its enforcement strength so the same bug class cannot slip through again.

## Stages

| Stage              | Form                                  | How it intercepts                   |
| ------------------ | ------------------------------------- | ----------------------------------- |
| 1. Documentation   | Learning in `.agents/learnings.jsonl` | Agent reads it during preamble      |
| 2. Checklist item  | Step in a command or template         | Agent must tick it during procedure |
| 3. Review lens     | Dedicated check in `aet-review`       | Peer review blocks merge if missed  |
| 4. Executable gate | Script, hook, or automated test       | CI or local tool fails the build    |

## Transition Criteria

| Recurrence     | Action                                                                                                               |
| -------------- | -------------------------------------------------------------------------------------------------------------------- |
| 1st occurrence | Document in `learnings.jsonl` with `trigger`.                                                                        |
| 2nd occurrence | Convert to a **checklist item** in the relevant command or template.                                                 |
| 3rd occurrence | Promote to a **review lens** in `aet-review/SKILL.md`.                                                               |
| 4th occurrence | Implement an **executable gate** (script, pre-commit hook, or test) that fails the build if the pattern is detected. |

## Procedure

1. When a retro identifies a recurring issue, check `.agents/learnings.jsonl` for a matching `trigger`.
2. If found, increment the `recurrence` count on the entry.
3. Based on the new count, move the learning up the ladder:
   - From doc → checklist: add the step, update the entry's `layer` field.
   - From checklist → lens: add the lens, update `layer`.
   - From lens → gate: write the script, update `layer`, add to `make validate` if applicable.
4. Commit the escalation atomically with the retro.
