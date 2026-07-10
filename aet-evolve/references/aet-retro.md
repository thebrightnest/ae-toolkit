# aet-retro

One-shot retro generation from telemetry. Run after an `aet-work` batch, a completed plan, or any session where AET tooling misbehaved. Generates a retro that splits findings into:

- **Project-level fixes** — changes to the codebase being built.
- **AET-level fixes** — changes to the toolkit itself (skills, orchestrator, commands, templates).

The script lives at `aet-evolve/bin/aet-retro` and is installed onto `PATH` by `install-aet-binaries` (run via `make install-skills` when developing in this repo).

## When to Run

- End of a multi-task `aet-work run`.
- After manually fixing multiple AET-related issues in one session.
- When you suspect the same AET failure is recurring across projects.

## Steps

1. Ensure `mine-learnings` is on `PATH` (run `make install-skills` if developing in this repo).
2. Run:

   ```bash
   aet-retro
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
- `--no-mine` — skip `mine-learnings` and only use the current project's recent telemetry.

## Expected Output

A retro markdown file with:

- Telemetry summary from `mine-learnings --propose`.
- Project-level findings from the current project's recent per-task telemetry.
- AET-level findings from the current project's recent per-task telemetry.
- Action items for both layers.

It also appends one `learning_candidate` telemetry record per finding, so the next `mine-learnings --propose` run can surface recurring patterns.
