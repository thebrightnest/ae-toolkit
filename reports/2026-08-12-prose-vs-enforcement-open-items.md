# Mechanical Enforcement over Prose: What Shipped, What Is Still Open

**Date:** 2026-08-12
**Branch:** `fix/mechanical-enforcement-over-prose` (5 commits, unpushed)
**Scope:** items 1–3 of the prose-vs-enforcement review, plus everything found
while implementing them. Items 4–5 below were surfaced by a parallel session
investigating a downstream AET project's halt loop and re-verified here; where
that session's framing was off, the correction is noted.

## What shipped

| Commit     | Change                                                                              |
| ---------- | ----------------------------------------------------------------------------------- |
| `01ed6e81` | Ledger verifies content addresses on load; appends instead of rewriting; `verify()`  |
| `45e788ef` | `evidence.submit_command` single-sources builder mode; four skills document it       |
| `328f7b2c` | Missing-verdict recovery session; stage prompts derive their submit command          |
| `c0d35b1c` | Corrected a false repair hint and two warnings describing a non-existent mechanism   |

Full suite green (1675 tests), plus `ruff`, `skills-lint`, `validate-skills`,
`plans lint`, `docs lint`, `validate-workflows`, markdownlint.

## Open items, most consequential first

### 1. ADR-055's authoritative ledger is declared, not wired

**ADR-055** (accepted 2026-08-09) decides that settled-ness lives in the
append-only provenance ledger, and that "is it done?" is answered by "the
ledger plus git ancestry — exactly one authoritative store pair, replacing
eight." Decision 4 adds: "Queue and ledger travel with the repo as pushed git
refs … `refs/aet/*` lives inside the repository, **outside the working tree,
invisible to every PR diff**."

`.agents/ledger.jsonl` currently has **five writers and zero readers**:

- Writers: `cli/sprint.py:149`, `cli/aet_state.py:584`, `cli/aet_state.py:735`,
  `cli/gate.py:369`, `cli/ship.py:860`.
- `Ledger.read_events()` has no caller anywhere in `src/aet` — only tests.
- No file under `src/aet/backends/` or `src/aet/projections/` references the
  ledger at all. `git_refs_backend.py` manages `refs/aet/tasks/*` and
  `refs/aet/meta/queue`; it has no ledger handling, so **no backend
  configuration moves the ledger out of the working tree.**

The actual settled-ness authority is `_is_settled_from_authority()`
(`cli/init_queue.py:71`), used by `aet queue sync` and `init-queue`. It reads
three things: the settled history log, a merge commit on `origin/main`, and the
**plan footer**. Its docstring says settled-ness is derived "from the ledger or
git ancestry"; the function never touches the ledger. `cli/sync.py:82` carries
the same claim as a comment.

Prose asserting the unbuilt behaviour as fact, beyond those two:

- `docs/CONVENTIONS.md:388` — "Queue and ledger state travel with the repo via
  `refs/aet/*` on origin."
- `docs/WORKFLOW-github.md:23` — "fetch refs/aet/\* → queue derived from
  ledger." Doubly false: the ledger is not refs-borne, and nothing derives the
  queue from it.
- `git_refs_backend.py:13` — "Nothing here pushes `refs/aet/*`: the backend is
  local-only by default", so even the *queue* half of decision 4 is conditional
  on configuration.

Neither authoritative store travels. `.agents/work-history.jsonl` — the store
that actually answers "is it done?" — is itself in `AET_IGNORED_PATHS`, i.e.
gitignored and machine-local. ADR-055's premise (one operator across several
machines, laptop invisible to the cloud box) is unmet on both halves.

**Why it went unnoticed: "ledger" names two different stores.** There is the
git-refs store — what `breaker.py:6` means by "rides the existing git-refs
ledger" (`BREAKER_REF = "refs/aet/breaker"`, `breaker.py:21`, written directly
via git, bypassing the backend class), and what ADR-030 means. And there is the
content-addressed event ledger — `aet.ledger.Ledger`, the JSONL defined by
ADR-055 §1–3. Decision 4, read in the context of §1–3, plainly means the
second; the implementation only ever delivered the first. Anyone reading the
ADR or the docs would reasonably conclude the ledger is refs-borne.

**Suggested shape:** either wire the reader and the transport, or amend ADR-055
to record what was built. Add both senses of "ledger" to the CONTEXT.md
glossary — `aet-validate-scope` exists to catch exactly this class of
terminology collision, and it did not, because both senses are legitimate
domain terms. Leaving four files asserting an unbuilt model is the worst of the
three options.

### 2. Every orchestrated run splits its provenance across two ledger files and deletes half

Ledger path derivation is not single-sourced. Four call sites, three different
answers:

