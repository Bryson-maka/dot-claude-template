#!/usr/bin/env bash
# PostToolUseFailure hook: Notify Claude when a Bash command was denied or failed
#
# Hook protocol (PostToolUseFailure):
#   - Receives JSON on stdin: { "tool_name": "Bash", "tool_input": {...},
#     "error": "...", "is_interrupt": false }
#   - Cannot block (informational only, tool already failed)
#   - additionalContext in stdout is shown to Claude
#
# This hook closes the feedback loop for ASK-tier commands:
#   PreToolUse emits "ask" → user sees permission dialog → user denies →
#   PostToolUseFailure fires → this hook tells Claude what happened.
#
# Without this hook, Claude has no context about WHY a command failed
# after an ASK decision was denied by the user.

set -euo pipefail

# Debug logging: capture Python errors to session log instead of /dev/null
_log_hook_error() {
  if [ -d "${CC_SESSION_DIR:-}" ]; then
    python3 -c "
import json, sys, datetime
entry = {'ts': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'hook': 'notify-bash-failure', 'error': sys.argv[1]}
print(json.dumps(entry))
" "$1" >> "$CC_SESSION_DIR/hook-debug.jsonl" 2>/dev/null
  fi
}

INPUT=$(cat)

_STDERR_FILE=$(mktemp 2>/dev/null || echo "/tmp/cc-hook-$$")
python3 -c "
import json, sys

data = json.load(sys.stdin)
command = data.get('tool_input', {}).get('command', '')
error = data.get('error', '')
is_interrupt = data.get('is_interrupt', False)

# Don't add noise for user interrupts — Claude already knows
if is_interrupt:
    sys.exit(0)

# Extract first line of command for readable context
cmd_short = command.split('\n')[0][:200] if command else 'unknown'

# Build context message — guard against non-string error values
error_str = str(error) if error else ''
msg = f'Bash command was denied or failed: {cmd_short}'
if any(kw in error_str.lower() for kw in ('permission', 'denied', 'rejected')):
    msg = f'User DENIED the command: {cmd_short}. Do not retry without explicit instruction.'
elif error_str:
    msg = f'Command failed ({cmd_short}): {error_str[:200]}'

output = {
    'hookSpecificOutput': {
        'hookEventName': 'PostToolUseFailure',
        'additionalContext': msg
    }
}
print(json.dumps(output))
" <<< "$INPUT" 2>"$_STDERR_FILE" || {
  _log_hook_error "$(cat "$_STDERR_FILE" 2>/dev/null)"
  true
}
rm -f "$_STDERR_FILE" 2>/dev/null

exit 0
