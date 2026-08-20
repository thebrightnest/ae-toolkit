---
subject: supervision-uniformity
supersedes: [53]
---

# Supervision Values Are Uniform Across Adapters

## Status

Proposed

## Context

ADR-053 calibrated stall_timeout and wall_backstop per adapter because agent CLIs differ in output cadence: kimi streams incrementally, while claude's json-envelope mode emits a single envelope at exit. The per-adapter values prevented the claude stall timer from killing healthy sessions at ~1800 s.

The orchestrator-liveness-and-validation redesign replaces stdout-silence detection with hybrid liveness (process-tree activity + run-log/file writes). With hybrid liveness, the stall timeout is no longer a proxy for output cadence — it is a backstop for true session death. A session with an active process tree or recent run-log writes is alive regardless of which adapter drives it, so the adapter-specific calibration loses its purpose.

Uniform values also remove the per-session variance ADR-053 observed: agents driving `aet run` no longer inherit different ceilings depending on which CLI they select.

## Decision

1. **All CLI adapters use the same stall_timeout and wall_backstop values.** The `CLIAdapter` record keeps the fields for backward compatibility, but the values are identical across adapters.
2. **The values are global constants**, not adapter data. They live in `src/aet/liveness.py` (or equivalent) and are imported by `cli_adapter.py`.
3. **ADR-053 item 2 is superseded.** The principle of adapter-supplied supervision defaults remains for future adapters that genuinely need different values, but the current kimi/claude pair uses uniform values.

## Consequences

- **Simpler reasoning:** operators and agents no longer need to know which adapter is active to predict supervision behavior.
- **No per-session variance:** the ceiling is the same regardless of CLI selection.
- **Claude's json-envelope mode is safe:** hybrid liveness checks process-tree activity, so a claude session emitting only at exit is not killed as long as its process tree is active.
- **Future adapters with genuinely different needs** can still override by adding adapter-specific values back to `CLIAdapter`, but the default is uniform.

## Alternatives Considered

1. **Keep per-adapter values** — rejected: with hybrid liveness, the timeout is a death backstop, not an output-cadence proxy. Different values would reintroduce the variance ADR-053 exists to remove, without the justification that output cadence provides.
2. **Remove the fields from CLIAdapter entirely** — rejected: backward compatibility and future adapter flexibility argue for keeping the record shape, even when values are uniform.
