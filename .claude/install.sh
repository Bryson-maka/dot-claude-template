#!/usr/bin/env bash
# Install .claude/ template into a target project
# Usage: .claude/install.sh /path/to/target [--force]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE_DIR="$SCRIPT_DIR"
TARGET="${1:-}"
FORCE=false

if [[ "${2:-}" == "--force" ]]; then
  FORCE=true
fi

if [[ -z "$TARGET" ]]; then
  echo "Usage: $0 /path/to/target [--force]"
  echo ""
  echo "Copies the .claude/ template into a target project directory."
  echo "  --force  Overwrite existing .claude/ in target (preserves handoff/archive and session)"
  exit 1
fi

if [[ ! -d "$TARGET" ]]; then
  echo "Error: target directory does not exist: $TARGET"
  exit 1
fi

DEST="$TARGET/.claude"

if [[ -d "$DEST" ]] && [[ "$FORCE" != true ]]; then
  echo "Error: $DEST already exists. Use --force to overwrite."
  echo "  (handoff/archive/ and session/ contents are preserved with --force)"
  exit 1
fi

# Preserve target's handoff archive and session state if overwriting
TEMP_DIR=""
if [[ -d "$DEST" ]] && [[ "$FORCE" == true ]]; then
  TEMP_DIR="$(mktemp -d)"
  if [[ -d "$DEST/handoff/archive" ]]; then
    cp -r "$DEST/handoff/archive" "$TEMP_DIR/archive"
  fi
  if [[ -d "$DEST/session" ]]; then
    cp -r "$DEST/session" "$TEMP_DIR/session"
  fi
  rm -rf "$DEST"
fi

# Copy template (clean copy, not merge)
cp -r "$TEMPLATE_DIR" "$DEST"

# Clean project-specific artifacts
find "$DEST/session" -mindepth 1 ! -name '.gitkeep' -exec rm -rf {} + 2>/dev/null || true
find "$DEST/handoff/archive" -mindepth 1 ! -name '.gitkeep' -exec rm -rf {} + 2>/dev/null || true
find "$DEST" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
rm -f "$DEST/project_config.yaml"
rm -f "$DEST/settings.local.json"

# Ensure placeholder active.md is in place
cat > "$DEST/handoff/active.md" << 'HANDOFF'
# New Project

**Date**: -
**Status**: Template installed — run /cc-prime-cw to initialize

---

## Open Items

- Run /cc-prime-cw to discover project structure and load context
- Run /cc-execute to begin work

## Guardrails

- Do not modify .claude/hooks/ unless extending the security model
- Do not remove .gitkeep files from handoff or session directories
- Run /cc-conclude at end of session to generate a proper handoff
HANDOFF

# Restore preserved data if overwriting
if [[ -n "$TEMP_DIR" ]]; then
  if [[ -d "$TEMP_DIR/archive" ]]; then
    cp -r "$TEMP_DIR/archive/"* "$DEST/handoff/archive/" 2>/dev/null || true
  fi
  if [[ -d "$TEMP_DIR/session" ]]; then
    cp -r "$TEMP_DIR/session/"* "$DEST/session/" 2>/dev/null || true
  fi
  rm -rf "$TEMP_DIR"
fi

# Remove install script from the copy (template tool, not needed in target)
rm -f "$DEST/install.sh"

echo "Installed .claude/ template into $TARGET"
echo ""
echo "Next steps:"
echo "  cd $TARGET"
echo "  Start Claude Code, then run /cc-prime-cw"
