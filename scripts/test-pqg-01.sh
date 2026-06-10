#!/usr/bin/env bash
# TDD validation script for pqg-01: plan self-consistency lint,
# implement reconciliation, and review completeness lens.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

ERRORS=0

echo "=== PQG-01 Behavior Contract Tests ==="
echo

# Test 1: aet-plan contains self-consistency lint procedure
echo "Test 1: aet-plan/SKILL.md contains self-consistency lint"
if grep -iq "self-consistency" aet-plan/SKILL.md && \
   grep -iq "constraint" aet-plan/SKILL.md && \
   grep -iq "files" aet-plan/SKILL.md && \
   grep -iq "acceptance" aet-plan/SKILL.md; then
  echo "  PASS"
else
  echo "  FAIL — missing self-consistency lint procedure"
  ERRORS=$((ERRORS + 1))
fi

# Test 2: aet-implement contains reconciliation procedure
echo "Test 2: aet-implement/SKILL.md contains reconciliation procedure"
if grep -iq "reconcil" aet-implement/SKILL.md && \
   grep -iq "prose" aet-implement/SKILL.md && \
   grep -iq "code block" aet-implement/SKILL.md; then
  echo "  PASS"
else
  echo "  FAIL — missing reconciliation procedure"
  ERRORS=$((ERRORS + 1))
fi

# Test 3: aet-review completeness lens is behavior-oriented
echo "Test 3: aet-review/SKILL.md completeness lens is behavior-oriented"
if grep -q "If I exercised this as the user" aet-review/SKILL.md; then
  echo "  PASS"
else
  echo "  FAIL — missing behavior-oriented completeness question"
  ERRORS=$((ERRORS + 1))
fi

# Test 4: lint, format, and skill structure pass on modified files
echo "Test 4: validation passes on modified skill files"
VALIDATE_OK=true
if ! npx markdownlint-cli2 --config .markdownlint.yaml aet-plan/SKILL.md aet-implement/SKILL.md aet-review/SKILL.md > /dev/null 2>&1; then
  echo "  FAIL — markdownlint failed on modified skill files"
  VALIDATE_OK=false
fi
if ! npx prettier@3.1.0 --check aet-plan/SKILL.md aet-implement/SKILL.md aet-review/SKILL.md > /dev/null 2>&1; then
  echo "  FAIL — prettier format check failed on modified skill files"
  VALIDATE_OK=false
fi
if ! ./scripts/validate-skills.sh > /dev/null 2>&1; then
  echo "  FAIL — skill structure validator failed"
  VALIDATE_OK=false
fi
if [ "$VALIDATE_OK" = true ]; then
  echo "  PASS"
else
  ERRORS=$((ERRORS + 1))
fi

echo
if [ "$ERRORS" -eq 0 ]; then
  echo "✅ All pqg-01 behavior contract tests passed"
  exit 0
else
  echo "❌ Found $ERRORS failure(s)"
  exit 1
fi
