---
subject: global-ai-config-and-two-tier-model-routing
relates: [20, 48, 62, 75]
---

# Global AI Configuration and Two-Tier Convention Routing (`fast` / `frontier`)

## Status

Accepted. Amends ADR-020 and ADR-048.

## Context

Previously, `src/aet/cli_adapter.py` hardcoded `"gemini-3.7-flash"` and `--effort high`
inside `CLIAdapter.build_cmd()` for the Antigravity (`agy`) adapter, while `claude` and
`kimi` received no `--model` flag at all, and the `routing` block in
`src/aet/workflows/software.json` (`{"default": {"harness": "claude", "model": null}, "by_stage": {}}`)
was parsed into `Workflow.routing` and never read by the orchestrator.

As a result:

1. Upgrading the AI model used by `aet run` required editing Python source code and
   committing a change to the repository.
2. There was no global user configuration file (`~/.aet/config.json`); personal config
   existed only per-repository at `~/.aet/{slug}/config.json`.
3. Every pipeline stage ran on the same model regardless of task `work_class`
   (`trivial`, `normal`, `critical`) or stage role (mechanical sync vs. adversarial
   review).

## Decision

1. **No Hardcoded Models in Source Code (Fail-Closed Preflight):**
   `src/aet/cli_adapter.py` contains no default model strings or `AET_AGY_MODEL` /
   `AET_AGY_EFFORT` environment variables. Before `aet run` or `aet run-one` spawns
   an orchestrator, `_validate_preflight()` verifies that both `models.fast` and
   `models.frontier` are configured via `require_models_configured()`. When either
   tier is missing, preflight fails closed immediately with remediation instructions:

   ```bash
   aet configure --global --fast-model <model> --frontier-model <model>
   ```

2. **Global User Config (`~/.aet/config.json`) and Personal AI Settings:**
   `user_paths.global_config_path()` resolves `~/.aet/config.json` (overridable via
   `AET_GLOBAL_CONFIG`). AI provider and model tiers resolve external-first across
   personal layers (`AET_WORK_CONFIG` → `~/.aet/{slug}/config.json` →
   `~/.aet/config.json`) and are forbidden in committed `.agents/aet-config.json` so
   personal provider and model choices never leak into version control.

3. **Provider Resolution Precedence:**
   `resolve_cli_adapter()` resolves the active CLI adapter in order:
   1. Explicit `--cli-bin` flag
   2. `AET_CLI_BIN` environment variable
   3. `provider` in resolved user/global config (`~/.aet/config.json`)
   4. `detect_host_adapter()` (the calling client session when nothing is configured)

4. **Two Semantic Model Tiers (`fast` and `frontier`) and Rule A Routing (`work_class` × `stage`):**
   Users configure two model names (`models.fast` and `models.frontier`). The workflow
   definition (`src/aet/workflows/software.json`) maps `work_class` and stage names to
   these two semantic tiers:
   - `trivial`: `fast` across all stages.
   - `normal` / `unclassified`: `fast` for `plan-approved` (`aet-tdd` / `aet-implement`),
     `implemented` (`aet-qa`), `reviewed` (`aet-cso`), and `secure` (`aet-sync-docs`);
     **`frontier` for `qa-complete` (`aet-review`)** so code review always uses deep
     reasoning.
   - `critical`: **`frontier`** for `plan-approved`, `implemented`, `qa-complete`,
     `reviewed` (`aet-cso`), and `synced` (`aet-verify`); `fast` only for mechanical
     `secure` (`aet-sync-docs`).
   - Multi-stage session groups (`run_stage_group`) promote to `frontier` if any
     runnable stage in the group requires `frontier`.
   - Auxiliary sessions (failure `triage` and missing-verdict recovery) always use `fast`.

5. **Opinionated Effort Convention:**
   Reasoning effort is a built-in convention, not a user-configurable setting. When
   `work_class == "critical"`, `Workflow.resolve_effort()` returns `"high"`, and
   adapters that support an effort flag (`agy` via `--effort high`) pass it
   automatically. For `trivial` and `normal` tasks, `--effort` is omitted.

## Consequences

- Upgrading models across all projects is a single command
  (`aet configure --global --fast-model ... --frontier-model ...`) with zero git diff.
- Routine implementation and QA on `normal` tasks stay fast and economical while
  adversarial code review (`qa-complete`) and `critical` work automatically receive
  the `frontier` model (plus `--effort high` on `critical` tasks).
- Misconfigured or unconfigured environments fail immediately at preflight instead of
  silently running an outdated or unintended model.
