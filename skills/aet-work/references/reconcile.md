# `aet reconcile`

Report and heal drift between committed plans and their GitHub Issues mirror.

## Overview

The GitHub Issues projection is a one-way mirror: AET writes issues and labels,
but it never reads the board to decide what to do. Over time the board can drift
from the committed plan state: a plan is promoted without an issue being
created, a label is changed by hand, an issue is closed while its plan is still
live, or an issue outlives its plan.

`aet reconcile` compares the live plans in `docs/plans/*.md` against the
`aet:*` issues in the configured GitHub repository, reports the differences,
and optionally applies the smallest corrective write.

## Safety contract

- **Dry-run by default.** Running `aet reconcile` with no flags prints the diff
  and mutates nothing.
- **`--apply` is required to write.** Corrective writes happen only when the
  operator explicitly opts in.
- **Orphan issues are reported, never deleted.** An issue whose plan is settled
  or missing is surfaced for human decision; reconcile will not bulk-close
  issues.
- **Hand-closed live issues are reopened under `--apply`.** A live plan whose
  issue was closed outside AET is reported; with `--apply` the issue is reopened
  and relabelled.
- **All writes go through the fail-open projection dispatcher.** A dead `gh`
  token, network outage, or API error is warned on stderr but does not fail the
  command.

## Drift categories

| Category      | Cause                                                    | `--apply` action                                      |
|---------------|----------------------------------------------------------|-------------------------------------------------------|
| `missing`     | Live plan has no matching `aet:*` issue.                 | Create the issue with the correct `aet:*` label.      |
| `mislabeled`  | Issue exists but carries the wrong or extra `aet:*` labels. | Edit labels so exactly the expected label remains.    |
| `closed-live` | Live plan's issue is closed.                             | Reopen the issue and ensure its label is correct.     |
| `orphan`      | Issue exists for a plan that is no longer live.          | Report only; never delete or close automatically.     |

## Expected labels

The expected label for a live plan follows the same mapping as the rest of the
projection:

- `status: draft` → `aet:draft`
- `status: approved` → `aet:backlog`
- `status: queued` with pending blockers → `aet:blocked`
- `status: queued` with no pending blockers → `aet:ready`
- `status: in_progress` → `aet:in-progress`
- `status: awaiting_merge` → `aet:awaiting-merge`

If a queued plan is also present in the local work queue, the queue state takes
precedence. Missing live plans get a synthetic task derived from their
frontmatter.

## Usage

```bash
# Report only (recommended first step)
aet reconcile

# Apply corrections
aet reconcile --apply

# Use a non-standard plans directory or config
aet reconcile --plans-dir docs/plans --config .agents/aet-work.json

# Machine-readable output
aet reconcile --json
```

## Configuration

Reconcile uses the same `projections` config axis as the rest of AET:

```json
{
  "task_backend": "git-refs",
  "projections": [
    { "type": "github", "repo": "owner/repo", "label_prefix": "aet" }
  ]
}
```

When no projection is configured, `aet reconcile` exits successfully after
reporting that there is nothing to reconcile.
