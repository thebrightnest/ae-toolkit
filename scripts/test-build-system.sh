#!/usr/bin/env bash
# Build system tests for AE Toolkit skill assembly

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

ERRORS=0

echo "=== Build System Tests ==="

# Test 1: build-skills.py exists and can substitute a single partial
test_basic_substitution() {
  echo "Test 1: Basic partial substitution"
  
  local tmpdir
  tmpdir=$(mktemp -d)
  trap 'rm -rf "$tmpdir"' RETURN
  
  mkdir -p "$tmpdir/partials"
  echo "CANONICAL PREAMBLE" > "$tmpdir/partials/preamble.md"
  
  cat << 'TMPL' > "$tmpdir/template.md"
---
name: test-skill
description: Test skill
---

# Test Skill

{preamble}

## Body
TMPL

  python3 scripts/build-skills.py \
    --template "$tmpdir/template.md" \
    --partials-dir "$tmpdir/partials" \
    --output "$tmpdir/output.md" \
    --skill-name "test-skill" \
    --next-step "aet-implement"
  
  if grep -q "CANONICAL PREAMBLE" "$tmpdir/output.md"; then
    echo "  ✓ Basic substitution works"
  else
    echo "  ❌ Basic substitution failed"
    cat "$tmpdir/output.md"
    ERRORS=$((ERRORS + 1))
  fi
}

# Test 2: Multiple partials substituted
test_multiple_partials() {
  echo "Test 2: Multiple partials substitution"
  
  local tmpdir
  tmpdir=$(mktemp -d)
  trap 'rm -rf "$tmpdir"' RETURN
  
  mkdir -p "$tmpdir/partials"
  echo "PREAMBLE TEXT" > "$tmpdir/partials/preamble.md"
  echo "GUARDRAILS TEXT" > "$tmpdir/partials/guardrails.md"
  echo "STAGE TABLE TEXT" > "$tmpdir/partials/stage-table.md"
  
  cat << 'TMPL' > "$tmpdir/template.md"
---
name: {skill_name}
description: Test
---

# Skill

{preamble}

## Guardrails

{guardrails}

## Stage Table

{stage_table}
TMPL

  python3 scripts/build-skills.py \
    --template "$tmpdir/template.md" \
    --partials-dir "$tmpdir/partials" \
    --output "$tmpdir/output.md" \
    --skill-name "test-skill" \
    --next-step "aet-qa"
  
  local failed=0
  grep -q "PREAMBLE TEXT" "$tmpdir/output.md" || { echo "  ❌ preamble missing"; failed=1; }
  grep -q "GUARDRAILS TEXT" "$tmpdir/output.md" || { echo "  ❌ guardrails missing"; failed=1; }
  grep -q "STAGE TABLE TEXT" "$tmpdir/output.md" || { echo "  ❌ stage-table missing"; failed=1; }
  grep -q "name: test-skill" "$tmpdir/output.md" || { echo "  ❌ skill_name not substituted"; failed=1; }
  
  if [ "$failed" -eq 0 ]; then
    echo "  ✓ Multiple partials work"
  else
    ERRORS=$((ERRORS + 1))
  fi
}

# Test 3: docs/PIPELINE.md has required sections
test_pipeline_doc() {
  echo "Test 3: docs/PIPELINE.md sections"
  
  if [ ! -f "docs/PIPELINE.md" ]; then
    echo "  ❌ docs/PIPELINE.md does not exist"
    ERRORS=$((ERRORS + 1))
    return
  fi
  
  local failed=0
  grep -qi "stage state machine" docs/PIPELINE.md || { echo "  ❌ Missing 'Stage State Machine'"; failed=1; }
  grep -qi "trigger" docs/PIPELINE.md || { echo "  ❌ Missing trigger section"; failed=1; }
  grep -qi "completion protocol" docs/PIPELINE.md || { echo "  ❌ Missing 'Completion Protocol'"; failed=1; }
  grep -qi "work-class" docs/PIPELINE.md || { echo "  ❌ Missing 'Work-Class Routing'"; failed=1; }
  
  if [ "$failed" -eq 0 ]; then
    echo "  ✓ docs/PIPELINE.md has all required sections"
  else
    ERRORS=$((ERRORS + 1))
  fi
}

# Test 4: make package calls build system
test_make_package() {
  echo "Test 4: make package integration"
  
  if grep -q "build-skills.py" Makefile; then
    echo "  ✓ Makefile references build-skills.py"
  else
    echo "  ❌ Makefile does not reference build-skills.py"
    ERRORS=$((ERRORS + 1))
  fi
}

# Run all tests
test_basic_substitution
test_multiple_partials
test_pipeline_doc
test_make_package

echo
if [ "$ERRORS" -eq 0 ]; then
  echo "✅ All build system tests passed"
  exit 0
else
  echo "❌ $ERRORS test(s) failed"
  exit 1
fi
