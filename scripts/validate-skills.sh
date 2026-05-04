#!/usr/bin/env bash
# Skill structure validator for AE Toolkit
# Checks: frontmatter, required dirs, line count, internal links

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

ERRORS=0
WARNINGS=0
SKILL_DIRS=()

# Find all skill directories (root-level dirs containing SKILL.md)
for dir in */; do
  if [ -f "${dir}SKILL.md" ]; then
    SKILL_DIRS+=("$dir")
  fi
done

echo "=== Skill Structure Checks ==="
echo "Found ${#SKILL_DIRS[@]} skill(s)"
echo

for skill_dir in "${SKILL_DIRS[@]}"; do
  name="${skill_dir%/}"
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

  # 2. Frontmatter: name must match directory
  frontmatter_name=$(grep -m1 '^name:' "$skill_file" | sed 's/^name: *//' | tr -d '[:space:]') || true
  if [ -z "$frontmatter_name" ]; then
    echo "❌ $name: missing 'name' in frontmatter"
    ((ERRORS++)) || true
  elif [ "$frontmatter_name" != "$name" ]; then
    echo "❌ $name: frontmatter name ('$frontmatter_name') does not match directory"
    ((ERRORS++)) || true
  fi

  # 3. Frontmatter: description must exist
  frontmatter_desc=$(grep -m1 '^description:' "$skill_file" | sed 's/^description: *//') || true
  if [ -z "$frontmatter_desc" ]; then
    echo "❌ $name: missing 'description' in frontmatter"
    ((ERRORS++)) || true
  fi

  # 4. Line count <= 400 (warning for existing legacy skills)
  line_count=$(wc -l < "$skill_file" | tr -d ' ')
  if [ "$line_count" -gt 400 ]; then
    echo "⚠️  $name: SKILL.md has $line_count lines (recommended max 400; refactor into references/ when editing)"
    ((WARNINGS++)) || true
  fi
done

echo

echo "=== Internal Link Checks ==="
LINK_ERRORS=0
# Check that relative markdown links resolve
while IFS= read -r -d '' mdfile; do
  # Strip code blocks before checking links (templates contain example links)
  links=$(sed '/^```/,/^```/d' "$mdfile" | grep -oE '\[([^]]*)\]\(([^)]+)\)' 2>/dev/null | grep -v 'http' | grep -v '^#' || true)
  if [ -n "$links" ]; then
    echo "$links" | while read -r match; do
      link=$(echo "$match" | sed -E 's/.*\]\(([^)]+)\).*/\1/')
      # Strip anchor
      link="${link%%\#*}"
      [ -z "$link" ] && continue
      [[ "$link" == \#* ]] && continue
      dir=$(dirname "$mdfile")
      target="$dir/$link"
      target=$(cd "$REPO_ROOT" && realpath -m "$target" 2>/dev/null || echo "$target")
      if [ ! -e "$target" ]; then
        echo "❌ Broken link in $mdfile → $link"
        touch "$REPO_ROOT/.link-errors"
      fi
    done
  fi
done < <(find . -name '*.md' -not -path './.git/*' -not -path './content/*' -print0)

if [ -f "$REPO_ROOT/.link-errors" ]; then
  rm "$REPO_ROOT/.link-errors"
  LINK_ERRORS=1
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
