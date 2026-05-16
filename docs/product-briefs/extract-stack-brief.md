# Product Brief: extract-stack

## Idea Summary

A skill that scans an existing project's infrastructure, DevOps, and automation setup and extracts it into a reusable scaffold. The inverse of `aet-setup`: instead of bootstrapping from scratch, clone the proven setup from a project that already works.

## Demand Reality

**Evidence:**

- User has performed manual infrastructure extraction 10+ times over the past few months when spinning up new PoCs.
- One other developer explicitly asked the user for help doing the same thing.
- Each manual extraction takes 1+ hours and spans dependencies, git hooks, Makefiles, folder structure, design patterns, framework configs, linter settings, and server/DevOps configs.
- Cross-stack pain observed: Python, PHP, and server configurations.

**Assessment:** Real, repeated behavioral evidence. Not interest or waitlists — actual hours spent on tedious config archaeology.

**Uncomfortable truth:** N=1 primary source. No observed lead behavior. The other dev asked for help but we don't know if they would use a _skill_ or just ask for a template repo.

## Status Quo

**Current workaround:**

1. Open the "working well" project.
2. Manually inspect and copy: `package.json` / `requirements.txt`, `.pre-commit-config.yaml`, `Makefile`, `Dockerfile`, CI/CD workflows, linter configs, folder conventions.
3. Rewrite project-specific names, paths, and domains from memory.
4. Test that the new project builds and passes checks.
5. Fix things that were forgotten (usually git hooks or a linter rule).

**Time cost:** 1+ hours per project.
**Failure mode:** Forgetting pieces, introducing drift from team standards, inconsistent security scanning across repos.

## Desperate Specificity

**Primary user:** Engineering leads standardizing setup across multiple team projects.

**Why leads:**

- They have the authority to enforce "every new repo must match our standard."
- They feel pain at scale (5, 10, 20 repos).
- They already use `aet-setup` for greenfield projects; this fills the gap for "clone our golden repo."

**Consequence if unsolved:**

- New projects drift from team standards.
- Security scanning, linting, or type-checking gets silently omitted.
- Onboarding new developers to "yet another project setup" creates friction.

**Secondary personas (out of scope for primary wedge):**

- Solo developers spinning up PoCs (would use it, but don't drive toolkit adoption).
- Agencies cloning client stacks (too many edge cases, not the right fit for a standardized skill).

## Narrowest Wedge

The smallest version someone would use this week:

A skill that scans a single repo, detects CI/CD + container + tooling configs, and produces:

1. An `INFRA.md` manifest documenting what was found.
2. A `scaffold/` directory with extracted, sanitized configs (placeholders for project-specific values).

**Scope boundary:** Must be a companion to `aet-setup`, not a replacement. If `aet-setup` bootstraps from zero, `extract-stack` bootstraps from an existing proven project.

**What is NOT in the wedge:**

- Source code extraction (this is infrastructure only).
- Secret management or migration.
- Automatic application to the new project (human review required).
- Cross-repo synchronization of living projects (one-time extraction only).

## Verdict

**BUILD**

Strong demand evidence (10+ repetitions, 1+ hour each), clear primary user (engineering leads), and natural fit within the existing toolkit ecosystem. The uncomfortable truth is that evidence is still thin beyond the immediate requester — but the pattern is common enough in engineering teams to justify the bet.

**Condition for planning:** Scope must be tightly bounded to "extract what aet-setup would create" to avoid overlap and bloat.

---

_Stage: brief-validated_
_Next step: run `aet-plan`_
