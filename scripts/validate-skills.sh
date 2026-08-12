#!/usr/bin/env bash
# Skill structure validator for AE Toolkit
# Checks: frontmatter, required dirs, line count, internal links,
#         trigger uniqueness, next-step consistency, preamble template match

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

ERRORS=0
WARNINGS=0
SKILL_DIRS=()

# Find all skill directories under skills/ (content-only skill root)
for dir in skills/*/; do
  if [ -f "${dir}SKILL.md" ]; then
    SKILL_DIRS+=("$dir")
  fi
done

echo "=== Skill Structure Checks ==="
echo "Found ${#SKILL_DIRS[@]} skill(s)"
echo

for skill_dir in ${SKILL_DIRS[@]+"${SKILL_DIRS[@]}"}; do
  name="$(basename "${skill_dir%/}")"
  skill_file="${skill_dir}SKILL.md"

  # 1. Required subdirectories
  if [ ! -d "${skill_dir}examples" ]; then
    echo "❌ $name: missing examples/ directory"
    ((ERRORS++)) || true
  fi

  if [ ! -d "${skill_dir}references" ]; then
    echo "❌ $name: missing references/ directory"
    ((ERRORS++)) || true
  fi

  # 2. Content-only rule: no executable code inside skill directories
  #    .example content assets are exempt from the extension check.
  code_files=$(find "$skill_dir" -type f \( -name '*.py' -o -name '*.sh' \) ! -name '*.example*' 2>/dev/null || true)
  if [ -n "$code_files" ]; then
    echo "❌ $name: skill directory contains executable code files (.py/.sh)"
    echo "$code_files"
    ((ERRORS++)) || true
  fi
  if [ -d "${skill_dir}bin" ] || [ -d "${skill_dir}lib" ]; then
    echo "❌ $name: skill directory contains bin/ or lib/ directory"
    ((ERRORS++)) || true
  fi

  # 3. Frontmatter: name must match directory
  frontmatter_name=$(grep -m1 '^name:' "$skill_file" | sed 's/^name: *//' | tr -d '[:space:]') || true
  if [ -z "$frontmatter_name" ]; then
    echo "❌ $name: missing 'name' in frontmatter"
    ((ERRORS++)) || true
  elif [ "$frontmatter_name" != "$name" ]; then
    echo "❌ $name: frontmatter name ('$frontmatter_name') does not match directory"
    ((ERRORS++)) || true
  fi

  # 4. Frontmatter: description must exist
  frontmatter_desc=$(sed -n '/^---$/,/^---$/p' "$skill_file" | grep -m1 '^description:' | sed 's/^description: *//') || true
  if [ -z "$frontmatter_desc" ]; then
    echo "❌ $name: missing 'description' in frontmatter"
    ((ERRORS++)) || true
  fi

  # 5. Line count <= 400 (warning for existing legacy skills)
  line_count=$(wc -l < "$skill_file" | tr -d ' ')
  if [ "$line_count" -gt 400 ]; then
    echo "⚠️  $name: SKILL.md has $line_count lines (recommended max 400; refactor into references/ when editing)"
    ((WARNINGS++)) || true
  fi

  # 6. Execution-mode handling: skills with interactive approval gates must mention AET_EXECUTION_MODE
  if grep -q 'Approve to proceed?' "$skill_file"; then
    if ! grep -q 'AET_EXECUTION_MODE' "$skill_file"; then
      echo "❌ $name: contains interactive approval gate ('Approve to proceed?') but does not mention AET_EXECUTION_MODE"
      ((ERRORS++)) || true
    fi
  fi

  # 7. Preamble template match: Shared Preamble must contain core fields
  if grep -q '^## Shared Preamble' "$skill_file"; then
    for field in BRANCH REPO_STATE AGENTS_MD LEARNINGS ACTIVE_PRD_STAGE ACTIVE_PLAN_STAGE; do
      if ! grep -q "\`$field\`" "$skill_file"; then
        echo "❌ $name: Shared Preamble missing required field \`$field\`"
        ((ERRORS++)) || true
      fi
    done
  fi

done

# 8. Trigger uniqueness: no two skills may share a trigger phrase
echo
echo "=== Trigger Uniqueness Check ==="

