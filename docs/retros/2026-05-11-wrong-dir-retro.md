# Retro — New Skills Created Outside Git Repo

_Date: 2026-05-11_
_Cycle: aet-_ toolkit upgrades (stage tracking, pipeline skills, aet-sync-docs)\*

## What Went Wrong

Three new skill directories were created directly in `~/.claude/skills/` instead of in the git repo at `~/Sites/aiskills/`. The skills worked immediately in Claude Code (which reads from `~/.claude/skills/`), but they were silently outside git tracking.

The existing aet-\* skill directories in `~/.claude/skills/` are **symlinks** pointing to `~/Sites/aiskills/`, so edits to existing skills correctly modified the real files. This created a false sense that all file creation was happening in the right place.

## Why Every Check Missed It

1. **`ls` without `-la` hides symlink targets** — the initial `ls /Users/pedrorocha/.claude/skills/ | sort` showed skill names indistinguishably as real dirs or symlinks.
2. **Existing skill edits worked through symlinks** — reinforced the false assumption that `~/.claude/skills/` was the right write location.
3. **`git status` during implementation** — run before the new directories were created; by the time they were created (wrong location), nothing appeared to be wrong.
4. **aet-review passed** — no review lens checked whether new files followed the symlink pattern of existing files.
5. **skill-writing-guide.md Pre-Plan Checklist** — covered agent-agnostic tooling and guardrails, but said nothing about file location verification.

## Root Cause

Two gaps, both in the guidance layer:

1. **skill-writing-guide.md** — Pre-Plan Checklist had no step requiring `ls -la` before creating new files to detect symlink structure.
2. **aet-review** — no "Project Structure" lens; only checked code quality, not whether new files were placed correctly.

## Fixes Applied

### Fix 1 — skill-writing-guide.md Pre-Plan Checklist

Added: _New-file location verified_ — if creating new skill directories, run `ls -la <skills-parent-dir>` BEFORE `mkdir`. Check if existing skills are symlinks. If yes, create the real directory in the symlink target, then symlink from the expected location. Never `mkdir` directly into `~/.claude/skills/`.

### Fix 2 — aet-review `review` command

Added **Project Structure** as the first review lens:

> Do new files/directories follow the same pattern as existing ones? If the project uses symlinks, are new entries created in the real location and linked correctly? Run `ls -la` on the parent directory for any path where new files were created.

## What Would Have Caught This

Either fix alone would have caught it:

- A checklist item requiring `ls -la` before `mkdir` → would show the symlinks
- A review lens explicitly asking "does this new directory match the pattern of existing dirs?" → would prompt `ls -la`

## Prevention

The gap was not about knowing better — it was about having no forcing function. Both fixes add explicit forcing functions that require the agent to look at what already exists before creating anything new.
