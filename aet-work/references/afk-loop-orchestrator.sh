#!/usr/bin/env bash
# =============================================================================
# AFK Loop Orchestrator — Reference Implementation
# =============================================================================
# This is a standalone, heavily commented example of the queue-processing loop
# used by aet-work. It demonstrates:
#
#   - Reading and writing JSON queue state with inline python3 (no jq)
#   - Topological task ordering via blocked_by / blocks arrays
#   - Idempotent git worktree creation for branch isolation
#   - A stub agent_invoke() function you can adapt for your runtime
#
# Copy this script, customize agent_invoke(), and run it directly:
#   ./afk-loop-orchestrator.sh
#
# Or use aet-work run to generate a fully configured version.
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration — adjust these for your repo and agent runtime
# ---------------------------------------------------------------------------

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
QUEUE_FILE="$REPO_ROOT/.agents/work-queue.json"

# ---------------------------------------------------------------------------
# Agent invocation stub — customize this for your CLI
# ---------------------------------------------------------------------------
# This function is called once per task. It receives the path to the task's
# plan.md and the path to its dedicated worktree directory.
#
# Examples:
#   Kimi:    kimi --afk -p "Run aet-pipeline-implement on $plan_file" -w "$worktree_dir"
#   Claude:  claude --print --dangerously-skip-permissions "Run aet-pipeline-implement on $plan_file" --add-dir "$worktree_dir"
#   Aider:   aider --message "Implement the plan in $plan_file" --file "$worktree_dir"
#
# Return 0 on success, non-zero on failure.
# ---------------------------------------------------------------------------

agent_invoke() {
  local plan_file="$1"
  local worktree_dir="$2"

  # >>> CUSTOMIZE THIS BLOCK FOR YOUR RUNTIME <<<
  echo "[STUB] Would invoke agent on:"
  echo "  Plan file:   $plan_file"
  echo "  Worktree:    $worktree_dir"
  echo ""
  echo "Edit agent_invoke() in this script to plug in your CLI."
  return 1
}

# ---------------------------------------------------------------------------
# Queue helpers (inline python3 — portable, no external dependencies)
# ---------------------------------------------------------------------------

# Returns the first task with status "unblocked" as JSON, or exits 1.
get_next_unblocked() {
  python3 -c "
import json, sys
with open('$QUEUE_FILE', 'r') as f:
    queue = json.load(f)
for task in queue:
    if task.get('status') == 'unblocked':
        print(json.dumps(task))
        sys.exit(0)
sys.exit(1)
"
}

# Updates a task's status. Optional third arg records the failed stage.
mark_status() {
  local task_id="$1"
  local status="$2"
  local stage="${3:-}"
  python3 -c "
import json
with open('$QUEUE_FILE', 'r') as f:
    queue = json.load(f)
for task in queue:
    if task['id'] == '$task_id':
        task['status'] = '$status'
        if '$stage':
            task['failed_stage'] = '$stage'
with open('$QUEUE_FILE', 'w') as f:
    json.dump(queue, f, indent=2)
    f.write('\n')
"
}

# Promotes "blocked" tasks to "unblocked" when all their blockers are done.
promote_dependents() {
  python3 -c "
import json
with open('$QUEUE_FILE', 'r') as f:
    queue = json.load(f)
done_ids = {t['id'] for t in queue if t.get('status') == 'done'}
for task in queue:
    if task.get('status') == 'blocked':
        blockers = task.get('blocked_by', [])
        if all(b in done_ids for b in blockers):
            task['status'] = 'unblocked'
with open('$QUEUE_FILE', 'w') as f:
    json.dump(queue, f, indent=2)
    f.write('\n')
"
}

# Check that all blocked_by dependencies are merged before starting a task.
check_dependency_merged() {
  local task_id="$1"
  python3 -c "
import json, sys
with open('$QUEUE_FILE', 'r') as f:
    queue = json.load(f)
task = next((t for t in queue if t['id'] == '$task_id'), None)
if not task:
    sys.exit(0)
for dep_id in task.get('blocked_by', []):
    dep = next((t for t in queue if t['id'] == dep_id), None)
    if not dep:
        continue
    if dep.get('status') != 'merged':
        print(f'⚠️  Warning: dependency {dep_id} is not merged. '
              f'This task may build on a stale base. Continuing anyway.')
        sys.stdout.flush()
"
}

