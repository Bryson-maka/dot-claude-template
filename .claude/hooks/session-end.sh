#!/usr/bin/env bash
# SessionEnd hook: Archive session when Claude Code exits
#
# Hook protocol (SessionEnd):
#   - Receives JSON on stdin: { "reason": "clear"|"logout"|"prompt_input_exit"|"other", ... }
#   - Cannot block
#   - No feedback mechanism (fire-and-forget)
#
# This hook logs the session end event. Full archival happens via /cc-conclude,
# but this ensures we always record when a session ended even if the user
# just closes the terminal.

set -euo pipefail

INPUT=$(cat)
REASON=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('reason','unknown'))" 2>/dev/null || echo "unknown")

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
STATE_CLI="$PROJECT_DIR/.claude/lib/session_state.py"

if [ -f "$STATE_CLI" ]; then
  python3 "$STATE_CLI" log --type session_ended --details "Session ended: $REASON" 2>/dev/null || true
fi

exit 0
