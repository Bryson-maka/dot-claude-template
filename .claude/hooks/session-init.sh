#!/usr/bin/env bash
# SessionStart hook: Initialize session environment
#
# Hook protocol (SessionStart):
#   - Receives JSON on stdin: { "source": "startup"|"resume"|"clear", ... }
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

# Ensure session directory exists (guard against permission/disk errors)
mkdir -p "$SESSION_DIR" 2>/dev/null || true

# Set environment variables for the entire session via CLAUDE_ENV_FILE
# This is the ONLY hook event where CLAUDE_ENV_FILE is available
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export CC_SESSION_DIR=\"$SESSION_DIR\"" >> "$CLAUDE_ENV_FILE"
  echo "export CC_PROJECT_DIR=\"$PROJECT_DIR\"" >> "$CLAUDE_ENV_FILE"
  echo "export CC_SESSION_SOURCE=\"$SOURCE\"" >> "$CLAUDE_ENV_FILE"
fi

# On fresh startup, validate session state
if [ "$SOURCE" = "startup" ]; then
  # Run integrity check to catch template drift early
  VERIFY_CLI="$PROJECT_DIR/.claude/lib/verify_integrity.py"
  if [ -f "$VERIFY_CLI" ]; then
    INTEGRITY=$(python3 "$VERIFY_CLI" --json 2>/dev/null || echo "")
    if [ -n "$INTEGRITY" ]; then
      # Use Python to safely construct JSON output (avoids shell quoting issues)
      echo "$INTEGRITY" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if not data.get('passed', True):
    warnings = data.get('warnings', [])
    msg = 'INTEGRITY WARNING: Template drift detected. '
    msg += 'Run python3 .claude/lib/verify_integrity.py for details. '
    msg += 'Read .claude/SETTINGS_GUARD.md before modifying settings.json. '
    msg += 'Issues: ' + '; '.join(warnings)
    print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': msg}}))
" 2>/dev/null || true
    fi
  fi

  if [ -f "$STATE_FILE" ]; then
    # Check if state is from a previous session that wasn't concluded
    CONCLUDED=$(python3 -c "
import sys, json
with open(sys.argv[1]) as f:
    state = json.load(f)
print(state.get('concluded_at', 'null'))
" "$STATE_FILE" 2>/dev/null || echo "error")

    if [ "$CONCLUDED" = "null" ] && [ "$CONCLUDED" != "error" ]; then
      echo '{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "Previous session was not concluded. Run /cc-conclude to archive it, or /cc-prime-cw to start fresh."}}'
    fi
  fi
fi

# On resume, confirm state is intact
if [ "$SOURCE" = "resume" ]; then
  if [ ! -f "$STATE_FILE" ]; then
    echo '{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "No session state found. Run /cc-prime-cw to initialize."}}'
  fi
fi

exit 0