# ---------------------------------------------------------------------------
# Pre-branch hygiene check
# ---------------------------------------------------------------------------

check_main_hygiene() {
  local repo_root="$1"
  cd "$repo_root"

  # Ensure origin refs are current
  git fetch origin 2>/dev/null || true

  # Check working tree
  if [ -n "$(git status --short)" ]; then
    echo "⚠️  Working tree is dirty. Stash or commit changes before branching."
    return 1
  fi

  # Check unpushed commits
  local ahead
  ahead=$(git rev-list --count origin/main..main 2>/dev/null || echo 0)
  if [ "$ahead" -gt 0 ]; then
    echo "⚠️  Local main is ahead of origin/main by $ahead commit(s)."
    echo "   Push first: git push origin main"
    echo "   Or branch from origin/main explicitly."
    return 1
  fi

  # Check unpulled commits
  local behind
  behind=$(git rev-list --count main..origin/main 2>/dev/null || echo 0)
  if [ "$behind" -gt 0 ]; then
    echo "⚠️  Local main is behind origin/main by $behind commit(s)."
    echo "   Pull first: git pull origin main"
    return 1
  fi

  return 0
}

# ---------------------------------------------------------------------------
# Worktree helper (idempotent — safe to re-run on resume)
# ---------------------------------------------------------------------------

ensure_worktree() {
  local task_id="$1"
  local worktree_dir="$REPO_ROOT/.worktrees/$task_id"

  if [ ! -d "$worktree_dir" ]; then
    echo "   Creating worktree: $worktree_dir"
    git -C "$REPO_ROOT" worktree add "$worktree_dir" -b "$task_id"
  else
    echo "   Reusing existing worktree: $worktree_dir"
  fi

  echo "$worktree_dir"
}

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

echo "🚀 AFK loop orchestrator starting..."
echo "   Queue file: $QUEUE_FILE"
echo "   Repo root:  $REPO_ROOT"
echo ""

CURRENT_BRANCH=$(git -C "$REPO_ROOT" branch --show-current)
if [ "$CURRENT_BRANCH" != "main" ]; then
  echo "⚠️  Currently on '$CURRENT_BRANCH', not 'main'. Skipping pre-branch hygiene check."
  echo "   Run 'git checkout main' first if you want worktrees based on a clean, synced main."
else
  if ! check_main_hygiene "$REPO_ROOT"; then
    if [ "${AET_EXECUTION_MODE:-}" = "unattended" ]; then
      echo "   Unattended mode — continuing despite hygiene warnings."
    else
      echo "⛔ Pre-branch hygiene check failed. Halting."
      exit 1
    fi
  fi
fi

echo ""

while true; do
  # Fetch the next ready task
  TASK_JSON=$(get_next_unblocked) || {
    echo "✅ No more unblocked tasks. Queue complete."
    break
  }

  # Extract task fields
  TASK_ID=$(echo "$TASK_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
  TASK_TITLE=$(echo "$TASK_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['title'])")
  PLAN_FILE=$(echo "$TASK_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['plan_file'])")

  echo "▶️  Task: $TASK_TITLE ($TASK_ID)"
  echo "   Plan: $PLAN_FILE"

  # Merge verification
  check_dependency_merged "$TASK_ID"

  # Update queue state to in-progress
  mark_status "$TASK_ID" "in-progress"

  # Ensure the task has an isolated branch + worktree
  WORKTREE_DIR=$(ensure_worktree "$TASK_ID")

  # Invoke the agent (customize agent_invoke() above)
  set +e
  agent_invoke "$REPO_ROOT/$PLAN_FILE" "$WORKTREE_DIR"
  EXIT_CODE=$?
  set -e
  cd "$REPO_ROOT"

  # Update queue based on result
  if [ $EXIT_CODE -eq 0 ]; then
    echo "   ✅ Task completed successfully"
    mark_status "$TASK_ID" "done"
    promote_dependents
  else
    echo "   ❌ Task failed with exit code $EXIT_CODE"
    mark_status "$TASK_ID" "failed" "pipeline"
    echo ""
    echo "⛔ Orchestrator stopped. Failed task: $TASK_ID"
    echo "   Branch preserved at: $WORKTREE_DIR"
    exit 1
  fi

  echo ""
done

echo ""
echo "🏁 All tasks complete."
echo "   Run 'git worktree list' to see active worktrees."
echo "   Run 'aet-work cleanup' to remove merged worktrees."
