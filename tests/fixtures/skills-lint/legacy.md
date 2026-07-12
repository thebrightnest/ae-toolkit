# Legacy fixture

```bash
aet-work run --max-jobs 2
./aet-work/bin/orchestrator --queue-file .agents/work-queue.json
aet-state audit
```

Bootstrap of the binary itself is validated as an `aet` invocation:

```bash
./aet-work/bin/aet status --queue-file .agents/work-queue.json
```
