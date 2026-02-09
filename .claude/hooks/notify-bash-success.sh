#!/usr/bin/env bash
# PostToolUse hook: Provide context to Claude after Bash commands
#
# Hook protocol (PostToolUse):
#   - Receives JSON on stdin: { "tool_name": "Bash", "tool_input": {...},
#     "tool_response": {...} }
#   - Cannot block (informational only, tool already ran)
#   - additionalContext in stdout is shown to Claude
#
# This hook closes the feedback loop for ASK-tier commands that succeed:
#   PreToolUse emits "ask" + additionalContext → user accepts → tool runs →
#   PostToolUse fires → this hook confirms what happened so Claude can
#   acknowledge the action to the user.
#
# Only emits context for commands that produce no output (like rm, mv, mkdir)
# where Claude would otherwise have nothing to report back.

set -euo pipefail

# Debug logging: capture Python errors to session log instead of /dev/null
_log_hook_error() {
  if [ -d "${CC_SESSION_DIR:-}" ]; then
    python3 -c "
import json, sys, datetime
entry = {'ts': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'hook': 'notify-bash-success', 'error': sys.argv[1]}
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
response = data.get('tool_response', {})

# Get the response text — tool_response structure varies
resp_text = ''
if isinstance(response, dict):
    resp_text = response.get('stdout', '') or response.get('output', '') or ''
elif isinstance(response, str):
    resp_text = response

# Only emit context for commands that produced no meaningful output
# (like rm, mv, mkdir, cp, chmod) — other commands already have output
# that Claude can reference.
cmd_short = command.split('\n')[0][:200] if command else ''
silent_commands = ['rm ', 'rm\t', 'mv ', 'mkdir ', 'cp ', 'chmod ', 'touch ']
is_silent_cmd = any(cmd_short.lstrip().startswith(prefix) for prefix in silent_commands)

if is_silent_cmd and len(resp_text.strip()) == 0:
    output = {
        'hookSpecificOutput': {
            'hookEventName': 'PostToolUse',
            'additionalContext': 'Command completed successfully: ' + cmd_short + '. Acknowledge this to the user.'
        }
    }
    print(json.dumps(output))
" <<< "$INPUT" 2>"$_STDERR_FILE" || {
  _log_hook_error "$(cat "$_STDERR_FILE" 2>/dev/null)"
  true
}
rm -f "$_STDERR_FILE" 2>/dev/null

exit 0
