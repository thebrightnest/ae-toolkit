# Mechanical Enforcement over Prose: What Shipped, What Is Still Open

**Date:** 2026-08-12
**Branch:** `fix/mechanical-enforcement-over-prose` (4 commits, unpushed)
**Scope:** items 1–3 of the prose-vs-enforcement review. Item 4 and everything
found while implementing 1–3 are recorded here.

## What shipped

| Commit     | Change                                                                             |
| ---------- | ---------------------------------------------------------------------------------- |
| `01ed6e81` | Ledger verifies content addresses on load; appends instead of rewriting; `verify()` |
| `45e788ef` | `evidence.submit_command` single-sources builder mode; four skills document it      |
| `328f7b2c` | Missing-verdict recovery session; stage prompts derive their submit command         |
| `c0d35b1c` | Corrected a false repair hint and two warnings describing a non-existent mechanism  |

Full suite green (1675 tests), plus `ruff`, `skills-lint`, `validate-skills`,
`plans lint`, `docs lint`, `validate-workflows`, markdownlint.

## Open items, most consequential first

### 1. ADR-055's authoritative ledger is declared, not wired

**ADR-055** (accepted 2026-08-09) decides that settled-ness lives in the
append-only provenance ledger, and that "is it done?" is answered by "the
ledger plus git ancestry — exactly one authoritative store pair, replacing
eight."

`.agents/ledger.jsonl` currently has **five writers and zero readers**:

- Writers: `cli/sprint.py:149`, `cli/aet_state.py:584`, `cli/aet_state.py:735`,
  `cli/gate.py:369`, `cli/ship.py:860`.
- `Ledger.read_events()` has no caller anywhere in `src/aet` — only tests.
- No file under `src/aet/backends/` or `src/aet/projections/` references the
  ledger at all.

The actual settled-ness authority is `_is_settled_from_authority()`
(`cli/init_queue.py:71`), used by `aet queue sync` and `init-queue`. It reads
three things: the settled history log, a merge commit on `origin/main`, and the
**plan footer**. Its docstring says settled-ness is derived "from the ledger or
git ancestry"; the function never touches the ledger. `cli/sync.py:82` carries
the same claim as a comment.

Two consequences:

- The eight-store partition ADR-055 was written to end is still in place — three
  stores answer the question in this one function. The footer path is milder
  than the ADR-034 defect it replaced (the footer is code-written by
  `update_plan_footer`, unlike frontmatter `status`), but it is still a third
  store, and the ADR promised one pair.
- ADR-055's premise — one operator across several machines, laptop invisible to
  the cloud box — is unmet. `.gitignore:15` untracks `.agents/ledger.jsonl*`,
  no backend syncs it, so the store the ADR calls authoritative never leaves the
  machine that wrote it.

This is the same failure class as the two incidents that started the review, at
a larger scale: a decision was recorded, the prose half landed (docstrings and
comments assert the new model), the mechanical half did not, and the ADR reads
as done. **Suggested shape:** either wire the reader and the transport, or amend
ADR-055 to record what was actually built. Leaving the comments asserting an
unbuilt model is the worst of the three.

### 2. The 2026-08-11 "settled tasks disappeared" incident is still undiagnosed

The learning attributed it to hand-editing the ledger. That cannot be the
mechanism: nothing reads the ledger to decide settled-ness (item 1). The
hardening in `01ed6e81` fixed a real data-loss bug in that file — silent line
drops amplified into permanent erasure by rewrite-all — but it did **not** fix
the reported symptom, because the symptom's cause is elsewhere.

Prior learnings point at the likely neighbourhood: `derive_status` rule 1
(`is_ancestor_of_main` on a bare branch) and `cmd_heal`'s trust of that
derivation. **Suggested shape:** a real reproduction before any further fix.
Without one, the next fix will aim at the wrong store again.

### 3. The escalation ladder escalates on the wrong signal (item 4)

`skills/aet-evolve/references/escalation-ladder.md` maps recurrence 1 →
document, 2 → checklist, 3 → review lens, 4 → executable gate. Both recent
learnings sit at recurrence 1, so the prose-only fixes were the ladder working
as designed. The defect is the trigger, not evolve's leniency:

- **Rung should be chosen by check-shape, not incident count.** Whether a
  requirement is mechanically decidable is knowable at the first incident.
  Incident count charges three incidents of tuition for it.
