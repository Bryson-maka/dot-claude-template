#!/usr/bin/env bash
# PreToolUse hook: Protect secret/critical files from being written to
#
# Hook protocol (PreToolUse):
#   - Receives JSON on stdin: { "tool_name": "Edit"|"Write", "tool_input": { "file_path": "..." } }
#   - Exit 0 + JSON = decision
#   - Exit 2 = block with stderr message
#
# Philosophy: Secret and critical files are HARD DENIED for writes — the agent
# should never be able to modify credentials, keys, or security configuration.
# Unlike read hooks, write hooks also protect .git internals and the security
# config itself (.claude/settings.json) to prevent self-modification attacks.
#
#   Safe env templates (.env.example, .env.sample, .env.template) ARE writable
#   because the agent may legitimately scaffold them for the user.
#
# Customize protected patterns via .claude/security-policy.yaml

set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null || echo "")

if [ -z "$FILE_PATH" ]; then
  # Fail-closed: if we can't parse the path, block the write
  echo "validate-write: could not parse file_path from hook input — blocking write (fail-closed)" >&2
  exit 2
fi

# Extract just the filename for matching
FILENAME=$(basename "$FILE_PATH")

# Helper: emit deny decision (uses sys.argv, NOT shell interpolation in Python)
emit_deny() {
  local reason="$1"
  python3 -c "
import json, sys
print(json.dumps({
    'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'permissionDecision': 'deny',
        'permissionDecisionReason': sys.argv[1]
    }
}))
" "$reason" && exit 0
  # python3 failed — fall back to exit 2 (block) so files stay protected
  echo "Blocked: $reason (hook JSON emit failed)" >&2
  exit 2
}

# ============================================================================
# ALLOWED: Safe env templates (check BEFORE deny patterns)
# These contain structure/variable names but not actual secrets.
# The agent may scaffold these for the user.
# ============================================================================
SAFE_PATTERNS=(
  ".env.example"
  ".env.sample"
  ".env.template"
  ".env.defaults"
  ".env.test"
)

for safe in "${SAFE_PATTERNS[@]}"; do
  if [ "$FILENAME" = "$safe" ]; then
    exit 0
  fi
done

# ============================================================================
# HARD DENY: Secret files — never prompt, never allow writes
# ============================================================================

# .env files: deny ALL .env* files that weren't already allowed above.
# Safe patterns (.env.example, .env.sample, .env.template) are checked first
# and exit early. Everything else (.env, .env.local, .env.production, etc.) is denied.
if [ "$FILENAME" = ".env" ] || echo "$FILENAME" | grep -qE '^\.env\.'; then
  emit_deny "Secret file '$FILENAME' — writing to env files is denied; use .env.example for templates"
fi

# Credential/key files (pattern matches against filename)
SECRET_PATTERNS=(
  ".*\.pem"
  ".*\.key"
  ".*\.p12"
  ".*\.pfx"
  ".*_rsa"
  ".*_ed25519"
  "\.npmrc"
  "\.pypirc"
  "\.netrc"
  "credentials\.json"
  "serviceAccountKey.*\.json"
  "service-account.*\.json"
  "firebase-admin.*\.json"
  "gcp-credentials\.json"
)

for pattern in "${SECRET_PATTERNS[@]}"; do
  if echo "$FILENAME" | grep -qE "^${pattern}$"; then
    emit_deny "Credential/key file '$FILENAME' — writing to secret files is denied"
  fi
done

# ============================================================================
# HARD DENY: .git internal files — protect repository integrity
# ============================================================================
if echo "$FILE_PATH" | grep -qE '(^|/)\.git/'; then
  emit_deny "Git internal file '$FILE_PATH' — direct writes to .git/ are denied"
fi

# ============================================================================
# HARD DENY: Security config — prevent self-modification attacks
# ============================================================================
if echo "$FILE_PATH" | grep -qE '(^|/)\.claude/settings\.json$'; then
  emit_deny "Security config '.claude/settings.json' — writing to the security configuration is denied"
fi

# Security policy — prevents weakening safe_delete_paths or secret_files at runtime
if echo "$FILE_PATH" | grep -qE '(^|/)\.claude/security-policy\.yaml$'; then
  emit_deny "Security policy '.claude/security-policy.yaml' — writing to the security policy is denied"
fi

# ============================================================================
# Load project-specific secret patterns from security-policy.yaml
# ============================================================================
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
POLICY_FILE="$PROJECT_DIR/.claude/security-policy.yaml"

if [ -f "$POLICY_FILE" ]; then
  EXTRA_SECRETS=$(python3 -c "
import sys
try:
    import yaml
    with open(sys.argv[1]) as f:
        policy = yaml.safe_load(f) or {}
    for pattern in policy.get('secret_files', []):
        print(pattern)
except Exception:
    pass
" "$POLICY_FILE" 2>/dev/null || true)

  while IFS= read -r pattern; do
    [ -z "$pattern" ] && continue
    if echo "$FILENAME" | grep -qE "$pattern"; then
      emit_deny "Project-protected secret file '$FILENAME' (from security-policy.yaml) — writing denied"
    fi
  done <<< "$EXTRA_SECRETS"
fi

# ============================================================================
# ALLOW: Everything else
# ============================================================================
exit 0