| Call site                    | Derivation                                                   | Resolves to      |
| ---------------------------- | ------------------------------------------------------------ | ---------------- |
| `cli/gate.py:368`            | `telemetry.resolve_repo_root() / ".agents" / "ledger.jsonl"`  | **worktree** root |
| `cli/aet_state.py:583,734`   | `Path(backend.queue_file).resolve().parent / "ledger.jsonl"`  | main repo         |
| `cli/sprint.py:148`          | `Path(args.queue_file).resolve().parent / "ledger.jsonl"`     | main repo         |
| `cli/ship.py:860`            | bare `Ledger()` → CWD-relative default                        | wherever CWD is  |

`resolve_repo_root()` runs `git rev-parse --show-toplevel` (`project_id.py:26`),
which **inside a git worktree returns the worktree's own root**. Verified with a
probe: from `/tmp/wt-probe/wt` it returned `/tmp/wt-probe/wt`, not the main
repo. Meanwhile `_record_stage` (`cli/orchestrator.py:305`) passes an
**absolute** main-repo queue path to `aet state set-stage`, so stage events
resolve to the main repo.

Consequence, on the normal path of every orchestrated run:

- `aet gate submit` runs inside the stage session, whose cwd is the worktree →
  **every `verdict` event lands in `<worktree>/.agents/ledger.jsonl`**, together
  with the boundary-contract (ADR-057) and identity-conflation lens payloads
  that ride it.
- `aet state set-stage` and closure → `<main repo>/.agents/ledger.jsonl`.
- `.worktrees/` is in `AET_IGNORED_PATHS`, and `aet ship close` runs
  `git worktree remove --force` (`cli/ship.py:1003`). **The verdict half of the
  run's provenance is deleted at closure.**

This produces no symptom today only because nothing reads the ledger (item 1) —
a fragmented, half-discarded store and a healthy one are indistinguishable to a
codebase with no readers. It becomes a data-loss bug the moment item 1 is
wired, and it is already a data-loss bug in the honest sense: events the system
recorded on purpose are destroyed.

Two smaller divergences in the same table:

- `ship.py:860`'s bare `Ledger()` is CWD-relative, so `aet ship` invoked from a
  subdirectory reads and writes a different ledger than every other call site.
  Real, and worth its own fix, but the least severe of the three — it needs an
  unusual invocation, whereas the worktree split is the default path.
- `--queue-file` / the `queue` argument are user-settable
  (`cli/sprint.py:175`, `cli/aet_state.py:1409`). A non-default value moves the
  ledger with it while `gate.py` stays at the repo root — a fourth answer,
  conditional on flags.

