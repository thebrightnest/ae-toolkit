#!/usr/bin/env bash
set -euo pipefail

# Orchestrator integration tests
# Tests parallel execution, concurrency cap, drain-on-failure, and resume behavior.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE="$SCRIPT_DIR/../aet-work/references/orchestrator-template.sh"
TMPDIR=""
FAILED=0
PASS=0

cleanup() {
  if [ -n "${TMPDIR:-}" ] && [ -d "$TMPDIR" ]; then
    rm -rf "$TMPDIR"
  fi
}
trap cleanup EXIT

setup_tmpdir() {
  TMPDIR=$(mktemp -d -t aet-orchestrator-test-XXXXXX)
}

# Generate a runnable orchestrator from the template by substituting placeholders.
generate_orchestrator() {
  local repo="$1"
  local cli_bin="$2"
  local max_jobs="${3:-}"

  local orchestrator="$repo/scripts/.aet-work-orchestrator.sh"

  # Read template, substitute variables
  sed \
    -e "s|{{CLI_BIN}}|$cli_bin|g" \
    -e 's|{{CLI_ARGS}}||g' \
    -e 's|{{CLI_PROMPT_FLAG}}||g' \
    -e 's|{{CLI_WORKDIR_FLAG}}||g' \
    "$TEMPLATE" > "$orchestrator"
  chmod +x "$orchestrator"

  # Also inject MAX_JOBS override if provided
  if [ -n "$max_jobs" ]; then
    sed -i.bak "1i\\
MAX_JOBS=$max_jobs
" "$orchestrator"
    rm -f "$orchestrator.bak"
  fi
}

# Create a mock git repo with the required structure
setup_repo() {
  local repo="$TMPDIR/repo"
  mkdir -p "$repo/.agents" "$repo/scripts" "$repo/docs/plans"
  cd "$repo"
  git init -q
  git config user.email "test@test.com"
  git config user.name "Test"
  touch README.md
  git add README.md
  git commit -q -m "init"
  # Ensure main branch exists (git init may already create it)
  git checkout -q main 2>/dev/null || git checkout -q -b main
  echo "$repo"
}

# Create a mock agent CLI that sleeps for N seconds then exits with a code.
# Usage: create_mock_cli <name> <sleep_sec> <exit_code>
create_mock_cli() {
  local name="$1"
  local sleep_sec="$2"
  local exit_code="$3"
  local cli="$TMPDIR/$name"
  cat > "$cli" <<EOF
#!/usr/bin/env bash
sleep $sleep_sec
exit $exit_code
EOF
  chmod +x "$cli"
  echo "$cli"
}

# Write a work-queue.json file
write_queue() {
  local repo="$1"
  shift
  python3 -c "
import json, sys
queue = sys.argv[1:]
# Each arg is a JSON object string
objs = [json.loads(a) for a in queue]
with open('$repo/.agents/work-queue.json', 'w') as f:
    json.dump(objs, f, indent=2)
    f.write('\n')
" "$@"
}

