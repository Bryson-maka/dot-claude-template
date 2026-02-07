#!/usr/bin/env bash
# Stop hook: Session checkpoint when Claude finishes responding
#
# Hook protocol (Stop):
#   - Receives JSON on stdin with stop_hook_active flag
#   - Exit 0 = allow stop
#   - Exit 2 = force Claude to continue (use with caution)
#   - JSON { "decision": "block", "reason": "..." } = ask Claude to continue
#
# IMPORTANT: Check stop_hook_active to prevent infinite loops.
# If this hook blocks, Claude responds again, which triggers Stop again.
# The stop_hook_active flag is true when we're already in a stop-hook cycle.

set -euo pipefail

INPUT=$(cat)

# Prevent infinite loop - if we're already in a stop hook cycle, allow stop
STOP_HOOK_ACTIVE=$(echo "$INPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(str(data.get('stop_hook_active', False)).lower())
" 2>/dev/null || echo "false")

if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
  exit 0
fi

# Checkpoint: save a lightweight timestamp to session state
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
STATE_CLI="$PROJECT_DIR/.claude/lib/session_state.py"

if [ -f "$STATE_CLI" ]; then
  python3 "$STATE_CLI" log --type session_checkpoint --details "Auto-checkpoint on response complete" 2>/dev/null || true
fi

# Always allow stop (this is a non-blocking checkpoint)
exit 0