**Suggested shape:** one exported derivation, the way ADR-023 already solved
this exact problem for verdict paths (`evidence.resolve_verdict_path`, "writers
and the gate must share this single derivation; hand-computing slugs from the
worktree CWD is out of contract"). The ledger needs the same treatment, and the
precedent means this is a known-solved problem applied to a second store, not a
design question. A test should assert all call sites agree from inside a
worktree.

### 3. Downstream projects hit an unrecoverable halt loop: the ledger is missing from `AET_IGNORED_PATHS`

`AET_IGNORED_PATHS` (`worktree.py:535`) holds seven entries and **does not
include `.agents/ledger.jsonl`**. It is consumed by two things whose docstring
promises they "always agree":

1. `write_aet_gitignore_entries()` (`cli/setup.py:44`) — what `aet setup` writes
   into a project's `.gitignore`.
2. `check_base_hygiene()` (`worktree.py:588`) — which excludes AET-generated
   paths from the dirty check "because the orchestrator mutates them as part of
   normal operation and they must be gitignored in projects using the toolkit".

So in any project bootstrapped by `aet setup`: the ledger is not gitignored; the
first AET command that records an event creates it; `check_base_hygiene` runs
`git status --short --untracked-files=all` and does not forgive it
(`worktree.py:603-620`, `_is_ignored_path` misses); the tree is permanently
dirty; ADR-027 halts the next unattended run. The file does not even need to be
*tracked* — untracked is enough.

`ae-toolkit`'s own `.gitignore:15` carries `.agents/ledger.jsonl*`, hand-added.
The dogfooding repo is masked from the break it ships.

**Correcting the source session's framing:** it concluded "the toolkit ships
nothing that makes that automatic". The mechanism does exist and is correct —
one shared constant feeding both the gitignore writer and the hygiene gate. The
defect is a **missed registration** in that constant when ADR-055 added a new
file the toolkit writes on every run. That distinction changes the fix: not
"build an automatic mechanism" but "add the entry, and add a test asserting
every file AET writes under `.agents/` appears in `AET_IGNORED_PATHS`". The
second half is what stops the next store from repeating this.

**Caveat that makes it a decision, not a cleanup:** adding the entry embeds the
"ledger is machine-local" answer to item 1's architectural question. The halt is
real on either branch, so the entry should ship regardless and the ADR question
be taken separately — but shipping it quietly settles the ADR by default, which
is the pattern this whole review is about. Take the decision explicitly.

For a project already halted, the remedies are `git rm --cached
.agents/ledger.jsonl` plus a local gitignore entry (loses nothing that exists —
see item 2: half the events were being deleted anyway), or keep it tracked and
accept the halt. A tracked JSONL that every writer appends to would also
conflict-thrash on merge, which is precisely why decision 4 chose refs.

### 4. The 2026-08-11 "settled tasks disappeared" incident is still undiagnosed

The learning attributed it to hand-editing the ledger. That cannot be the
mechanism: nothing reads the ledger to decide settled-ness (item 1). The
hardening in `01ed6e81` fixed a real data-loss bug in that file — silent line
drops amplified into permanent erasure by rewrite-all — but it did **not** fix
the reported symptom.

Prior learnings point at the likely neighbourhood: `derive_status` rule 1
(`is_ancestor_of_main` on a bare branch) and `cmd_heal`'s trust of that
derivation. **Suggested shape:** a real reproduction before any further fix.
Without one, the third fix will aim at the wrong store too.

### 5. The escalation ladder escalates on the wrong signal

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

### 6. The narrow drift lint

Not "MUST without a referenced gate" — most `MUST`s in the skill corpus are
judgment-shaped, and flagging them all trains suppressions. The enforceable
version is drift detection: **flag prose naming a schema field, CLI flag, or
path that code owns.** Host: `docs_lint.py` with `.agents/doc-rules.yaml`
(ADR-040, documentation invariants as data).

Evidence it works: `scripts/skills-lint` already validates CLI flags mentioned
in skills against the real CLI, and it caught a draft in this session citing
`aet gate submit --help` — a flag that does not exist. Items 1 and 3 show the
target set is wider than `skills/`: the false claims live in module docstrings,
inline comments, `CONVENTIONS.md`, and `WORKFLOW-github.md`.

### 7. `aet state set-stage` writes the ledger after the queue is already pushed

`cli/aet_state.py:729-735`: `backend.save()` → `backend.push()` → print → then
the ledger event. A raise between them leaves the queue advanced with no
`stage` event; in the `sprint add` path (`cli/sprint.py:144-158`) it also skips
`projections.on_add()` and `backend.close()`. Pre-existing, but corruption is
now a reachable raise, so it is easier to hit. Verified by smoke test: the
command printed `Set stage for smk-01: qa-complete` and *then* refused on the
ledger. Belongs with `docs/prds/single-ledger-closure-prd.md`.

### 8. Two deliberate decisions worth re-taking

- **`aet gate submit` swallows ledger corruption as a warning**
  (`cli/gate.py:388`, `except Exception` → print, exit stays 0). Deliberate per
  ADR-057 ("advisory provenance"), but a *corruption* warning is the silent
  shape being removed. If item 1 is wired, advisory is no longer defensible.
- **Whether an unread store should fail closed.** `01ed6e81` makes a store with
  no readers refuse to open when damaged, justified by ADR-033 §3 and ADR-055's
  intent. If item 1 is abandoned, revisit: a write-only advisory store blocking
  commands is over-strict. Note the interaction with item 3 — a stricter ledger
  raises the cost of the halt loop for downstream projects.

### 9. Follow-through on what shipped

- **Watch the recovery rate.** Query stage telemetry for records with
  `attempt >= 2`. If verdict recovery fires on most runs, the prompt is not the
  problem and the ask should shrink further — e.g. have the qa stage emit its
  own report file so `--from-pytest` has an input by construction.
- **The 7f6cace learning still records the prompt clause as the fix.** Now
  superseded by builder mode plus recovery. Worth a correcting append, as was
  done for the ledger learning.
- **`.agents/learnings.jsonl.lock` is left on disk by `aet learnings append`**
  and is not in `AET_IGNORED_PATHS` (unlike the ledger's sibling lock, which
  ae-toolkit's own `.gitignore` covers by glob). Same class as item 3; the
  proposed "every file AET writes is registered" test would catch both.
- **Reinstall before trusting `aet` behaviour.** The installed CLI is a
  snapshot; the five files changed on this branch differ from what `aet` on
  PATH executes until reinstall.

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

**Moving the ledger out of the tree via backend configuration.** No such
configuration exists (item 1). Any recommendation of the form "switch to the
git-refs backend to make this go away" is wrong.

## The rule, as it now reads

Prose must never be the sole carrier of a machine-decidable fact, **and must
never restate a fact code owns** — it should name where the fact lives. Two
questions at authoring time:

1. Is this decidable from repo state or command output? → put it on a code path.
2. Does code already own it? → point at it; do not copy it.

Items 1–3 sharpen it with a third failure mode the original review did not
name: **a fact that code owns in one place, and a second place that recomputes
it.** Item 2 is that defect (four derivations of one path), item 3 is its
inverse (one shared constant, one file forgotten). Neither is a prose problem
and neither would be caught by auditing `skills/`. ADR-023 already solved the
general form for verdict paths; the lesson is that a single-derivation rule
holds only for the store it was written about, unless something enforces it for
the next one.
