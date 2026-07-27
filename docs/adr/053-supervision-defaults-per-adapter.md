# Supervision Defaults Live on the CLI Adapter

## Status

Accepted. **Supersedes ADR-031 decision item 2 only** — ADR-031 remains accepted for item 1
(budget is analytics-only) and item 3 (its unifying principle). Preserves ADR-030 (triage
routing) and ADR-048 (two-layer config model). Implemented by the plan set under
`docs/prds/run-invocation-determinism-prd.md`.

## Context

ADR-031 established that stalls are detected by event-silence rather than the clock, and
fixed the watchdog's silence interval at `--stall-timeout`, default 300 seconds, with the
wall-clock `--task-timeout` retained as a coarse backstop above it. The principle was right.
The number was not.

A full pytest suite in this repo goes silent for longer than 300 seconds during the QA stage,
so the watchdog kills a healthy run. The operational workaround was to pass
`--stall-timeout 1800` by hand on every invocation. That workaround is where the real damage
began: because the correct value lived in an operator's memory rather than in code, each AI
coding agent driving `aet run` chose a different value — or none — and varied between
sessions of the same provider. Runs died mid-stage, left dirty sessions, and cost several
recovery exchanges before any work happened.

The value is also not universal. It is a property of the agent CLI being driven: how
frequently that CLI emits output during a long stage is adapter-specific, and the two
supported adapters (`kimi`, `claude`) differ in their output cadence and in where their usage
data appears (`cli_adapter.py:59-77`).

Two homes were available for the corrected value: the config file established by ADR-048, or
the `CLIAdapter` record itself.

## Decision

1. **Supervision defaults are adapter data, not configuration.** `CLIAdapter`
   (`src/aet/cli_adapter.py:17`) carries the stall timeout and wall backstop for each agent
   CLI, and the orchestrator watchdog resolves them from the active adapter. They are not
   keys in `.agents/aet-config.json` or the shadow config.

2. **The stall default is recalibrated per adapter** to exceed the observed silent interval
   of a full test suite, superseding ADR-031's flat 300 seconds. The wall backstop keeps
   ADR-031's role — a coarse ceiling set well above the stall interval — and keeps its
   `--task-timeout` override.

3. **`--stall-timeout` is removed from the `run` / `run-one` surface.** There is no correct
   value an agent can derive at call time, so the choice is not offered. `--cli-bin` remains,
   and selecting the CLI therefore selects its supervision defaults.

## Consequences

- **The QA-stage kill stops recurring** without an operator remembering a magic number.
- **Variance across and within agent providers is removed at the source** — the parameter no
  longer exists at the call site, so there is nothing to choose differently.
- **Config stays about the project; adapters stay about the tool.** ADR-048's two layers
  describe how a *team or a person* wants work integrated (backend, trunk, integration mode).
  How long a given CLI may plausibly stay silent is a fact about that CLI, identical for every
  project using it, and putting it in a per-project file would invite every project to
  rediscover the same value.
- **A new adapter must supply its own timeouts.** This is the intended forcing function: it
  is the moment when someone actually knows the CLI's output cadence.
- **Per-project override is deliberately unavailable.** A project whose suite is slower than
  every adapter default has no config key to raise; it must raise the adapter default or use
  `--task-timeout`. Accepted because the failure is loud, and a config key would restore the
  per-session variance this ADR exists to remove.
- **ADR-031's principle is unchanged.** Sessions still die only on evidence of silence, never
  on an estimate or a stopwatch. Only the calibration and the location of the value change.

## Alternatives Considered

1. **Put the timeouts in the ADR-048 config file.** Rejected. It would work, but it makes a
   property of the *tool* into a property of the *project*, so every project adopting AET
   would have to discover a value that is the same for all of them. It also reopens
   per-session variance the moment the key is writable, and it would couple this work to the
   config-file surface for no gain.

2. **Keep `--stall-timeout` on the command with a better default.** Rejected. A better
   default helps only until an agent decides to pass something else, which is the behavior
   this whole PRD exists to eliminate. Leaving the flag leaves the variance.

3. **Derive the stall timeout dynamically from observed output cadence.** Rejected for now.
   Attractive — a watchdog that adapts to what a stage actually does would need no constant
   at all — but it is a behavior change to the kill path with its own failure modes, and it
   should not ride along with a calibration fix. Revisit once telemetry records per-stage
   silence intervals.

4. **Amend ADR-031 in place.** Rejected. Item 2's original reasoning is sound and worth
   preserving; a superseding ADR keeps the reasoning legible and records that the number, not
   the principle, was wrong.
