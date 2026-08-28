# Bug Report: "verify evidence" has three disagreeing contracts, so the ship gate is unsatisfiable in-band

## Metadata

- **Reported:** 2026-08-28
- **Severity:** high (blocks every `work_class: critical` merge without a manual artefact)
- **Status:** open

## Symptoms

`aet ship merge` refuses a critical-class task:

```
⛔ Pipeline paused at aet-ship.
Workflow stage 'synced' requires aet-verify evidence.
Attach evidence at .agents/verify/<task-id>-evidence.md before shipping.
```

Reported from the consuming repository (`dhl-agentic-tot`, task `pub-03`): once
the task reached `awaiting_merge` there was no legal transition back, and
`aet run-one` printed `✅ Task complete` and did nothing, twice. The evidence had
to be produced out of band by running the `aet-verify` procedure by hand.

## Reproduction Steps

1. Plan a task with `work_class: critical` and no `verify` routing key.
2. Run it through the `software` workflow to `awaiting_merge`.
3. Run `aet ship merge <task-id>`.

Observed: the refusal above, with no in-band command that produces the file it
names.

## Root Cause

Not a missing stage. `verify` is a stage the pipeline walks:
`workflows/software.json` defines `synced → verified` with
`"skills": ["aet-verify"]`, `"evidence": "verify"`, `"gate_key": "verify"`,
`"gate_default": "critical-only"`, and `gate.required_evidence`
(`gate.py:59-83`) resolves it as required when `work_class` is `critical` and the
routing key is absent — matching `plan_parser.required_verdict_kinds`.

The defect is that three components name three different artefacts for that one
evidence kind:

| Component | Artefact |
| --- | --- |
| Workflow / evidence machinery | verdict JSON at `<reports>/<slug>/<task-id>/verify.json` (`evidence.py:92-111`) |
| `aet ship gate` | markdown at `.agents/verify/<task-id>-evidence.md` (`cli/ship.py:527-548`) |
| `aet-verify` skill | `/tmp/aet-reports/<task-id>/evidence/` and the QA report (`skills/aet-verify/SKILL.md:97`, `:113`) |

Nothing writes the path the gate checks. The stage running to completion and
recording a schema-valid passing `verify` verdict does not satisfy the gate,
because the gate never looks at the verdict — it checks `Path.exists()` on a
working-tree file. `skills/aet-ship/SKILL.md:40` documents the gate's path, which
makes the mismatch a documented contract rather than an oversight in one place.

## Consequences

Every critical-class task reaches `awaiting_merge` in a state the gate rejects,
and the only route through is a hand-written file at a path no producer knows
about. The gate is therefore not a check on whether verification happened; it is
a check on whether an operator knew the convention.

`awaiting_merge` having no transition back to `synced` compounds it — the refusal
lands where the pipeline can no longer act on it — but that is a consequence of
the mismatch, not an independent defect: a gate reading the verdict the stage
already wrote would not refuse.

## Fix Direction

Have `aet ship gate` consult `gate.verdict_status(task_id, kind, repo_root)` for
every pair `required_evidence` returns, which is the same derivation the
orchestrator's gate uses and the path the stage actually writes. The `.agents/`
file check then disappears rather than being duplicated.

`aet-verify` writes captured artefacts (screenshots, response bodies, terminal
output) that a JSON verdict does not carry. Those stay where the skill puts them;
the verdict references them. The gate's business is the verdict.

If a working-tree markdown artefact is wanted for review, the skill must write it
and the workflow must declare it — one producer, one consumer, one path.
