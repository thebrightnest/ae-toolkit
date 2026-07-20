# aet-sync-docs Mechanical-Slice Findings

## Recommendation

**No-go.** Do not promote the mechanical slices of `aet-sync-docs` to a standalone
`aet` CLI subcommand. Keep changed-file diffing, active plan/PRD resolution, and
task-list checkbox transcription inside the `aet-sync-docs` skill (or, if the
orchestrator needs them, as internal library helpers). The mechanical work is
real, but it is too thin, too dependent on the judgment step that precedes it,
and not independently useful enough to justify the extra CLI surface and
maintenance cost.

## Boundary Analysis

`aet-sync-docs/SKILL.md` defines the `sync` procedure as eight steps. The three
candidate mechanical slices are steps 1, 2, and 6:

| Step | Action | Mechanical? | Judgment required? |
| --- | --- | --- | --- |
| 1 | Identify the active plan and corresponding PRD | Yes, with caveats | The "most recently modified `docs/plans/*.md`" heuristic is mechanical, but choosing it over other heuristics (branch name, frontmatter `id`, orchestrator queue) is a judgment the skill currently makes. |
| 2 | Read the git diff for the current branch | Yes | `git diff <base>..HEAD` is purely deterministic. |
| 6 | Update the plan.md task list from the comparison | Yes, *given a verdict* | Marking `✓`, adding `[Changed: …]`, or adding `[Deferred: …]` is mechanical *only after* step 3 has classified each item as completed/changed/added/deferred. Step 6 cannot produce the verdict itself. |
| 3 | Compare plan intent vs. actual diff and classify divergences | **No** | This is the judgment step: deciding whether a change is a rename, a scope narrowing, an unplanned addition, or a deferral. |
| 4–5, 7–8 | Write/append Divergence Summary, update footers, commit | Mixed | Formatting is mechanical; deciding *whether* to write a summary at all depends on the verdict from step 3. |

The boundary holds as literally written: steps 1 and 2 are mechanical, and step
6 is mechanical *conditional on* the output of step 3. The judgment step cannot
be removed from the skill without making the CLI command either (a) silently
classify changes by some brittle heuristic, or (b) require a human/agent to pass
in a pre-computed verdict. Either option erases most of the claimed value of a
standalone subcommand.

## Empirical Evidence

Three historical, merged plan/PRD pairs were re-run through the mechanical
steps. In every case the active plan pointed to its PRD with an explicit
reference, the diff was obtainable by a literal git command, and the task-list
update would have been a transcription exercise — but only because the
divergence classification had already been written by a prior judgment pass.

### Case 1 — `vgr-04-pytest-xdist-parallel` / `validate-gate-review-prd.md`

- **Plan:** `docs/plans/vgr-04-pytest-xdist-parallel.md`
- **PRD:** `docs/prds/validate-gate-review-prd.md`
- **Step 1:** The plan references the PRD as `[validate-gate-review](../prds/validate-gate-review-prd.md)`; resolving the pair is a link/text parse.
- **Step 2:** The implementation branch diff is `git diff e3bb92c2..c1f15cd` (26 files, 75 insertions, 63 deletions).
- **Step 6:** The PRD's Divergence Summary lists a `Changed` item for the plan's task 3, two `Added` items, and no `Deferred` items. Translating those into the vgr-04 task list is mechanical; deciding that the root cause was a stdlib `queue` module collision rather than shared mutable state is the judgment that step 3 owns.

### Case 2 — `unified-orchestrator-plan` / `unified-orchestrator-session-isolated-pipeline.md`

- **Plan:** `docs/plans/unified-orchestrator-plan.md`
- **PRD:** `docs/prds/unified-orchestrator-session-isolated-pipeline.md`
- **Step 1:** The plan references the PRD as `PRD: docs/prds/unified-orchestrator-session-isolated-pipeline.md`.
- **Step 2:** The implementation branch diff is `git diff 4ce3282..b922bdd` (37 files, 907 insertions, 835 deletions).
- **Step 6:** The Divergence Summary records a `Changed` documentation task, an `Added` archive-cleanup integration, and two `Deferred` items (disk-space management and manual reconcile). Mapping those onto the plan's numbered tasks is mechanical; deciding that archive cleanup was "necessary for queue hygiene at scale" is a judgment call.

### Case 3 — `pkg-02-package-skeleton` / `aet-package-extraction-prd.md`

- **Plan:** `docs/plans/pkg-02-package-skeleton.md`
- **PRD:** `docs/prds/aet-package-extraction-prd.md`
- **Step 1:** The plan references the PRD as `PRD: docs/prds/aet-package-extraction-prd.md`.
- **Step 2:** The implementation branch diff is `git diff 8f05d277..cca75b8` (9 files, 115 insertions, 25 deletions).
- **Step 6:** The Divergence Summary records no `Changed` plan tasks, two `Added` test-census adjustments, and no `Deferred` items. The added test changes are not plan tasks at all; the mechanical step can transcribe them into the PRD's `Added` section, but deciding that they count as unplanned rather than as plan-task changes is again step 3.

Across all three cases, steps 1 and 2 completed without any hidden judgment. Step
6 completed without hidden judgment only because the Divergence Summary
(classification) was already present; it never had to decide *what* changed.

## Value vs. Cost Evaluation

**Value of extracting the mechanical slice:**

- Saves a small number of context-window steps in each sync session (run `git diff`, read plan/PRD paths).
- Makes the diff output and plan/PRD resolution format stable across agents.
- Could let the orchestrator pre-fetch the diff before invoking the skill.

**Cost of a standalone subcommand:**

- Adds a new public CLI entry point that must be named, documented, tested, and
  kept stable under the ADR-039 taxonomy.
- Requires a calling contract for the judgment verdict if step 6 is included
  (e.g., `--verdict <json>`), which pushes complexity back onto the caller.
- Risks scope creep: once `aet <something> sync` exists, future requests will
  pressure it to absorb parts of step 3.

The value is marginal because the mechanical work is already one-liner commands
or trivial file parsing. The cost is non-trivial because any CLI addition must
survive the namespace taxonomy and the package-extraction roadmap. The balance
favors leaving the mechanical steps inside the skill.

## Naming Consequence (if the recommendation were "go")

Per `docs/adr/039-namespace-taxonomy.md`, any promoted sync command must follow
the noun-scoped, nested-verb convention already established by `aet sprint add`
and `aet backlog add` (gib-06). The flat-hyphenated form `aet sync-docs` would
not satisfy ADR-039. A mechanical sync command would have to be named something
like `aet docs sync` or `aet state sync`, with the noun (`docs`/`state`)
identifying the domain and the verb (`sync`) identifying the action. Because the
recommendation is no-go, this naming consequence is moot.

## Follow-Up Scope

No follow-up implementation ticket is warranted. `aet-sync-docs` should continue
to execute steps 1, 2, and 6 inside the skill, after the judgment classification
in step 3. If the orchestrator later needs deterministic helpers (e.g., a
function that returns `(plan_path, prd_path, diff_text)`), they should be
internal library code, not a user-facing CLI subcommand.

---

*Recorded: 2026-07-19 — Branch: nc-05-sync-docs-mechanical-spike*
