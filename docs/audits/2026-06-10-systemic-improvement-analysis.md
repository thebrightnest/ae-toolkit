# AE Toolkit Systemic Improvement Analysis

**Date:** 2026-06-10
**Scope:** All 21 skills, all 12 reports in `reports/`, `workflow-audit-2026-06-01.md`, `2026-05-16-aet-toolkit-branch-safety-report.md`, ADRs 001–008, and the in-flight coverage work (`docs/prds/auth-infra-blind-spots-prd.md`, cov-01..04).
**Question:** How can the AE Toolkit become more stable at guiding engineering workflows — systemically, not via framework-specific instructions?

---

## Core Diagnosis

The individual skills are well-designed, and the evolution loop visibly works — every incident produced a retro, and most produced real fixes. But read side by side, almost every failure shares one of two shapes:

1. **Gates verify proxies, not reality.** Lint, typecheck, mocked tests, and "diff matches plan" all passed while the actual system was broken — unstyled UI, un-loginable auth, unparseable uploads, a CSS bug "fixed" four times blind.
2. **Failures happen at the seams, not inside skills.** The auth retro said it perfectly: _"Every aet-\* skill operated correctly within its own scope, but none of them had scope over the auth boundary."_ Routing, handoffs, plan-to-implement transfer, and the learning loop itself are the weak joints.

The reports span at least two different host projects (an Electron/Drizzle app in May, a Laravel/React app in June), and the same failure classes repeat across them. That is the strongest possible argument that fixes belong in the toolkit, not in any project's AGENTS.md.

## Already Fixed — Excluded From Recommendations

Coverage completeness across plan/tdd/qa/review (cov-01..04, merged), merge verification and branch safety (ADR 003), report artifacts to `/tmp/aet-reports/`, terminal mode for step budgets, queue status normalization (`merged`/`abandoned`), worktree cleanup and stale-field repair, the CSS completeness lens (ADR 001), oversized-task gates, and unattended execution mode (ADR 005).

---

## Design Principle: Proportionality Over Universalism

This analysis identifies failure modes in **high-stakes seams** — auth, data models, dependency upgrades, and cross-boundary handoffs. It does **not** propose corporate-level ceremony for every task. The toolkit must stay fluid for normal product work. A 2-line CSS fix that breaks is acceptable cost for a product; a password-hash double-hashing bug is not.

Every recommendation below is governed by **work class**:

| Class        | Examples                                             | Pipeline                             | Live Verification              |
| ------------ | ---------------------------------------------------- | ------------------------------------ | ------------------------------ |
| **Trivial**  | Copy change, color tweak, typo fix                   | Direct edit → ship                   | None beyond diff review        |
| **Normal**   | New field, standard endpoint, simple UI              | Quick plan → implement → auto checks | Fast automated tests only      |
| **Critical** | Auth, data model, infrastructure, dependency upgrade | Full PRD → TDD → QA → review         | `aet-verify` observed evidence |

If a recommendation lacks an explicit work-class trigger, it applies to **all** classes. Where it does, only the named classes pay the cost. The goal is to **catch the six high-severity incidents without burdening the sixty trivial tasks**.

---

## Part 1 — Six Systemic Findings

### Finding 1 — Close the reality gap: require observed evidence of behavior

**Evidence (6 of 12 reports):**

- The CSS truncation bug was declared "fixed" 4 times without ever seeing the render (`reports/2026-05-09-css-chat-truncation-retro.md`)
- The MCP feature passed plan → implement → QA → review → security → merge with zero CSS (`reports/2026-05-14-mcp-css-retro.md`)
- The task-detail modal had 23 passing unit tests with every child mocked while the real app threw on open (`reports/2026-05-25-task-detail-modal-testing-retro.md`)
- The boot-flow "fix" shipped with a race condition unit tests could not see (`reports/2026-05-18-boot-flow-cascade-retro.md`)
- Nobody ever attempted a login before the auth cascade (`reports/2026-06-07-auth-cascade-retro.md`)
- Nobody ever uploaded a document before the upload cascade (`reports/2026-06-07-document-upload-cascade-retro.md`)

The new coverage gates help but do not close this: a mocked-to-death test satisfies "every file has a test" while proving nothing — the task-modal incident is exactly that.

**Mechanisms (all framework-agnostic):**

