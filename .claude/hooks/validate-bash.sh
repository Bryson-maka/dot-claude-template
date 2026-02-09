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
# Four security tiers:
#   1. BLOCKED - always denied (catastrophic/irreversible system-level ops)
#   2. ASK     - user prompted for confirmation (destructive but legitimate dev ops)
#              NOTE: permissionDecisionReason is shown to the USER, not Claude.
#              We emit additionalContext alongside "ask" so Claude knows what was
#              flagged regardless of whether the user accepts or denies.
#   3. WARN    - allowed with context warning to Claude (side-effect commands)
#   4. ALLOW   - silent pass-through (everything else)
#
# Customize tiers via .claude/security-policy.yaml (see template for format).

set -euo pipefail

# Read the tool input from stdin
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null || echo "")

if [ -z "$COMMAND" ]; then
  exit 0
fi

# Helper: emit structured decision and exit
#
# For "ask" decisions, permissionDecisionReason is shown to the USER in the
# permission dialog, but NOT to Claude. We include additionalContext so Claude
# knows what was flagged regardless of whether the user accepts or denies.
# For "deny" decisions, permissionDecisionReason IS shown to Claude directly.
emit_decision() {
  local decision="$1"
  local reason="$2"
  python3 -c "
import json, sys
decision = sys.argv[1]
reason = sys.argv[2]
hso = {
    'hookEventName': 'PreToolUse',
    'permissionDecision': decision,
    'permissionDecisionReason': reason
}
# For 'ask' decisions, emit additionalContext so Claude knows what
# was flagged. The user sees the reason in the permission dialog; Claude
# sees additionalContext regardless of accept/deny outcome.
# For 'allow' decisions with a reason, emit it as context so Claude is
# informed (e.g., WARN tier, safe-delete downgrades).
if decision == 'ask':
    hso['additionalContext'] = '[ASK] ' + reason + '. User was prompted to accept or deny.'
elif decision == 'allow' and reason:
    hso['additionalContext'] = reason
print(json.dumps({'hookSpecificOutput': hso}))
" "$decision" "$reason" && exit 0
  # python3 failed — fail-closed for deny/ask, fail-open for allow
  if [ "$decision" = "allow" ]; then
    exit 0
  fi
  echo "Blocked: $reason (hook JSON emit failed)" >&2
  exit 2
}

# Extract command prefix (first line, max 200 chars) to avoid false positives
# from patterns inside heredoc content, commit messages, or quoted strings.
CMD_PREFIX=$(echo "$COMMAND" | head -1 | cut -c1-200)

# ============================================================================
# Load project-specific overrides from security-policy.yaml (if exists)
# ============================================================================
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
POLICY_FILE="$PROJECT_DIR/.claude/security-policy.yaml"

# Parse policy file for safe_delete_paths (space-separated list)
SAFE_DELETE_PATHS=""
if [ -f "$POLICY_FILE" ]; then
  SAFE_DELETE_PATHS=$(python3 -c "
import sys
try:
    import yaml
    with open(sys.argv[1]) as f:
        policy = yaml.safe_load(f) or {}
    paths = policy.get('safe_delete_paths', [])
    print(' '.join(paths))
except Exception:
    print('')
" "$POLICY_FILE" 2>/dev/null || echo "")
fi

# ============================================================================
# TIER 1: BLOCKED - always denied, no user override
# MUST be checked BEFORE safe pass-through to prevent bypass via chaining
# (e.g., "git commit -m msg && rm -rf /").
# Catastrophic operations that are never correct in a development context.
# These are security-sensitive: we deny silently, never prompt.
#
# IMPORTANT: Blocked patterns are checked against the FULL command (all lines),
# not just CMD_PREFIX. This prevents multiline bypass where a destructive
# command is hidden on line 2+. Only ASK/WARN tiers use CMD_PREFIX.
# ============================================================================
BLOCKED_PATTERNS=(
  "rm\s+-rf\s+/( |$)"       # root filesystem only (anchored, whitespace-flexible)
  "rm\s+-rf\s+~( |$)"       # home directory
  "rm\s+-rf\s+\\\$HOME"     # home directory via variable
  "> /dev/sda"
  "mkfs\."
  "dd if="
  ":\(\)\{.*\|.*&\}"        # fork bomb
  "chmod\s+-R\s+777\s+/"
  "curl .+\| *(ba)?sh\b"    # pipe to shell (word-bounded)
  "wget .+\| *(ba)?sh\b"    # pipe to shell
)

for pattern in "${BLOCKED_PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qE "$pattern"; then
    emit_decision "deny" "Blocked: catastrophic pattern — this is never allowed"
  fi
done

# ============================================================================
# SAFE PASS-THROUGH: git read operations and safe git writes
# Placed AFTER blocked tier so catastrophic patterns are always caught, but
# BEFORE ASK/WARN tiers to prevent false positives from heredoc content
# (e.g., commit messages mentioning "rm" would otherwise trigger ASK).
# ============================================================================
if echo "$CMD_PREFIX" | grep -qE '^git (add|commit|status|diff|log|branch|show|stash|tag|remote|fetch|symbolic-ref|rev-parse|config --get) '; then
  exit 0
fi
# Chained git add && git commit patterns
if echo "$CMD_PREFIX" | grep -qE '^git add .+&& *git commit'; then
  exit 0
fi

# ============================================================================
# TIER 2: ASK - prompt user for confirmation
# Destructive but legitimate dev operations. The user sees the command and
# reason, then approves or rejects. This is the key UX improvement: instead
# of blocking routine dev ops like "rm -rf node_modules", we ask.
# ============================================================================

# File/directory deletion — check if it's a known safe-delete path first
if echo "$CMD_PREFIX" | grep -qE '\brm\b'; then
  # Check if rm target is a known safe path (downgrade to WARN)
  IS_SAFE_DELETE=false
  for safe_path in $SAFE_DELETE_PATHS; do
    if echo "$CMD_PREFIX" | grep -qF "$safe_path"; then
      IS_SAFE_DELETE=true
      break
    fi
  done

  if [ "$IS_SAFE_DELETE" = true ]; then
    emit_decision "allow" "Deleting known build artifact. Matched safe_delete_paths in security policy."
  else
    emit_decision "ask" "File deletion requested: $CMD_PREFIX"
  fi
fi

# Destructive git operations
if echo "$CMD_PREFIX" | grep -qE 'git (push --force|reset --hard|clean -f|checkout \.|restore \.|branch -D)'; then
  emit_decision "ask" "Destructive git operation: $CMD_PREFIX"
fi

# Consequential git writes (push, rebase, merge)
if echo "$CMD_PREFIX" | grep -qE 'git (push|rebase|merge|cherry-pick)'; then
  emit_decision "ask" "Git write operation requires confirmation: $CMD_PREFIX"
fi

# ============================================================================
# TIER 3: WARN - allowed but Claude receives context
# Commands with side effects that should proceed but Claude should be aware of.
# ============================================================================
WARNING_PATTERNS=(
  "npm publish"
  "docker push"
  "pip install"
)

for pattern in "${WARNING_PATTERNS[@]}"; do
  if echo "$CMD_PREFIX" | grep -qF "$pattern"; then
    emit_decision "allow" "Warning: '$pattern' has external side effects. Confirm user intent before proceeding."
  fi
done

# ============================================================================
# TIER 4: ALLOW - pass through silently
# ============================================================================
exit 0
