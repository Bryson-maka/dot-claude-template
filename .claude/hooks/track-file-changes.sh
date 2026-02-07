#!/usr/bin/env bash
# PostToolUse hook: Track file modifications to session state
#
# Hook protocol (PostToolUse):
#   - Receives JSON on stdin with tool_input and tool_result
#   - Cannot block (informational only)
#   - stdout feedback is shown to Claude as context
#
# This hook records which files were edited/written so cc-conclude
# has an accurate list of changes for commit message generation.

set -euo pipefail

INPUT=$(cat)

# Extract the file path from tool_input
FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
ti = data.get('tool_input', {})
# Edit tool uses 'file_path', Write tool uses 'file_path'
print(ti.get('file_path', ''))
" 2>/dev/null || echo "")

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Log to session state if the CLI is available
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
STATE_CLI="$PROJECT_DIR/.claude/lib/session_state.py"

if [ -f "$STATE_CLI" ]; then
  python3 "$STATE_CLI" log --type file_modified --file "$FILE_PATH" 2>/dev/null || true
fi

exit 0