- **Conditional live verification triggered by work class.** `aet-verify` is not a universal pipeline stage. Trivial and normal tasks rely on fast automated checks. Critical tasks (auth, data, infrastructure, upgrades) require at least one _observable check_: the command to run, the action to take, and the expected observation (e.g., "`make dev`, open settings tab, form renders styled"; "`curl -X POST /login` returns 200 and a session cookie"). `aet-qa` executes it and captures the evidence; `aet-ship` checks that evidence exists for the task's declared class. Today browser testing in `aet-qa` is optional ("if Playwright configured") and nothing requires critical features to have ever _run_. The boot-flow retro asked for this hard gate — but only for critical work.
- **A mock-boundary policy in `aet-tdd`/`aet-review`.** The task-modal learning is a universal testing principle: _mock at system boundaries (network, external services); render/execute first-party code for real._ Make "test mocks a first-party module" a review flag. This is a lens, not a gate — low overhead, applies to all classes.
- **Gate calibration ("does the gate bite?").** The `await`-in-callback report (`reports/2026-05-04-await-in-non-async-callback.md`) is the purest case: `tsc --noEmit` passed because project references made it check nothing. Once per project, `aet-setup` (or first `aet-prime`) should plant a trivial error, confirm each validation command actually fails, revert, and record the authoritative commands. A gate that cannot fail is decoration — and the toolkit currently trusts every gate untested.

### Finding 2 — Validate the foundation, not just the diff

**Evidence:** All 37 plans in the Laravel project built on top of auth that was never set up — no sessions table, double-hashed factory passwords, drifted Sanctum domains. The upload cascade included a queue worker declared in the Procfile but absent from `make dev`. Every skill is deliberately diff-focused (`aet-cso`: "only review what changed"), so the substrate is _nobody's_ job.

**Mechanism: a foundation contract, checked at session start.** Each project declares its critical flows as a handful of executable smoke checks (login works, app boots, primary entity CRUDs, declared dev services respond) — scaffolded by `aet-setup`, stored as e.g. `make smoke` or `.agents/smoke/`. Run **once per session** when context loads (via `aet-prime` or the triage front door), and **after** critical work that touches infrastructure. This is not a per-task gate; it is a floor-check that prevents building on broken substrate for the day's work. It also gives dev-topology drift (ports, workers, env) an owner, because the smoke check exercises the real topology.

For critical work, run smoke **before and after** the change. For normal work, the session-level check is sufficient — if the floor was solid when you started, a standard change is unlikely to break the foundation. This avoids making `make smoke` overhead on every trivial task.

### Finding 3 — Make the learning loop ratchet instead of leak

`aet-evolve` is called "the highest-leverage long-term skill," and its current design under-delivers on that claim:

- **Lessons do not cross projects.** Error-swallowing was retroed and "fixed" in the Electron project on May 11 (`reports/2026-05-11-s1-t2-t4-session-persistence.md`, B4) — and bit the Laravel project twice on June 7. Project-local `learnings.jsonl` structurally cannot prevent that; only toolkit changes do. The branch-safety report's section 5 already articulated this argument — generalize it into a standing channel: a `reports/` convention plus a periodic `aet-evolve --toolkit` pass that mines project retros for toolkit-level patterns.
- **Action items do not close.** The upload retro has 3 unchecked items, login-password 2, model-404 1. No skill ever looks back at them. `aet-evolve retro` should start with a "retro debt" check: previous action items are either verified done, converted to queue tasks, or explicitly dropped.
- **No escalation on recurrence.** The model-404 fix had been "applied twice before and kept regressing" (`reports/2026-06-08-ai-model-404-cascade-retro.md`). When a new incident matches an existing learning, the response must move _up the enforcement ladder_: documentation → checklist item → review lens → executable gate. Docs demonstrably do not prevent recurrence; the toolkit's own history proves only gates do. Encode that ladder in `aet-evolve`.
- **Retrieval is undefined.** Every preamble says "top-3 relevant entries from learnings.jsonl" with no mechanism for relevance. Add a `trigger` field to the learning schema ("when touching test factories", "when writing catch blocks") so matching is operational rather than vibes.

### Finding 4 — De-throne the plan as a single point of failure

**Evidence:** The FK existed in plan prose but not in the plan's code block — the implement agent followed the code block (`reports/2026-05-11-s1-t1-session-schema.md`). The wrong session ID was in the code block — followed verbatim into a silent-data-loss bug (s1-t2). CSS was absent from the plan — so implement did not write it and review's "Completeness vs plan" lens passed broken work (mcp-css). Plans inherit total authority but get no internal consistency check, and downstream gates cannot see what plans omit.

**Mechanisms:**

