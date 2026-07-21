# Placeholder fixture

Opaque tokens pass as values without further checks:

```bash
aet ship <task-id> <plan-file>
aet state transition $TASK_ID planned in-progress --reason "..."
aet state <subcommand>
aet gate review --plans-dir $(pwd)/docs/plans
aet retro --lookback-days ${DAYS}
```
