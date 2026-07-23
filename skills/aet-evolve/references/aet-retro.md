# aet-retro

One-shot retro generation from telemetry. Run after an `aet run` batch, a completed plan, or any session where AET tooling misbehaved. Generates a retro that splits findings into:

- **Project-level fixes** — changes to the codebase being built.
- **AET-level fixes** — changes to the toolkit itself (skills, orchestrator, commands, templates).

Run `aet retro`; `aet setup link` puts the `aet` dispatcher on `PATH` (run via `make install-skills` when developing in this repo).

## When to Run

- End of a multi-task `aet run`.
- After manually fixing multiple AET-related issues in one session.
- When you suspect the same AET failure is recurring across projects.

## Steps

1. Ensure `aet mine-learnings` is on `PATH` (run `make install-skills` if developing in this repo).
2. Run:

   ```bash
   aet retro
   ```

3. The command writes `docs/retros/YYYY-MM-DD-aet-retro.md`.
4. Review the split between project-level and AET-level findings.
5. For AET-level findings, run `aet-evolve system-evolve` and append a learning to `.agents/learnings.jsonl`.
6. For project-level findings, create or queue fixes in the current project.

## Options

- `--archive-dir PATH` — use a custom telemetry archive root (default: `~/.aet/telemetry`).
- `--project-slug SLUG` — override the project slug (default: derived from git origin or cwd).
- `--lookback-days N` — days of per-task telemetry to read for the current project (default: 7).
- `--output PATH` — write the retro to a specific file.
- `--no-mine` — skip `aet mine-learnings` and only use the current project's recent telemetry.

## Metrics Evidence Step

Before running `aet retro`, gather quantitative context with `aet metrics`:

```bash
aet metrics --json
```

- `--json` — print the machine-readable projection (first-pass rate, rework count, cost per merged task) instead of the human report.
- `--since YYYY-MM-DD` — only include tasks settled on or after this date. Use the date of the most recent `docs/retros/YYYY-MM-DD-aet-retro.md` to scope the metrics window to new work.

Cite the returned values when proposing skill or workflow edits. Metrics are advisory only; they inform but do not trigger automatic changes.

## Expected Output

A retro markdown file with:

- Telemetry summary from `aet mine-learnings --propose`.
- Project-level findings from the current project's recent per-task telemetry.
- AET-level findings from the current project's recent per-task telemetry.
- Action items for both layers.

It also appends one `learning_candidate` telemetry record per finding, so the next `aet mine-learnings --propose` run can surface recurring patterns.
