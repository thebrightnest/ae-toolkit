# Valid fixture

Run the queue status:

```bash
aet status --queue-file .agents/work-queue.json
```

Inline form: `aet state audit`.

Multiple commands in one block:

```sh
cd repo && aet retro --lookback-days 7
aet ship record-merge t1 docs/plans/t1.md
```

Unlabeled fence:

```
aet run --max-jobs 2 --isolation full
```

Non-shell fences are ignored:

```markdown
`aet bogus-subcommand --nope`
```

Prose mentions of aet-work and orchestrator are not invocations.