TRIGGER_TMP=$(mktemp)
for skill_dir in ${SKILL_DIRS[@]+"${SKILL_DIRS[@]}"}; do
  name="$(basename "${skill_dir%/}")"
  skill_file="${skill_dir}SKILL.md"
  frontmatter_desc=$(sed -n '/^---$/,/^---$/p' "$skill_file" | grep -m1 '^description:' | sed 's/^description: *//') || true
  if [ -z "$frontmatter_desc" ]; then
    continue
  fi
  # Extract quoted strings from description
  phrases=$(echo "$frontmatter_desc" | grep -oE '"[^"]+"' | tr -d '"' || true)
  while IFS= read -r phrase; do
    [ -z "$phrase" ] && continue
    # Normalize: lowercase, strip trailing punctuation
    norm=$(echo "$phrase" | tr '[:upper:]' '[:lower:]' | sed 's/[.,;:!?]$//')
    if [ -n "$norm" ] && [ ${#norm} -gt 2 ]; then
      echo "$norm|$name"
    fi
  done <<< "$phrases"
done > "$TRIGGER_TMP"

TRIGGER_COLLISIONS=$(sort "$TRIGGER_TMP" | cut -d'|' -f1 | uniq -d)
if [ -n "$TRIGGER_COLLISIONS" ]; then
  while IFS= read -r phrase; do
    skills=$(grep "^$phrase|" "$TRIGGER_TMP" | cut -d'|' -f2 | sort -u | tr '\n' ', ' | sed 's/, $//')
    echo "❌ Trigger collision: '$phrase' claimed by: $skills"
    ERRORS=$((ERRORS + 1))
  done <<< "$TRIGGER_COLLISIONS"
fi
rm -f "$TRIGGER_TMP"

if [ -z "$TRIGGER_COLLISIONS" ]; then
  echo "✅ No trigger collisions detected"
fi

# 9. Next-step consistency: completion-protocol pointers must resolve to existing skills
echo
echo "=== Next-Step Consistency Check ==="

NEXTSTEP_ERRORS=0
for skill_dir in ${SKILL_DIRS[@]+"${SKILL_DIRS[@]}"}; do
  name="$(basename "${skill_dir%/}")"
  skill_file="${skill_dir}SKILL.md"

  # Extract next-step skill references from backticks inside "Next step:" lines
  # Look for "run `skill-name`" pattern to avoid matching stage names like `merged`
  next_steps=$(grep -i 'next step:' "$skill_file" | grep -oE 'run `[a-z0-9-]+`' | sed 's/run //' | tr -d '`' || true)

  for step in $next_steps; do
    # Skip non-skill references
    [ "$step" = "none" ] && continue
    [ "$step" = "post-ship-verify" ] && continue
    case "$step" in
      */*) continue ;;
    esac

    # Must resolve to an existing skill directory under skills/
    if [ ! -d "$REPO_ROOT/skills/$step" ] || [ ! -f "$REPO_ROOT/skills/$step/SKILL.md" ]; then
      echo "❌ $name: completion protocol points to non-existent skill '$step'"
      NEXTSTEP_ERRORS=$((NEXTSTEP_ERRORS + 1))
    fi
  done
done

if [ "$NEXTSTEP_ERRORS" -eq 0 ]; then
  echo "✅ All next-step pointers resolve to existing skills"
else
  ERRORS=$((ERRORS + NEXTSTEP_ERRORS))
fi

echo

echo "=== Internal Link Checks ==="
# Single-pass relative-link check: one python process strips code blocks,
# extracts links, and resolves each target (previously several subshells
# per link). Behavior preserved: code-block stripping, http/anchor skips,
# and the broken-link message format are unchanged.
if ! python3 - "$REPO_ROOT" <<'PYEOF'
import os
import re
import sys

repo_root = sys.argv[1]
link_re = re.compile(r"\[([^]]*)\]\(([^)]+)\)")

broken = False
for dirpath, dirnames, filenames in os.walk("."):
    if dirpath == ".":
        dirnames[:] = [d for d in dirnames if d not in (".git", "content", ".worktrees")]
    # Skip dependency directories and build artifacts; their markdown files are
    # third-party content and not part of the maintained corpus.
    dirnames[:] = [d for d in dirnames if d != "node_modules"]
    # Archived plans are settled and excluded from corpus scans; their relative
    # links were written for docs/plans/ and are intentionally not maintained
    # after the move to docs/plans/archive/.
    if dirpath.startswith("./docs/plans/archive"):
        continue
    for fname in filenames:
        if not fname.endswith(".md"):
            continue
        mdfile = os.path.join(dirpath, fname)
        with open(mdfile, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
        # Strip code blocks before checking links (templates contain example links)
        in_fence = False
        kept = []
        for line in lines:
            if line.startswith("```"):
                in_fence = not in_fence
                continue
            if not in_fence:
                kept.append(line)
        for match in link_re.finditer("\n".join(kept)):
            if "http" in match.group(0):
                continue
            # Strip anchor
            link = match.group(2).split("#", 1)[0]
            if not link:
                continue
            target = os.path.normpath(os.path.join(repo_root, os.path.dirname(mdfile), link))
            if not os.path.exists(target):
                print(f"❌ Broken link in {mdfile} → {link}")
                broken = True

sys.exit(1 if broken else 0)
PYEOF
then
  ERRORS=$((ERRORS + 1))
fi

echo

if [ "$WARNINGS" -gt 0 ]; then
  echo "⚠️  $WARNINGS warning(s)"
fi

if [ "$ERRORS" -eq 0 ]; then
  echo "✅ All skill structure checks passed"
  exit 0
else
  echo "❌ Found $ERRORS error(s)"
  exit 1
fi