- **The counter undercounts by construction.** Ladder step 1 matches on
  `trigger` keywords, which are artifact names (`.agents/ledger.jsonl`, `manual
  edit`). The ledger learning is the same *class* as the earlier
  work-queue.json hand-edit warning it explicitly cites, but no trigger
  overlaps, so it logged as recurrence 1. Class-keyed matching puts it at rung
  2+ immediately.

This is the ADR-worthy piece: it changes how `aet-evolve` accepts a fix.

### 4. The narrow drift lint

Not "MUST without a referenced gate" — most `MUST`s in the skill corpus are
judgment-shaped, and flagging them all trains suppressions. The enforceable
version is drift detection: **flag prose naming a schema field, CLI flag, or
path that code owns.** Host: `docs_lint.py` with `.agents/doc-rules.yaml`
(ADR-040, documentation invariants as data).

Evidence it works: `scripts/skills-lint` already validates CLI flags mentioned
in skills against the real CLI, and it caught my own draft citing
`aet gate submit --help` — a flag that does not exist. The class this would
catch has at least three instances (omitted `tree_hash` 2026-07-14, hand-rolled
payloads, `--from-pytest` undocumented for months).

### 5. `aet state set-stage` writes the ledger after the queue is already pushed

`cli/aet_state.py:729-735`: `backend.save()` → `backend.push()` → print → then
the ledger event. A raise between them leaves the queue advanced with no
`stage` event; in the `sprint add` path (`cli/sprint.py:144-158`) it also skips
`projections.on_add()` and `backend.close()`. Pre-existing, but corruption is
now a reachable raise, so it is easier to hit. Verified by smoke test: the
command printed `Set stage for smk-01: qa-complete` and *then* refused on the
ledger. Belongs with `docs/prds/single-ledger-closure-prd.md`.

### 6. Two deliberate decisions worth re-taking

- **`aet gate submit` swallows ledger corruption as a warning**
  (`cli/gate.py:388`, `except Exception` → print, exit stays 0). Deliberate per
  ADR-057 ("advisory provenance"), but a *corruption* warning is the silent
  shape being removed. If item 1 is wired, advisory is no longer defensible.
- **Whether an unread store should fail closed.** `01ed6e81` makes a store with
  no readers refuse to open when damaged, justified by ADR-033 §3 and ADR-055's
  intent. If item 1 is abandoned, revisit: a write-only advisory store blocking
  commands is over-strict.

### 7. Follow-through on what shipped

- **Watch the recovery rate.** Query stage telemetry for records with
  `attempt >= 2`. If verdict recovery fires on most runs, the prompt is not the
  problem and the ask should shrink further — e.g. have the qa stage emit its
  own report file so `--from-pytest` has an input by construction.
- **The 7f6cace learning still records the prompt clause as the fix.** Now
  superseded by builder mode plus recovery. Worth a correcting append, as was
  done for the ledger learning.
- **`.agents/learnings.jsonl.lock` is left on disk by `aet learnings append`**
  and is not gitignored (unlike `.agents/ledger.jsonl*`). One line in
  `.gitignore`, or unlink after release.

## Closed — do not reopen

**Deriving the qa verdict from observed test execution.** Foreclosed by
ADR-051: the observed wire stream carries command, timestamps, and exit code
and "never knows how many tests were in the run"; counts exist only on the
claimed record, and counting a claimed record as a passing run "double-counts
the verdict as evidence for itself". ADR-050 makes the wire reader kimi-only,
so under the claude adapter there is no observed stream at all. Synthesizing
the verdict would require the estimation ADR-031 forbids.

The realized alternative was to **shrink the ask, not remove it**: builder mode
reduces the qa payload from 11 schema fields to a verdict, a summary, and four
measured counts. Shipped in `45e788ef`.

## The rule, as it now reads

Prose must never be the sole carrier of a machine-decidable fact, **and must
never restate a fact code owns** — it should name where the fact lives. Two
questions at authoring time:

1. Is this decidable from repo state or command output? → put it on a code path.
2. Does code already own it? → point at it; do not copy it.

Item 1 is the current largest violation, and it is a violation by comment and
docstring rather than by skill prose — which is why the audit should not stop at
`skills/`.