# Read a work-queue.json file and print statuses
read_queue_statuses() {
  local repo="$1"
  python3 -c "
import json
with open('$repo/.agents/work-queue.json') as f:
    queue = json.load(f)
for t in queue:
    print(f\"{t['id']}:{t['status']}\")
"
}

# Read a work-queue.json file and extract a single field for a task
get_task_field() {
  local repo="$1"
  local task_id="$2"
  local field="$3"
  python3 -c "
import json, sys
with open('$repo/.agents/work-queue.json') as f:
    queue = json.load(f)
for t in queue:
    if t['id'] == '$task_id':
        val = t.get('$field', 'NULL')
        print('NULL' if val is None else val)
        sys.exit(0)
sys.exit(1)
" "$repo"
}

# Run the orchestrator in the repo and return exit code
run_orchestrator() {
  local repo="$1"
  cd "$repo"
  # Commit any scaffold files so the pre-branch hygiene check passes
  git add -A
  git commit -q -m "test scaffold" || true
  set +e
  "$repo/scripts/.aet-work-orchestrator.sh" > "$TMPDIR/orchestrator.log" 2>&1
  local ec=$?
  set -e
  echo $ec > "$TMPDIR/orchestrator.exit"
}

# Assert that a condition is true
assert() {
  local msg="$1"
  shift
  if "$@"; then
    echo "  ✓ $msg"
    ((PASS+=1))
  else
    echo "  ✗ $msg"
    ((FAILED+=1))
  fi
}

# ---- Tests -------------------------------------------------------------

test_parallel_execution() {
  echo "TEST: parallel execution of independent tasks"
  setup_tmpdir
  local repo
  repo=$(setup_repo)
  local cli
  cli=$(create_mock_cli "mock-cli" 2 0)

  generate_orchestrator "$repo" "$cli"

  write_queue "$repo" \
    '{"id":"t1","title":"Task 1","status":"unblocked","plan_file":"docs/plans/t1.md","blocked_by":[]}' \
    '{"id":"t2","title":"Task 2","status":"unblocked","plan_file":"docs/plans/t2.md","blocked_by":[]}' \
    '{"id":"t3","title":"Task 3","status":"unblocked","plan_file":"docs/plans/t3.md","blocked_by":[]}'

  local start end elapsed
  start=$(python3 -c 'import time; print(time.time())')
  run_orchestrator "$repo"
  end=$(python3 -c 'import time; print(time.time())')
  elapsed=$(python3 -c "print(int($end - $start))")

  assert "orchestrator exits 0" [ "$(cat "$TMPDIR/orchestrator.exit")" -eq 0 ]
  local done_count
  done_count=$(read_queue_statuses "$repo" | grep -c ':done' || true)
  assert "all tasks done" [ "$done_count" -eq 3 ]
  # Sequential would be ~6s + worktree overhead; parallel should be ~2s + overhead
  assert "parallel (elapsed < 5s)" [ "$elapsed" -lt 5 ]

  cleanup
  TMPDIR=""
}

test_concurrency_cap() {
  echo "TEST: concurrency cap respected"
  setup_tmpdir
  local repo
  repo=$(setup_repo)
  local cli
  cli=$(create_mock_cli "mock-cli" 2 0)

  generate_orchestrator "$repo" "$cli" 2

  write_queue "$repo" \
    '{"id":"t1","title":"Task 1","status":"unblocked","plan_file":"docs/plans/t1.md","blocked_by":[]}' \
    '{"id":"t2","title":"Task 2","status":"unblocked","plan_file":"docs/plans/t2.md","blocked_by":[]}' \
    '{"id":"t3","title":"Task 3","status":"unblocked","plan_file":"docs/plans/t3.md","blocked_by":[]}' \
    '{"id":"t4","title":"Task 4","status":"unblocked","plan_file":"docs/plans/t4.md","blocked_by":[]}'

  local start end elapsed
  start=$(python3 -c 'import time; print(time.time())')
  run_orchestrator "$repo"
  end=$(python3 -c 'import time; print(time.time())')
  elapsed=$(python3 -c "print(int($end - $start))")

  assert "orchestrator exits 0" [ "$(cat "$TMPDIR/orchestrator.exit")" -eq 0 ]
  local done_count
  done_count=$(read_queue_statuses "$repo" | grep -c ':done' || true)
  assert "all tasks done" [ "$done_count" -eq 4 ]
  # With cap=2 and 4 tasks of 2s each, sequential would be ~8s + overhead, parallel-2 ~4s + overhead
  assert "cap respected (elapsed >= 4s)" [ "$elapsed" -ge 4 ]
  assert "cap respected (elapsed < 8s)" [ "$elapsed" -lt 8 ]

  cleanup
  TMPDIR=""
}

test_drain_on_failure() {
  echo "TEST: drain on failure"
  setup_tmpdir
  local repo
  repo=$(setup_repo)

  # t1 succeeds, t2 fails, t3 succeeds
  local cli_ok cli_fail
  cli_ok=$(create_mock_cli "mock-ok" 1 0)
  cli_fail=$(create_mock_cli "mock-fail" 1 1)

  # We'll use a single CLI that decides based on task ID via env, but our template
  # doesn't support that. Instead, make all tasks use the same CLI but have the
  # CLI check a marker file. Simpler: use a wrapper.
  local wrapper="$TMPDIR/mock-wrapper"
  cat > "$wrapper" <<'EOF'
#!/usr/bin/env bash
# The prompt is passed as extra args; last arg is the plan file.
# We look at worktree dir to infer task id.
TASK_ID=$(basename "$PWD")
if [ "$TASK_ID" = "t2" ]; then
  sleep 1
  exit 1
fi
sleep 1
exit 0
EOF
  chmod +x "$wrapper"

  generate_orchestrator "$repo" "$wrapper"

  write_queue "$repo" \
    '{"id":"t1","title":"Task 1","status":"unblocked","plan_file":"docs/plans/t1.md","blocked_by":[]}' \
    '{"id":"t2","title":"Task 2","status":"unblocked","plan_file":"docs/plans/t2.md","blocked_by":[]}' \
    '{"id":"t3","title":"Task 3","status":"unblocked","plan_file":"docs/plans/t3.md","blocked_by":[]}'

  local start end elapsed
  start=$(python3 -c 'import time; print(time.time())')
  run_orchestrator "$repo"
  end=$(python3 -c 'import time; print(time.time())')
  elapsed=$(python3 -c "print(int($end - $start))")

  assert "orchestrator exits non-zero" [ "$(cat "$TMPDIR/orchestrator.exit")" -ne 0 ]
  # t1 and t3 should have finished (drain), t2 failed
  local t1_status t2_status t3_status
  t1_status=$(get_task_field "$repo" t1 status)
  t2_status=$(get_task_field "$repo" t2 status)
  t3_status=$(get_task_field "$repo" t3 status)
  assert "t1 done" [ "$t1_status" = "done" ]
  assert "t2 failed" [ "$t2_status" = "failed" ]
  assert "t3 done" [ "$t3_status" = "done" ]
  # All 3 start, t2 fails at ~1s, t1/t3 drain by ~2s
  assert "drain respected (elapsed >= 1)" [ "$elapsed" -ge 1 ]
  assert "drain respected (elapsed < 5)" [ "$elapsed" -lt 5 ]

  cleanup
  TMPDIR=""
}

test_orphaned_in_progress() {
  echo "TEST: orphaned in-progress tasks marked failed"
  setup_tmpdir
  local repo
  repo=$(setup_repo)
  local cli
  cli=$(create_mock_cli "mock-cli" 0 0)

  generate_orchestrator "$repo" "$cli"

  write_queue "$repo" \
    '{"id":"t1","title":"Task 1","status":"in-progress","plan_file":"docs/plans/t1.md","blocked_by":[]}' \
    '{"id":"t2","title":"Task 2","status":"unblocked","plan_file":"docs/plans/t2.md","blocked_by":[]}'

  # Create a worktree for t1 (orphaned) but no real process
  mkdir -p "$repo/.worktrees/t1"

  run_orchestrator "$repo"

  assert "orchestrator exits 0" [ "$(cat "$TMPDIR/orchestrator.exit")" -eq 0 ]
  local t1_status t2_status
  t1_status=$(get_task_field "$repo" t1 status)
  t2_status=$(get_task_field "$repo" t2 status)
  assert "t1 marked failed" [ "$t1_status" = "failed" ]
  assert "t2 done" [ "$t2_status" = "done" ]

  cleanup
  TMPDIR=""
}

test_empty_worktree_cleanup_on_success() {
  echo "TEST: empty worktree removed when agent makes no commits (success)"
  setup_tmpdir
  local repo
  repo=$(setup_repo)
  local cli
  cli=$(create_mock_cli "mock-cli" 0 0)

  generate_orchestrator "$repo" "$cli"

  write_queue "$repo" \
    '{"id":"t1","title":"Task 1","status":"unblocked","plan_file":"docs/plans/t1.md","blocked_by":[],"worktree":".worktrees/t1"}'

  run_orchestrator "$repo"

  assert "orchestrator exits 0" [ "$(cat "$TMPDIR/orchestrator.exit")" -eq 0 ]
  assert "t1 done" [ "$(get_task_field "$repo" t1 status)" = "done" ]
  assert "worktree directory removed" [ ! -d "$repo/.worktrees/t1" ]
  assert "worktree field cleared" [ "$(get_task_field "$repo" t1 worktree)" = "NULL" ]

  cleanup
  TMPDIR=""
}

test_empty_worktree_cleanup_on_failure() {
  echo "TEST: empty worktree removed when agent makes no commits (failure)"
  setup_tmpdir
  local repo
  repo=$(setup_repo)
  local cli
  cli=$(create_mock_cli "mock-cli" 0 1)

  generate_orchestrator "$repo" "$cli"

  write_queue "$repo" \
    '{"id":"t1","title":"Task 1","status":"unblocked","plan_file":"docs/plans/t1.md","blocked_by":[],"worktree":".worktrees/t1"}'

  run_orchestrator "$repo"

  assert "orchestrator exits non-zero" [ "$(cat "$TMPDIR/orchestrator.exit")" -ne 0 ]
  assert "t1 failed" [ "$(get_task_field "$repo" t1 status)" = "failed" ]
  assert "worktree directory removed" [ ! -d "$repo/.worktrees/t1" ]
  assert "worktree field cleared" [ "$(get_task_field "$repo" t1 worktree)" = "NULL" ]

  cleanup
  TMPDIR=""
}

# ---- Main ---------------------------------------------------------------

echo "============================================"
echo "Orchestrator Integration Tests"
echo "Template: $TEMPLATE"
echo "============================================"
echo ""

# Verify template exists
if [ ! -f "$TEMPLATE" ]; then
  echo "ERROR: Template not found at $TEMPLATE"
  exit 1
fi

test_parallel_execution
test_concurrency_cap
test_drain_on_failure
test_orphaned_in_progress
test_empty_worktree_cleanup_on_success
test_empty_worktree_cleanup_on_failure

echo ""
echo "============================================"
echo "Results: $PASS passed, $FAILED failed"
echo "============================================"

if [ "$FAILED" -gt 0 ]; then
  exit 1
fi
