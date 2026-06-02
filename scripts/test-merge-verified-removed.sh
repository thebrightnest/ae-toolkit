#!/bin/bash
# TDD validation script: ensure merge_verified is removed from skill logic

set -euo pipefail

ERRORS=0

check_file() {
  local file="$1"
  local desc="$2"
  if grep -n "merge_verified" "$file" >/dev/null 2>&1; then
    echo "FAIL: $desc still references merge_verified"
    grep -n "merge_verified" "$file" || true
    ERRORS=$((ERRORS + 1))
  fi
}

check_file "aet-work/SKILL.md" "aet-work skill instructions"
check_file "aet-ship/SKILL.md" "aet-ship skill instructions"
check_file "aet-pipeline-implement/SKILL.md" "aet-pipeline-implement skill instructions"
check_file "aet-ship/examples/squash-merge-example.md" "aet-ship example"
check_file "aet-work/references/orchestrator-template.sh" "orchestrator template"
check_file "aet-work/references/afk-loop-orchestrator.sh" "afk-loop orchestrator"

# Check work-queue.json for merge_verified field (not just occurrences in values)
if grep -n '"merge_verified"' .agents/work-queue.json >/dev/null 2>&1; then
  echo "FAIL: .agents/work-queue.json still contains merge_verified field"
  ERRORS=$((ERRORS + 1))
fi

if [ "$ERRORS" -eq 0 ]; then
  echo "PASS: No merge_verified references found in target files"
  exit 0
else
  echo "FAIL: $ERRORS file(s) still reference merge_verified"
  exit 1
fi
