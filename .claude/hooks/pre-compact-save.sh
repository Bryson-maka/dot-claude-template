#!/usr/bin/env bash
# PreCompact hook: Save session state before context window is trimmed
#
# Hook protocol (PreCompact):
#   - Receives JSON on stdin: { "trigger": "manual"|"auto", ... }
#   - Cannot block
#   - No feedback mechanism (fire-and-forget)
#
# When Claude's context gets too large, it compacts (summarizes and trims).
# This hook ensures session state is preserved before that happens,
# because the model may lose track of what it was doing.

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
STATE_CLI="$PROJECT_DIR/.claude/lib/session_state.py"

if [ -f "$STATE_CLI" ]; then
  python3 "$STATE_CLI" log --type session_checkpoint --details "Pre-compaction checkpoint - context being trimmed" 2>/dev/null || true
fi

exit 0
