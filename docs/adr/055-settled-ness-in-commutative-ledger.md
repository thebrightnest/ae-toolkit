# Settled-ness Lives in a Commutative Provenance Ledger That Travels as Pushed Git Refs

## Status

Accepted (2026-08-09). Voids ADR-034 (Settled-ness Is Derived from Versioned
Plan Data). Supersedes ADR-054's revision of ADR-034 decision 3 and revises
ADR-054's durability model for queue and ledger state. Revisits ADR-011's
rejection of event sourcing. Implements the `single-ledger-closure` PRD
(`docs/prds/single-ledger-closure-prd.md`).

## Context

ADR-034 made plan frontmatter `status` the sole settled-ness signal so a
second clone would see the same live/settled partition. It failed in the
way the structural review (`content/aet-structural-review/`) diagnosed:
eight stores answer "is it done?", and five merged plans resurrected as
`queued` because two stores inside one file disagreed while the drift
detector checked neither against the third store that had the right answer.
The generative cause is mechanical closure duties living in prose — the
orchestrator itself asked stage agents to write the plan footer while
`update_plan_footer()` sat wired only to terminal closure.

ADR-054 (rev 4 of the review's lineage) then made plans local-only and
treated queue and history as operator-local state under `~/.aet/{slug}/`.
The beads evaluation (`content/aet-structural-review/12-beads-steal-list.md`)
broke that conclusion: one of the four supported deployment configurations
is one operator across several machines, and `~/.aet` on the laptop is
invisible to the cloud box. It also showed the git-refs backend is two
changes from being the answer — it does not push, and its chained
`content_hash` is non-commutative over a changing task-ref set, so any two
writers generate an irreconcilable conflict by construction.

## Decision

1. **Settled-ness lives in an append-only provenance ledger, not in plan
   frontmatter.** The `status` field leaves the plan contract; `aet plans
   lint` flags it. "Is it done?" is answered by the ledger plus git
   ancestry — exactly one authoritative store pair, replacing eight.
2. **Ledger events are content-addressed and idempotent.** Event ids derive
   deterministically from `source:task:kind:(ref | occurred_at)`; duplicate
   writes are no-ops. Concurrent appends from independent writers commute —
   the union of rows is the correct merge regardless of order. An event
   without an external ref must carry a caller-supplied `occurred_at`,
   enforced at the store boundary.
3. **The tamper-evident chained hash leaves the operational path.** A chain
   over a set is non-commutative by construction; under multi-machine and
   multi-operator configurations it cannot be made to work. Rev 5's
   operator testimony already held that the integrity apparatus creates the
   failures it guards against; the configurations promote that from
   preference to requirement.
4. **Queue and ledger travel with the repo as pushed git refs; config,
   telemetry, and reports stay machine-local.** The transport is the GitHub
   remote every AET project already has — `refs/aet/*` lives inside the
   repository, outside the working tree, invisible to every PR diff. Push
   is best-effort and offline-tolerant everywhere except closure, where it
   is mandatory.
5. **Closure and stage transitions are code transactions.** No skill or
   orchestrator prompt instructs an agent to mutate plan status, footer, or
   queue state. The footer survives as a human breadcrumb maintained by
   code on `aet gate submit`'s success path and at `aet ship` closure.
6. **No leases, claims, or cross-operator arbitration.** Concurrency
   control beyond commutative writes is a management convention, not an
   engine feature. State failing to travel between machines is a
   correctness bug and in scope; two machines racing for one plan is a
   scheduling decision the operator makes, and stays out.

This revisits ADR-011's rejection of event sourcing as "heavier than
needed." That was true when the alternative was one `state` field; it is no
longer true when the alternative is eight stores and a glossary. Its O(1)
objection was aimed at per-task git calls on the read path, which a fold
does not make.

## Consequences

- **Easier:** A fresh clone never resurrects settled work; settled-ness has
  one home. The five-plan defect class is structurally impossible.
- **Easier:** One operator across machines, and several operators on one
  repo, see the same state via the transport AET already mandates.
- **Easier:** The drift detector, footer↔status validator, and
  breadcrumb defenses are deleted with the redundancy they policed.
- **Harder:** Closure now requires a successful refs push; offline closure
  fails loudly. Mitigated by push being best-effort everywhere else.
- **Harder:** The skills corpus and CONTEXT.md describe the old contract
  until slc-06 lands; the PRD's R-10 same-change requirement bounds the
  skew window to one plan.
- **Neutral:** `work-history.jsonl` stays write-only telemetry in `~/.aet`
  (rev 5 stands): written, never loaded by operational commands.

## Alternatives Considered

1. **Adopt beads as the ledger** — Rejected: a second sync mechanism beside
   the mandated GitHub remote, and concurrency machinery aimed at many
   agents on one live frontier, which no AET deployment configuration has
   (`12-beads-steal-list.md`; six designs taken instead).
2. **Keep queue/history operator-local in `~/.aet` (rev 4)** — Rejected:
   does not survive configuration 2; machine-local is retained only for
   genuinely per-machine state (config, telemetry, reports).
3. **Keep the chained `content_hash` envelope** — Rejected: non-commutative
   over a set; a permanent conflict generator for any two writers.
4. **Derive settled-ness from git ancestry alone** — Rejected (ADR-034's
   reasoning stands): ancestry cannot distinguish `merged` from
   `abandoned`; the ledger's `land` event carries the distinction and the
   digest.
5. **Node-aware leases for multi-machine claims** — Rejected on standing
   policy: configuration 2 is a sequential handoff the operator directs,
   not two machines contending for a frontier.