- **Plan self-consistency lint** at plan completion or `aet-validate-scope`: every constraint stated in prose appears in the code blocks; every file in "files to modify" appears in a task; every acceptance criterion is an _observable behavior_, not a task restatement. Cheap, mechanical, catches the whole s1-t1/s1-t2 class.
- **Implement reconciles instead of obeying.** `aet-implement` should treat prose and code blocks as two witnesses: where they disagree, stop and flag — never silently follow the code block.
- **Completeness = behavior delivered, not tasks ticked.** Review's Completeness lens should verify against the story's acceptance criteria with the question "if I exercised this as the user, what would I see?" — that question catches missing CSS, missing endpoints, and missing error states even when the plan never mentioned them.

### Finding 5 — Fix the seams: routing, proportionality, composition integrity

- **Routing:** the boot-flow disaster (2-line bug → 1,165-line rewrite with 3 new bugs) was a _routing_ failure — a bug entered the feature pipeline. `aet-bug-report` redirects features to `aet-plan`, but the reverse gate does not exist: `aet-plan`/`aet-pipeline-plan` happily accept reproducible defects. Add the symmetric redirect, and an intake triage question ("demonstrable misbehavior of existing code → bug path") to every entry-point skill.
- **Proportionality budget:** task sizing exists for planning (dual-limit model) but nothing equivalent governs fixes. Give `aet-bug-report` a diff budget: a fix exceeding ~3 files / ~100 lines requires explicitly justifying why the minimal fix is insufficient — before writing it, not in retro.
- **Composition contradictions** (found by reading the skills against each other):

  - `aet-pipeline-implement` Step 1/2 ("aet-tdd: write all failing tests" → "aet-implement: write code to satisfy them") **institutionalizes the exact horizontal-slicing anti-pattern `aet-tdd`'s own SKILL.md forbids in bold** ("DO NOT write all tests first, then all implementation"). `aet-tdd`'s completion protocol ("Next step: run `aet-implement` to write code that satisfies these tests") has the same contradiction.
  - README's canonical order says **Implement → Review → QA**; the pipeline and the skills' completion protocols implement **QA → Review**.
  - `aet-plan` and `aet-pipeline-plan` declare _identical_ triggers ("plan this feature," "help me design") — ambiguous routing by design.
  - The Shared Preamble is copy-pasted into ~15 skills and has already drifted (some have stage fields, some do not).

  **Mechanism:** make composition mechanically checkable in this repo. Write the canonical stage state machine in one doc (`docs/PIPELINE.md`), then extend `scripts/validate-skills.sh` to verify: completion-protocol "next step" pointers form a consistent graph with it; no two skills share a trigger phrase; preamble blocks match the canonical template. The validator infrastructure already exists — point it at the seams.

### Finding 6 — Mechanize state; de-bias review

- **Deterministic operations should be scripts; judgment should be prompts.** The workflow audit's 10 issues (stale `worktree` fields, invented statuses, done-without-merge, artifacts staged) all trace to agents maintaining a three-headed state store (plan footers + PRD footers + queue JSON) by following prose. Scripts already ship where it matters (`release-prep.sh`, `orchestrator-template.sh`) — extend the precedent: a small `aet-state` helper that owns queue mutations and stage transitions, validates legality (cannot set `merged` without running the ancestry check itself), and updates footers and queue atomically. This also saves agent steps, which directly mitigates the step-limit failures.

  **Use Python (standard library only) for deterministic workflow scripts.** The repo currently declares itself "Markdown-only" with no `package.json` or `requirements.txt`. That constraint made sense when the toolkit was only skill files and bash wrappers. It no longer fits the infrastructure layer: derived status computation needs git history walking and JSON parsing; tracker adapters need HTTP auth and pagination; the skill build system needs template assembly and graph validation. Python 3 with only the standard library (`json`, `pathlib`, `subprocess`, `argparse`, `dataclasses`) covers 90% of this without introducing `node_modules` or `venv`. Keep shell/Make for simple orchestration (`make package`, `make lint`); graduate to Python when a script needs structured data, error handling, or cross-platform portability.

  **Graduated approach:** (1) Start with `aet-state` — greenfield, highest leverage. (2) Migrate `validate-skills.sh` when building the shared-source assembly system (it needs YAML parsing and link resolution). (3) Leave `make package` and formatting commands as shell — they don't need a real language.

- **Reviewer independence.** The toolkit's founding insight is "plans and code never share a context window; bias can't leak" — yet inside `aet-pipeline-implement`, the same context that wrote the code reviews it, QAs it, and security-audits it. Apply the same principle: the review step must work from disk artifacts only (diff + plan), ideally in a fresh subagent/session, never from the implementing conversation's memory. The s1-t2 report shows review catching 4 blockers when it has real distance; give it that distance structurally.

