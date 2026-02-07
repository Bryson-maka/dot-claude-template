#!/usr/bin/env bash
# SubagentStop hook: Validate subagent responses before accepting
#
# Hook protocol (SubagentStop):
#   - Receives JSON on stdin: { "agent_id": "...", "agent_type": "...",
#     "agent_transcript_path": "...", "stop_hook_active": bool }
#   - Can block via { "decision": "block", "reason": "..." }
#   - When blocked, the subagent is asked to continue/improve its response
#
# This hook checks that subagent responses meet minimum quality standards.
# Useful for catching subagents that return empty or too-short responses.

set -euo pipefail

INPUT=$(cat)

# Prevent infinite loops
STOP_ACTIVE=$(echo "$INPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(str(data.get('stop_hook_active', False)).lower())
" 2>/dev/null || echo "false")

if [ "$STOP_ACTIVE" = "true" ]; then
  exit 0
fi

# Check the subagent transcript for response quality
TRANSCRIPT_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('agent_transcript_path', ''))
" 2>/dev/null || echo "")

if [ -z "$TRANSCRIPT_PATH" ] || [ ! -f "$TRANSCRIPT_PATH" ]; then
  exit 0
fi

# Validate the last assistant message has substantive content
VALIDATION=$(python3 -c "
import json, sys

try:
    with open('$TRANSCRIPT_PATH') as f:
        lines = f.readlines()

    # Find last assistant message
    last_assistant = ''
    for line in reversed(lines):
        try:
            entry = json.loads(line.strip())
            if entry.get('role') == 'assistant':
                content = entry.get('content', '')
                if isinstance(content, list):
                    content = ' '.join(
                        c.get('text', '') for c in content if c.get('type') == 'text'
                    )
                last_assistant = content
                break
        except json.JSONDecodeError:
            continue

    word_count = len(last_assistant.split())
    if word_count < 10:
        print('too_short')
    else:
        print('ok')
except Exception:
    print('ok')
" 2>/dev/null || echo "ok")

if [ "$VALIDATION" = "too_short" ]; then
  echo '{"decision": "block", "reason": "Subagent response was too short (< 10 words). Please provide a more substantive analysis."}'
  exit 0
fi

exit 0
