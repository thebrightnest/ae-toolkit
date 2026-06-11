#!/bin/bash
# TDD validation script: ensure merge_verified boolean field is removed,
# and merge_verified legacy status is handled correctly in aet-work only.

set -euo pipefail

ERRORS=0

check_file_absent() {
  local file="$1"
  local desc="$2"
  if grep -n "merge_verified" "$file" >/dev/null 2>&1; then
    echo "FAIL: $desc still references merge_verified"
    grep -n "merge_verified" "$file" || true
    ERRORS=$((ERRORS + 1))
  fi
}

check_file_present() {
  local file="$1"
  local desc="$2"
  if ! grep -n "merge_verified" "$file" >/dev/null 2>&1; then
    echo "FAIL: $desc missing merge_verified legacy handling"
    ERRORS=$((ERRORS + 1))
  fi
}

# merge_verified should NOT appear in skills that don't need to know about the legacy status
check_file_absent "aet-ship/SKILL.md" "aet-ship skill instructions"
check_file_absent "aet-pipeline-implement/SKILL.md" "aet-pipeline-implement skill instructions"
check_file_absent "aet-ship/examples/squash-merge-example.md" "aet-ship example"

# merge_verified SHOULD be documented in aet-work as a legacy status
check_file_present "aet-work/SKILL.md" "aet-work skill instructions"

# merge_verified SHOULD be handled in the orchestrator for backward compat
check_file_present "aet-work/lib/queue.py" "orchestrator queue module"

# The boolean field merge_verified must NOT exist in the work queue JSON
if grep -n '"merge_verified"' .agents/work-queue.json >/dev/null 2>&1; then
  echo "FAIL: .agents/work-queue.json still contains merge_verified field"
  ERRORS=$((ERRORS + 1))
fi

if [ "$ERRORS" -eq 0 ]; then
  echo "PASS: merge_verified handled correctly (legacy in aet-work, removed elsewhere)"
  exit 0
else
  echo "FAIL: $ERRORS check(s) failed"
  exit 1
fi
