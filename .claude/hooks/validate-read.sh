#!/usr/bin/env bash
# PreToolUse hook: Protect secret files from being read
#
# Hook protocol (PreToolUse):
#   - Receives JSON on stdin: { "tool_name": "Read", "tool_input": { "file_path": "..." } }
#   - Exit 0 + JSON = decision
#   - Exit 2 = block with stderr message
#
# Philosophy: Secret files are HARD DENIED — the agent should never prompt
# the user for access to credentials. Prompting could catch humans off guard
# into approving. Instead, the agent should:
#   - Read .env.sample or .env.example for variable names/structure
#   - Test credentials by running actual API calls (e.g., health check endpoints)
#   - Never need the raw secret values
#
# Customize protected patterns via .claude/security-policy.yaml

set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null || echo "")

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Extract just the filename for matching
FILENAME=$(basename "$FILE_PATH")

# Helper: emit deny decision
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
" "$reason"
  exit 0
}

# ============================================================================
# ALLOWED: Safe env templates (check BEFORE deny patterns)
# These contain structure/variable names but not actual secrets.
# ============================================================================
SAFE_PATTERNS=(
  ".env.sample"
  ".env.example"
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
# HARD DENY: Secret files — never prompt, never allow
# These are silently blocked. The agent should use .env.sample for structure
# and test credentials via API calls, not by reading raw values.
# ============================================================================

# .env files: deny ALL .env* files that weren't already allowed above.
# Safe patterns (.env.sample, .env.example, .env.template, .env.defaults, .env.test)
# are checked first and exit early. Everything else (.env, .env.local, .env.production,
# .env.dev, .env.anything) is denied — no enumeration needed.
if [ "$FILENAME" = ".env" ] || echo "$FILENAME" | grep -qE '^\.env\.'; then
  emit_deny "Secret file '$FILENAME' — read .env.sample for structure, test credentials via API calls"
fi

# Credential/key files (pattern matches against filename)
SECRET_PATTERNS=(
  "credentials\.json"
  "serviceAccountKey.*\.json"
  ".*\.pem"
  ".*\.key"
  ".*_rsa"
  ".*_ed25519"
  "\.npmrc"
  "\.pypirc"
  "\.netrc"
)

# Public keys are NOT secrets — allow them before checking secret patterns
if echo "$FILENAME" | grep -qE '\.(pub)$'; then
  exit 0
fi

for pattern in "${SECRET_PATTERNS[@]}"; do
  if echo "$FILENAME" | grep -qE "^${pattern}$"; then
    emit_deny "Credential file '$FILENAME' — never read secrets directly"
  fi
done

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
      emit_deny "Project-protected secret file '$FILENAME' (from security-policy.yaml)"
    fi
  done <<< "$EXTRA_SECRETS"
fi

# ============================================================================
# ALLOW: Everything else
# ============================================================================
exit 0
