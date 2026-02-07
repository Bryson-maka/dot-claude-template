#!/usr/bin/env bash
# PreToolUse hook: Validate Bash commands before execution
#
# Hook protocol (PreToolUse):
#   - Receives JSON on stdin: { "tool_name": "Bash", "tool_input": { "command": "..." } }
#   - Exit 0 = allow (no output needed)
#   - Exit 2 = block (stderr message fed to Claude as context)
#   - JSON stdout with hookSpecificOutput for fine-grained decisions:
#     { "hookSpecificOutput": {
#         "hookEventName": "PreToolUse",
#         "permissionDecision": "allow" | "deny" | "ask",
#         "permissionDecisionReason": "explanation"
#     }}
#
# This is a teaching example. Customize the blocked patterns for your project.

set -euo pipefail

# Read the tool input from stdin
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null || echo "")

if [ -z "$COMMAND" ]; then
  exit 0
fi

# --- Blocked patterns ---
# Destructive operations that should never run automatically
BLOCKED_PATTERNS=(
  "rm -rf /"
  "rm -rf ~"
  "rm -rf \$HOME"
  "> /dev/sda"
  "mkfs\."
  "dd if="
  ":(){:|:&};:"
  "chmod -R 777 /"
  "curl .+\| *sh"
  "wget .+\| *sh"
)

for pattern in "${BLOCKED_PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qE "$pattern"; then
    # Use hookSpecificOutput for structured deny (preferred over exit 2)
    python3 -c "
import json
print(json.dumps({
    'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'permissionDecision': 'deny',
        'permissionDecisionReason': 'Blocked: command matches dangerous pattern: $pattern'
    }
}))
"
    exit 0
  fi
done

# --- Warning patterns (allow but inform Claude) ---
# These are allowed but Claude receives a warning via stdout
WARNING_PATTERNS=(
  "git push"
  "npm publish"
  "docker push"
  "pip install"
)

for pattern in "${WARNING_PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qF "$pattern"; then
    # Output context that Claude will see (non-blocking)
    echo "{\"additionalContext\": \"Warning: This command ($pattern) has side effects. Ensure user has approved.\"}"
    exit 0
  fi
done

# Allow everything else
exit 0
