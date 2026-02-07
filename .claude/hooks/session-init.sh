#!/usr/bin/env bash
# SessionStart hook: Initialize session environment
#
# Hook protocol (SessionStart):
#   - Receives JSON on stdin: { "source": "startup"|"resume"|"clear"|"compact", ... }
#   - Cannot block (informational only)
#   - Can write env vars to $CLAUDE_ENV_FILE (SessionStart exclusive feature)
#   - additionalContext in stdout is shown to Claude
#
# This hook ensures the session directory exists and sets up environment
# variables that all subsequent Bash commands can use.

set -euo pipefail

INPUT=$(cat)
SOURCE=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('source','unknown'))" 2>/dev/null || echo "unknown")

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
SESSION_DIR="$PROJECT_DIR/.claude/session"
STATE_FILE="$SESSION_DIR/state.json"

# Ensure session directory exists
mkdir -p "$SESSION_DIR"

# Set environment variables for the entire session via CLAUDE_ENV_FILE
# This is the ONLY hook event where CLAUDE_ENV_FILE is available
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export CC_SESSION_DIR=\"$SESSION_DIR\"" >> "$CLAUDE_ENV_FILE"
  echo "export CC_PROJECT_DIR=\"$PROJECT_DIR\"" >> "$CLAUDE_ENV_FILE"
  echo "export CC_SESSION_SOURCE=\"$SOURCE\"" >> "$CLAUDE_ENV_FILE"
fi

# On fresh startup, validate session state
if [ "$SOURCE" = "startup" ]; then
  if [ -f "$STATE_FILE" ]; then
    # Check if state is from a previous session that wasn't concluded
    CONCLUDED=$(python3 -c "
import json
with open('$STATE_FILE') as f:
    state = json.load(f)
print(state.get('concluded_at', 'null'))
" 2>/dev/null || echo "error")

    if [ "$CONCLUDED" = "null" ] && [ "$CONCLUDED" != "error" ]; then
      echo "{\"additionalContext\": \"Previous session was not concluded. Run /cc-conclude to archive it, or /cc-prime-cw to start fresh.\"}"
    fi
  fi
fi

# On resume, confirm state is intact
if [ "$SOURCE" = "resume" ]; then
  if [ ! -f "$STATE_FILE" ]; then
    echo "{\"additionalContext\": \"No session state found. Run /cc-prime-cw to initialize.\"}"
  fi
fi

exit 0
