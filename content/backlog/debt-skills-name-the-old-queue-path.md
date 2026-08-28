---
type: debt
status: accepted
recorded: 2026-08-27
source: docs/retros/2026-08-27-planning-pipeline-contradictions-retro.md
trigger: >-
  The next skill edit in `aet-work` or `aet-setup`, or any session where an agent reads or writes `.agents/work-queue.json` because a skill told it to.
depends_on: []
blocks: []
---

# Skills still name `.agents/work-queue.json` as the board

The `git-refs` backend stores the board in `refs/aet/tasks/*` with a
`refs/aet/meta/queue` envelope. `.agents/work-queue.json` is a path the backend no
longer writes, and `aet setup verify` already warns that `.gitignore` names it.
Seventeen references survive across fifteen files in six skills — `aet-work`
(7), `aet-pipeline-plan` (4), `aet-plan` (2), `aet-setup` (2),
`aet-validate-scope` (1), `aet-evolve` (1), plus reference files, examples, and
`aet-setup/checklist.md`.

One of the seventeen was corrected in passing when `aet-plan`'s completion item 5
was rewritten. The rest are untouched.

**Why accepted:** the occurrences are not uniformly wrong.
`aet-work/references/migration-aet-state.md` and `upgrading-existing-project.md`
describe migrating *from* that layout, where naming the old path is the point. A
blind replace would corrupt them, and the 2026-08-23 learning is specifically
about sweeps reported complete while wrong copies survive in reference files and
templates. The audit needs per-file judgment, which is more than the retro that
found it should carry.

**Trigger to fix:** the next skill edit in `aet-work` or `aet-setup`, or any
session where an agent reads or writes `.agents/work-queue.json` because a skill
told it to.
