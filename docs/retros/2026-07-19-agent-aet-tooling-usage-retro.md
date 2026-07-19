# Retro: Agent AET Tooling Usage Friction (2026-07-19)

## Context

Session started with two queued plans (`pkg-01-decision-records`, `tll-01-first-pass-rework-definitions`) that had been promoted to `queued` after recent intake work. The user asked to run the queue with `aet run`. The agent initially invoked the command in the foreground with the default timeout, which timed out. The user then had to explicitly redirect the agent to run it in the background with a longer timeout. After the batch completed and tasks reached `awaiting_merge`, the user expected to say `aet ship` to create PRs and then `merge PR and verify` to close them; the agent hesitated and required multiple prompts before proceeding. Finally, the user typed `aet evolve`, which is a skill, not an `aet` CLI subcommand, and it failed.

The underlying work completed successfully: both PRs (#140, #141) were merged and the queue was closed. This retro focuses on the avoidable friction in *how* the agent used the AET tooling.

## Retro Debt Check (from 2026-07-09-aet-work-run-self-review.md)

- [x] Add per-task timeout, heartbeat logging, and guaranteed cleanup/summary path to `aet-work/bin/orchestrator` — addressed by `nsr-03`/`nsr-05`/`frh-03` and related orchestrator hardening.
- [x] Make `create_worktree` refresh `origin/main` — addressed by `e6a9037` and related worktree reuse/refetch logic.
- [x] Allow `aet-ship/bin/ship` to close a task from CLI-supplied branch or merge commit — `ship` now accepts `--branch` and `--merge-commit`.
- [x] Add queue self-heal / audit command — `aet state audit` and `aet state heal --apply` are now available.

## What Went Well

- Once directed to background mode, `aet run` completed both tasks through to `awaiting_merge`.
- `make validate` passed after the merges (872 tests).
- The original plan-footer stage bug (`commit_and_push_status` overwriting `*Stage:*` with lifecycle status) was fixed and validated.

## What Went Wrong

### 1. `aet run` was invoked in the foreground with a short default timeout

- **Impact:** The orchestrator run timed out, requiring the user to re-issue the command and explicitly demand background execution.
- **Root cause:** The agent treated `aet run` like any other short CLI command instead of recognizing it as a long-running orchestrator that must run in the background with an explicit long/ disabled timeout. There was no agent-facing command doc describing the correct invocation pattern.
- **Layer:** `.agents/commands/` — missing AET operational usage guide.

### 2. `aet ship` workflow was not recognized from the user's prompts

- **Impact:** The user said `aet ship pkg-01`, `aet ship`, and `aet ship both` but the agent did not immediately execute the standard awaiting-merge workflow (open PR → wait for merge confirmation → run closure). Multiple clarification turns were wasted.
- **Root cause:** The agent did not have a concise operational reference for the `awaiting_merge → ship → merge → verify/close` sequence. The aet-ship skill exists, but there was no local command doc mapping common user utterances to the exact steps.
- **Layer:** `.agents/commands/` — missing AET operational usage guide.

### 3. `aet evolve` was treated as an `aet` CLI subcommand

- **Impact:** The command failed with `error: unknown subcommand 'evolve'`, producing an error the user had to interpret.
- **Root cause:** The agent conflated the `aet-evolve` skill (a meta-skill for retros/system evolution) with the `aet` CLI's subcommand namespace. The CLI has `aet retro` and `aet mine-learnings`; `aet-evolve` is invoked as a skill activation, not a CLI command.
- **Layer:** `.agents/commands/` — missing AET operational usage guide.

## Learnings

- Long-running orchestrator commands need explicit invocation discipline (background + long timeout) captured in a local command doc, not inferred per-session.
- Common AET transitions (`queued → run → awaiting_merge → ship → merged`) should be documented as an operational playbook so the agent recognizes trigger phrases and acts without hesitation.
- Skill names and CLI subcommands live in different namespaces; the agent needs a reference that maps skill activations to their actual CLI entry points.

## Action Items

- [ ] Create `.agents/commands/aet-work.md` with operational rules for `aet run`, `aet ship`, and skill-vs-CLI namespace mapping — owner: agent — due: this session.
- [ ] Append a learning to `.agents/learnings.jsonl` covering the foreground-timeout and ship-workflow gaps — owner: agent — due: this session.
