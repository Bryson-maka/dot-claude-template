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

# Parse command and (if policy file exists) safe_delete_paths in one python3 call
# to reduce subprocess overhead.
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
POLICY_FILE="$PROJECT_DIR/.claude/security-policy.yaml"

PARSED=$(python3 -c "
import json, sys, os

# Parse command from hook JSON
raw = sys.argv[1]
try:
    data = json.loads(raw)
    command = data.get('tool_input', {}).get('command', '')
except Exception:
    command = ''

# Parse safe_delete_paths from security-policy.yaml (if it exists)
safe_delete = ''
policy_file = sys.argv[2]
if os.path.isfile(policy_file):
    try:
        import yaml
        with open(policy_file) as f:
            policy = yaml.safe_load(f) or {}
        paths = policy.get('safe_delete_paths', [])
        safe_delete = ' '.join(paths)
    except Exception:
        pass

# Output: first line = command, second line = safe_delete_paths
# Use a delimiter that won't appear in commands
print(command)
print('---SAFE_DELETE_SEPARATOR---')
print(safe_delete)
" "$INPUT" "$POLICY_FILE" 2>/dev/null || echo "")

COMMAND=$(echo "$PARSED" | sed -n '1,/^---SAFE_DELETE_SEPARATOR---$/{ /^---SAFE_DELETE_SEPARATOR---$/d; p; }')
SAFE_DELETE_PATHS=$(echo "$PARSED" | sed -n '/^---SAFE_DELETE_SEPARATOR---$/,$ { /^---SAFE_DELETE_SEPARATOR---$/d; p; }')

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
# Project-specific overrides (parsed above with command extraction)
# SAFE_DELETE_PATHS and POLICY_FILE are already set from the consolidated
# python3 invocation at the top of this script.
# ============================================================================

# ============================================================================
# TIER 1: BLOCKED - always denied, no user override
# MUST be checked BEFORE safe pass-through to prevent bypass via chaining
# (e.g., "git commit -m msg && rm -rf /").
# Catastrophic operations that are never correct in a development context.
# These are security-sensitive: we deny silently, never prompt.
#
# IMPORTANT: All security tiers check against the FULL command (all lines),
# not just CMD_PREFIX. This prevents multiline bypass where a destructive
# command is hidden on line 2+. CMD_PREFIX is only used for safe pass-through.
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
    exit $?
  fi
done

# ============================================================================
# SAFE PASS-THROUGH: git read operations and safe git writes
# Placed AFTER blocked tier so catastrophic patterns are always caught, but
# BEFORE ASK/WARN tiers to prevent false positives from heredoc content
# (e.g., commit messages mentioning "rm" would otherwise trigger ASK).
#
# IMPORTANT: Only applies to SIMPLE commands. If the command contains chaining
# operators (&&, ||, ;) after the git verb, it falls through to ASK/WARN tiers
# so the chained portion is properly evaluated.
# ============================================================================
if echo "$CMD_PREFIX" | grep -qE '^git (add|commit|status|diff|log|branch|show|stash|tag|remote|fetch|symbolic-ref|rev-parse|config --get) '; then
  # Check for chaining operators in the full command — if present, don't fast-path
  if ! echo "$COMMAND" | grep -qE '(&&|\|\||;)'; then
    exit 0
  fi
  # Also allow "git add ... && git commit ..." as a known-safe compound pattern
  if echo "$CMD_PREFIX" | grep -qE '^git add .+&& *git commit'; then
    if ! echo "$COMMAND" | grep -qE '&&.*&&|;|\|\|'; then
      exit 0
    fi
  fi
fi

# ============================================================================
# TIER 2: ASK - prompt user for confirmation
# Destructive but legitimate dev operations. The user sees the command and
# reason, then approves or rejects. This is the key UX improvement: instead
# of blocking routine dev ops like "rm -rf node_modules", we ask.
# ============================================================================

# File/directory deletion — check if it's a known safe-delete path first
if echo "$COMMAND" | grep -qE '\brm\b'; then
  # Extract the rm arguments (everything after rm and its flags) to check
  # safe paths against the target, not the entire command string.
  RM_ARGS=$(echo "$CMD_PREFIX" | sed -E 's/^.*\brm\b\s+(-[a-zA-Z]+\s+)*//')
  IS_SAFE_DELETE=false
  for safe_path in $SAFE_DELETE_PATHS; do
    if echo "$RM_ARGS" | grep -qF "$safe_path"; then
      IS_SAFE_DELETE=true
      break
    fi
  done

  if [ "$IS_SAFE_DELETE" = true ]; then
    emit_decision "allow" "Deleting known build artifact. Matched safe_delete_paths in security policy."
    exit $?
  else
    emit_decision "ask" "File deletion requested: $CMD_PREFIX"
    exit $?
  fi
fi

# Destructive git operations
if echo "$COMMAND" | grep -qE 'git (push --force|reset --hard|clean -f|checkout \.|restore \.|branch -D)'; then
  emit_decision "ask" "Destructive git operation: $CMD_PREFIX"
  exit $?
fi

# Consequential git writes (push, rebase, merge)
if echo "$COMMAND" | grep -qE 'git (push|rebase|merge|cherry-pick)'; then
  emit_decision "ask" "Git write operation requires confirmation: $CMD_PREFIX"
  exit $?
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
  if echo "$COMMAND" | grep -qF "$pattern"; then
    emit_decision "allow" "Warning: '$pattern' has external side effects. Confirm user intent before proceeding."
    exit $?
  fi
done

# ============================================================================
# TIER 4: ALLOW - pass through silently
# ============================================================================
exit 0
