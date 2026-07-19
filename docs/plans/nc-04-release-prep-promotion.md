---
id: nc-04-release-prep-promotion
size: S
blocked_by: []
pipeline: minimal
status: approved
security_review: skipped
security_review_reason: This ticket only edits pkg-06's plan-document content; no code lands here. pkg-06's own security_review key is itself being corrected by this ticket (task 4) since the amended disposition is no longer a pure relocation.
docs_sync: skipped
docs_sync_reason: This ticket edits a plan file, not shipped docs; the actual doc sync (SKILL.md Step 1 invocation reference) is already gated by pkg-06's own docs_sync (required).
---

# Plan: Amend pkg-06 with the release-prep Promotion Spec

## Context

Source: `docs/prds/namespace-consolidation-prd.md`, R-4. Target: `docs/plans/pkg-06-cross-skill-extraction.md` — already `status: queued`, `blocked_by: pkg-04-cli-extraction`, footer `plan-approved`, sourced from `docs/prds/aet-package-extraction-prd.md` (R-2, R-3, R-11). Its existing task 5 (lines 47-50) disposes of `aet-release-prep/release-prep.sh` as a pure bash relocation: "Move ... → `scripts/release-prep.sh` (bash helper, not a Python subcommand — repo tooling, not package code)". This contradicts R-4, which requires the script's logic promoted into the package as `aet release-prep`, and contradicts the PRD's own acceptance criterion (verbatim): _"`aet release-prep` executes the full deterministic pipeline with no executable script remaining at the skill root"_ — relocating the script to `scripts/` would still leave an executable script, merely in a different directory, not satisfy that criterion.

Verified directly: `aet-release-prep/release-prep.sh` (376 lines, pure bash + `jq`, no external dependency) is already 100% deterministic — version-source detection (`package.json`/`VERSION`/git-tag, with `v`-prefix stripping), commit classification (conventional-commit prefixes plus keyword fallbacks), semver bump calculation (including prerelease-stripping), and JSON output. This is exactly SKILL.md's Step 1 ("Analyze Commits Since Last Tag") — the script implements all of Step 1 and none of Steps 2-5 (CHANGELOG editing, PRODUCT.md editing, version-file writing, summary), which remain genuine prose/judgment (translating commits into user-facing descriptions, triaging user-facing-vs-internal for PRODUCT.md, confirming the bump with the user). R-4's "deterministic pipeline" maps exactly onto Step 1's existing scope — this ticket does not invent new deterministic behavior beyond what the script already does.

## Intake Triage

- [x] Confirmed this is a **feature or enhancement**, not a reproducible defect
- [x] N/A — no defect redirect needed

## Task List

1. In pkg-06's Context section, add a citation to `docs/prds/namespace-consolidation-prd.md` (R-4) alongside its existing `aet-package-extraction-prd.md` citation, noting task 5 now traces both PRDs — S (traces: R-4)
2. Rewrite pkg-06 task 5's disposition: port `release-prep.sh`'s logic (version-source detection, commit classification including keyword fallbacks, bump calculation including prerelease-stripping, JSON output) with equivalent behavior to a new `aet release-prep` Python subcommand at `src/aet/cli/release_prep.py`; delete `release-prep.sh` entirely — no relocation, since R-4's acceptance criterion requires no executable script remaining at the skill root; update `aet-release-prep/SKILL.md` Step 1's invocation reference from the script path to `aet release-prep` — M (traces: R-4)
3. Update pkg-06's "Files to Modify" list: replace the `aet-release-prep/release-prep.sh → scripts/release-prep.sh` relocation line with `aet-release-prep/release-prep.sh` (deleted) and `src/aet/cli/release_prep.py` (new) — S (traces: R-4)
4. Re-evaluate pkg-06's top-level `security_review` key: flip from `skipped` to `required` and rewrite `security_review_reason` — task 5 is no longer a pure relocation once amended; it adds a new CLI subcommand surface and a full bash-to-Python behavior port, which is behavior-review relevant even without a new dependency — S (traces: R-4)
5. Update pkg-06's "Validation Steps": add a named test file (`tests/test_release_prep.py`, covering version-source detection across all three sources, commit classification including keyword fallbacks, and bump calculation including prerelease-stripping) and an explicit check that `aet-release-prep/release-prep.sh` no longer exists post-merge — S (traces: R-4)
6. Merge branch to main and verify integration — S

**Size definitions:**

- **S**: ≤ 2 hr human time / ≤ 3 files / ≤ 100 diff lines
- **M**: ≤ 1 day human time / ≤ 5 files / ≤ 200 diff lines
- **L**: > 1 day OR > 5 files OR > 200 lines — **must be split before implementation**

### Batching Check

- [x] This is not one of several near-identical additions.
- [x] The diff is expected to exceed 50 lines across pkg-06's Context, Task List, Files-to-Modify, `security_review`, and Validation Steps sections, even though confined to one file.
- [x] The work cannot share a branch/PR with other tickets — it is a standalone amendment with no shared dependency on any other in-flight ticket in this PRD.

## Rejected Alternatives

- **Performing the actual Python port now, during planning** — rejected: Planning Lockout forbids application source code changes; this ticket corrects pkg-06's recorded disposition and gating fields only, leaving the port itself to pkg-06's own implementation time.
- **Leaving pkg-06's `security_review: skipped` unchanged** — rejected: the amended task 5 is no longer a pure relocation; a stale skip would let real behavior-porting work bypass CSO review.
- **Resolving `docs/audits/deprecation-inventory.md`'s separate keyword-fallback deprecation flag as part of this port** — rejected: that is an independent, already-tracked audit finding outside this PRD's scope. The port must preserve existing classification behavior, including keyword fallbacks, unless and until that audit's own disposition removes them — this ticket does not adjudicate it.

## Files to Modify

- `docs/plans/pkg-06-cross-skill-extraction.md`

## Validation Steps

- [ ] Lint passes
- [ ] R-trace coverage: R-4 covered by tasks 1–5; no task cites an unknown R-id
- [ ] Named check per new file: N/A — no new file is introduced; pkg-06 is amended in place. Confirm the amended pkg-06 still passes its own self-consistency checks (files-assigned-to-tasks, R-trace coverage) after the edit
- [ ] Test types: N/A — plan-document edit only, no executable code
- [ ] Merge verified: `git merge-base --is-ancestor HEAD origin/main`

## Rollback Plan

Revert the commit amending pkg-06; pkg-06 reverts to its pre-amendment state (bash-relocate disposition, `security_review: skipped`), which was already a valid, independently mergeable plan — just not R-4-compliant.

## Pipeline

`pipeline` controls how the orchestrator runs this plan. It is set in the
frontmatter and is read by `aet run`/`run-one`.

| Value      | Behavior                                            |
| ---------- | ---------------------------------------------------- |
| `standard` | Default grouping (TDD→implement→QA, review, CSO)    |
| `minimal`  | All stages in one session; fastest, least isolation |
| `full`     | One session per stage; slowest, maximum isolation   |

`minimal` fits here: a contained plan-document edit with no code, dependency, auth, or API surface of its own.

---

_Stage: plan-approved_
_Next step: run `aet-work`_
