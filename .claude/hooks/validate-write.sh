#!/usr/bin/env bash
# PreToolUse hook: Protect secret/critical files and enforce directory-scoped writes
#
# Hook protocol (PreToolUse):
#   - Receives JSON on stdin: { "tool_name": "Edit"|"Write"|"NotebookEdit", "tool_input": { "file_path": "..." } }
#   - Exit 0 + JSON = decision
#   - Exit 2 = block with stderr message
#
# Enforcement layers (evaluated in order):
#   1. Safe env templates — allowed early (scaffolding use case)
#   2. Secret files — hard deny (.env*, credentials, keys)
#   3. .git internals — hard deny (repository integrity)
#   4. Security config — hard deny (self-modification protection)
#   5. Project-specific secrets — hard deny (from security-policy.yaml)
#   6. Directory scope — deny if outside allowed_write_directories (opt-in)
#   7. Allow — everything else passes
#
# Customize via .claude/security-policy.yaml:
#   - secret_files: additional regex patterns for secret file protection
#   - allowed_write_directories: directory-scoped write restriction (opt-in)

set -euo pipefail

INPUT=$(cat)

# Parse file_path from tool input — works for Edit, Write, and NotebookEdit
# NotebookEdit uses "notebook_path" field; Edit/Write use "file_path"
FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    ti = data.get('tool_input', {})
    path = ti.get('file_path') or ti.get('notebook_path', '')
    print(path)
except Exception:
    print('')
" 2>/dev/null || echo "")

if [ -z "$FILE_PATH" ]; then
  # Fail-closed: if we can't parse the path, block the write
  echo "validate-write: could not parse file_path from hook input — blocking write (fail-closed)" >&2
  exit 2
fi

# Extract just the filename for matching
FILENAME=$(basename "$FILE_PATH")

# Project directory for policy file resolution
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
LIB_DIR="$PROJECT_DIR/.claude/lib"
POLICY_FILE="$PROJECT_DIR/.claude/security-policy.yaml"

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
# DIRECTORY SCOPE: Deny writes outside allowed directories (opt-in)
#
# Uses path_validator.py for symlink-safe path resolution and directory
# matching. Feature is disabled when allowed_write_directories is empty
# or missing from security-policy.yaml.
# ============================================================================
if [ -f "$LIB_DIR/path_validator.py" ]; then
  DIR_CHECK=$(python3 "$LIB_DIR/path_validator.py" check-write "$FILE_PATH" "$PROJECT_DIR" 2>/dev/null || echo '{"allowed":true,"feature_enabled":false}')

  # Parse the result
  DIR_ALLOWED=$(echo "$DIR_CHECK" | python3 -c "import sys,json; r=json.load(sys.stdin); print('yes' if r.get('allowed',True) else 'no')" 2>/dev/null || echo "yes")
  DIR_ENABLED=$(echo "$DIR_CHECK" | python3 -c "import sys,json; r=json.load(sys.stdin); print('yes' if r.get('feature_enabled',False) else 'no')" 2>/dev/null || echo "no")

  if [ "$DIR_ENABLED" = "yes" ] && [ "$DIR_ALLOWED" = "no" ]; then
    DIR_REASON=$(echo "$DIR_CHECK" | python3 -c "import sys,json; print(json.load(sys.stdin).get('reason','Path outside allowed directories'))" 2>/dev/null || echo "Path outside allowed directories")
    emit_deny "Directory restriction: $DIR_REASON"
  fi
fi

# ============================================================================
# ALLOW: Everything else
# ============================================================================
exit 0