---

## Part 2 — Structural Changes: Add, Remove, Repurpose

### New skills to add

**`aet-verify` — conditional live verification and evidence capture.**
Not a universal pipeline stage; triggered by work class. One skill, three consumers:

- **Foundation mode** (session start, critical work): run the project's declared smoke checks — login works, app boots, dev services respond. Would have stopped the auth cascade before plan #1 of 37 was built on broken auth. Runs once per session for everyone; before/after for critical work only.
- **Feature mode** (critical work only): exercise the changed flow in the _running_ system — start the app, hit the endpoint, open the screen — and capture evidence (output, HTTP response, screenshot) into the QA report. Normal tasks skip this; their verification is fast automated tests.
- **Reproduction mode**: `aet-bug-report` Step 1 ("Reproduce") is the same capability with no shared procedure today.

ADR 001 rejected new skills for completeness _checks_, and that was right — but this is not a lens; it is a harness with its own procedure and tooling that three skills need. It also resolves a dangling reference: `aet-ship`'s principles mention a "canary" post-deploy step that no skill implements. Fold that in (run smoke on main after merge).

**`aet-upgrade` — dependency and framework upgrades as a first-class work type.**
Two of the worst June incidents were Laravel 11 breaking changes (the `hashed` cast double-hashing; the `storage/app/private` path move) that no skill could have owned: upgrades are not a feature (no PRD makes sense) and not a bug (nothing was "broken" yet). The upload retro explicitly asked for a breaking-changes checklist. The mechanism is framework-agnostic: fetch the upgrade guide/changelog for the bumped dependency, enumerate breaking changes, grep the codebase for each affected pattern, produce a risk-mapped plan, run foundation smoke before/after. Today this work type silently falls through the toolkit's routing.

**`spike` — a command inside `aet-plan`, not a new skill.**
The planning lockout is correct but currently absolute, and the s1-t1 retro shows the cost: the Drizzle snake*case behavior and the TTY-requiring command were discoverable only by \_running something*, so the plan shipped wrong and the implement agent paid for it. Sanction a time-boxed, throwaway experiment: separate worktree, hard time/scope box, output is a findings note that feeds the plan, code is deleted. De-risks plans without violating the lockout's purpose (preventing premature implementation, not preventing learning).

### Skills to fold away or repurpose

- **`aet-validate-ui` → merge into `aet-validate-scope`** (or into the plan-consistency lint). The weakest skill — keyword matching against seven categories, optional in the pipeline, and the MCP-CSS incident happened _with it in the stack_ because it validates plan prose, not outputs. Its checklist is genuinely useful as a lens; it does not carry its weight as a standalone skill with its own trigger surface.
- **`aet-prime` → repurpose as the triage front door (`aet-start`, or keep the name).** Its current 65 lines are mostly duplicated by the Shared Preamble every skill already runs. Repurpose it to: load context, classify the request into work class (trivial / normal / critical), and route — reproducible defect → `aet-bug-report`; capability → `aet-plan`; dependency bump → `aet-upgrade`; trivial chore → direct edit with minimal ceremony. The boot-flow disaster was a routing failure, and routing needs an owner. This is the first priority because it makes every subsequent gate proportionate.
- **Keep:** `aet-cso` (hard-fail security gating semantics justify separation from review), `aet-discover`, `aet-extract-stack`, both pipelines (but thin them — see below).

### Should `aet-work` use GitHub instead of `work-queue.json`? No — but fix what the question points at

The instinct is right because the queue's core failure mode is that **status is asserted, not derived** — the queue said `merge-verified` while git said otherwise (P3-REM, branch-safety incident, 39 stale worktree fields). And GitHub would genuinely solve one piece: a PR with `closes #N` closes the issue _only when the merge lands on the default branch_ — a mechanized version of the merge-verification invariant the toolkit has spent three ADRs hand-rolling.

But forcing GitHub breaks things the toolkit explicitly stands for:

- **Agent- and infra-agnosticism** is a stated core value (works via paste-into-chat; the Decision Log rejects CI specifically to stay "portable and free of vendor lock-in"). Forcing GitHub excludes GitLab teams, air-gapped work, and local-only solo projects — the heaviest current use case.
- The **DAG** (`blocked_by`/`blocks`) is first-class in the queue; GitHub has no good native blocking semantics, and Projects v2 custom fields via API are clunky for the metadata stored (`worktree`, `merge_commit`, `plan_file`, `oversized`).
- The AFK night-shift loop would take on auth, rate limits, and network as new failure modes in exactly the unattended context where they are least affordable.

