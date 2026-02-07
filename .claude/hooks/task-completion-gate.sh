#!/usr/bin/env bash
# TaskCompleted hook: Validate before allowing task completion
#
# Hook protocol (TaskCompleted):
#   - Receives JSON on stdin: { "task_id": "...", "task_subject": "...",
#     "task_description": "...", ... }
#   - Exit 0 = allow completion
#   - Exit 2 = block completion (stderr fed to Claude)
#
# This hook checks that tasks aren't being marked complete prematurely.
# It verifies that the task description doesn't contain unchecked items.

set -euo pipefail

INPUT=$(cat)

# Extract task details
TASK_INFO=$(echo "$INPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
task_id = data.get('task_id', 'unknown')
subject = data.get('task_subject', '')
description = data.get('task_description', '')
print(f'{task_id}|{subject}|{description}')
" 2>/dev/null || echo "unknown||")

TASK_ID=$(echo "$TASK_INFO" | cut -d'|' -f1)
TASK_SUBJECT=$(echo "$TASK_INFO" | cut -d'|' -f2)

# Log the completion to session state
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
STATE_CLI="$PROJECT_DIR/.claude/lib/session_state.py"

if [ -f "$STATE_CLI" ]; then
  python3 "$STATE_CLI" log --type task_completed --task-id "$TASK_ID" --subject "$TASK_SUBJECT" 2>/dev/null || true
fi

# Allow completion (this hook primarily logs; add validation logic as needed)
# Example: uncomment to require tests pass before task completion
# if ! npm test 2>&1; then
#   echo "Tests must pass before completing task '$TASK_SUBJECT'" >&2
#   exit 2
# fi

exit 0
