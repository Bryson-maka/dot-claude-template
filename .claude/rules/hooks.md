---
paths:
  - ".claude/hooks/**/*.sh"
---

# Hook Script Rules

When writing or modifying hook scripts:

- Always include `set -euo pipefail` at the top
- Read JSON input from stdin using `INPUT=$(cat)` - hooks receive tool context as JSON
- Use python3 for JSON parsing (jq may not be installed): `echo "$INPUT" | python3 -c "import sys,json; ..."`
- Use `$CLAUDE_PROJECT_DIR` for portable paths, never hardcode absolute paths
- Exit codes: 0=allow, 2=block (stderr fed to Claude), other=non-blocking error
- For PreToolUse hooks, use `hookSpecificOutput` JSON for fine-grained decisions (allow/deny/ask)
- For Stop hooks, always check `stop_hook_active` to prevent infinite loops
- Keep hooks fast (under 10s timeout for validators, under 300s for async tasks)
- Never modify files in hooks that could trigger other hooks (infinite loop risk)
- Test hooks manually: `echo '{"tool_input":{"command":"test"}}' | .claude/hooks/your-hook.sh`