**Do instead:**

1. **Make status derived from ground truth, not stored.** Almost every status is computable: plan file exists → planned; branch exists → in-progress; `git merge-base --is-ancestor` → merged; worktree dir present → has worktree. Have the `aet-state` helper script (Finding 6) _recompute_ these on every read. The JSON then only stores what is genuinely declarative — the DAG and `abandoned` + reason — and drift becomes structurally impossible rather than detected after the fact by `drift-check`.
2. **Tracker as an adapter, not a backend.** Keep `publish-issues` as a one-way mirror by default, and offer an optional `tracker: github` adapter behind the same `status`/`next`/`sync` commands for GitHub-native teams who want auto-close-on-merge and human visibility. Local-first stays the default; GitHub becomes a choice, not a dependency.

### Repo-level structural changes

**Build skills from shared source instead of hand-maintaining 21 copies.** The deepest structural issue. The Shared Preamble is pasted into ~15 skills and has already drifted; the stage graph lives in three places (README, pipeline skills, each skill's completion protocol) and they already contradict each other. The repo already treats skills as build artifacts (`make package` produces `.skill` zips) — extend the build one level: shared partials (preamble, guardrail blocks, stage table) assembled into self-contained SKILL.md files at build time, plus validator checks that next-step pointers form a consistent graph and no two skills claim the same trigger phrase. One edit instead of 21, and composition contradictions become build failures.

**Introduce explicit work classes with proportionate pipelines.** See the Design Principle above. Structurally, the toolkit has one weight class: the full ceremony. Bugs got an escape hatch (`aet-bug-report`); chores, config changes, small refactors, and upgrades have none — so they either get over-processed (boot-flow) or bypass the system entirely (which is how unmerged-branch and release-bump-on-feature-branch messes happen). A small routing table — trivial / normal / critical, each mapping to a defined skill sequence and gate set — turns proportionality from a judgment call into structure. This is what the triage front door routes _into_.

**Formalize the cross-project feedback channel.** The reports prove lessons do not cross projects (error-swallowing: learned in the Electron project in May, bit the Laravel project twice in June). Make `reports/` a defined interface: downstream projects' `aet-evolve` writes toolkit-relevant retros in a standard format, and a periodic `aet-evolve --toolkit` pass over them does systematically what this analysis did manually.

**Upgrade scripting infrastructure from bash to Python (standard library only).** The "Markdown-only repo" constraint served the toolkit well when it was just skill files and Make wrappers. The infrastructure layer has outgrown it: `aet-state` needs JSON parsing and state-machine validation; derived status needs git history walking; tracker adapters need HTTP handling; the build system needs template assembly. Python 3 with the standard library covers this without `node_modules` or `requirements.txt`. Keep shell/Make for simple orchestration; use Python when a script needs structured data, error handling, or cross-platform portability.

**Net result:** 21 skills → ~21 (drop `aet-validate-ui`, add `aet-verify` and `aet-upgrade`), but with a front door, a build system, derived state, proportionate pipelines, a defined feedback interface, and deterministic workflow scripts — the difference between a collection of good skills and a stable system.

---

## Priorities

If only three things get done:

1. **Work-class routing with proportionate pipelines** — the prerequisite that makes every other recommendation affordable. Without this, live verification and smoke checks become universal overhead on every task. This is the difference between a stable system and a bureaucratic one.
2. **The learning ratchet** (Finding 3) — zero per-task overhead, highest long-term leverage. Lessons that escalate from docs → checklist → review lens → executable gate, and propagate across projects into the toolkit.
3. **Conditional live verification** (Finding 1 / `aet-verify`) — applied only to critical work, preventing the six high-severity incidents without burdening normal tasks. Requires work-class routing to be in place first.

## Suggested Next Step

Build the triage front door (`aet-prime` repurposed) and work-class routing table first. This is the foundation that makes `aet-verify` and foundation smoke proportionate rather than universal. Then run the remaining findings through the toolkit's own pipeline — one PRD per finding, the same way `docs/prds/auth-infra-blind-spots-prd.md` was built from the June retros.

---

_Source analysis: Claude session 2026-06-10, covering all SKILL.md files, all `reports/*.md`, `workflow-audit-2026-06-01.md`, `2026-05-16-aet-toolkit-branch-safety-report.md`, and ADRs 001–008._
