#!/usr/bin/env bash
# Install or update .claude/ template into a target project
# Usage:
#   .claude/install.sh /path/to/target              # Fresh install (fails if .claude/ exists)
#   .claude/install.sh /path/to/target --force       # Full overwrite (preserves handoff/archive + session)
#   .claude/install.sh /path/to/target --update      # Smart update (only changed template files)
#   .claude/install.sh /path/to/target --update --dry # Preview update without writing
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE_DIR="$SCRIPT_DIR"
TARGET="${1:-}"
MODE="install"
DRY_RUN=false

# Parse flags (position-independent after target)
shift || true
for arg in "$@"; do
  case "$arg" in
    --force)  MODE="force" ;;
    --update) MODE="update" ;;
    --dry)    DRY_RUN=true ;;
  esac
done

if [[ -z "$TARGET" ]]; then
  cat <<'USAGE'
Usage: .claude/install.sh /path/to/target [--force | --update] [--dry]

Modes:
  (default)   Fresh install. Fails if .claude/ already exists.
  --force     Full overwrite. Preserves handoff/archive and session.
  --update    Smart update. Only overwrites changed template-owned files.
              Never touches handoff, session, project_config, or settings.
  --dry       Preview what --update would do without writing anything.

Template-owned (always updated):
  hooks/  lib/  skills/  status_lines/  SETTINGS_GUARD.md  TEMPLATE_VERSION

Config (diff shown, not auto-overwritten):
  settings.json  security-policy.yaml

Project data (never touched by --update):
  handoff/  session/  project_config.yaml  settings.local.json
USAGE
  exit 1
fi

if [[ ! -d "$TARGET" ]]; then
  echo "Error: target directory does not exist: $TARGET"
  exit 1
fi

DEST="$TARGET/.claude"

# ============================================================
# Mode: --update (smart incremental update)
# ============================================================
if [[ "$MODE" == "update" ]]; then
  if [[ ! -d "$DEST" ]]; then
    echo "Error: $DEST does not exist. Use install (without --update) for fresh setup."
    exit 1
  fi

  # Counters
  updated=0
  added=0
  skipped=0
  removed_from_template=0
  config_differs=0

  # Template-owned directories — safe to overwrite completely
  TEMPLATE_DIRS=(hooks lib skills status_lines)

  # Template-owned root files — safe to overwrite
  TEMPLATE_FILES=(SETTINGS_GUARD.md TEMPLATE_VERSION)

  # Config files — show diff, don't auto-overwrite
  CONFIG_FILES=(settings.json security-policy.yaml)

  echo "Updating $DEST from template..."
  echo ""

  # --- Update template-owned directories ---
  for dir in "${TEMPLATE_DIRS[@]}"; do
    src_dir="$TEMPLATE_DIR/$dir"
    dst_dir="$DEST/$dir"

    if [[ ! -d "$src_dir" ]]; then
      continue
    fi

    # Collect all files in template dir (excluding __pycache__, install.sh)
    while IFS= read -r -d '' src_file; do
      rel_path="${src_file#"$TEMPLATE_DIR/"}"

      # Skip __pycache__ and install.sh
      if [[ "$rel_path" == *__pycache__* ]]; then
        continue
      fi

      dst_file="$DEST/$rel_path"

      if [[ ! -f "$dst_file" ]]; then
        # New file in template
        if [[ "$DRY_RUN" == true ]]; then
          echo "  + $rel_path (new)"
        else
          mkdir -p "$(dirname "$dst_file")"
          cp "$src_file" "$dst_file"
          echo "  + $rel_path (new)"
        fi
        ((added++))
      elif ! diff -q "$src_file" "$dst_file" >/dev/null 2>&1; then
        # File differs — update it
        if [[ "$DRY_RUN" == true ]]; then
          echo "  ~ $rel_path (changed)"
        else
          cp "$src_file" "$dst_file"
          echo "  ~ $rel_path (changed)"
        fi
        ((updated++))
      else
        ((skipped++))
      fi
    done < <(find "$src_dir" -type f -print0 2>/dev/null)

    # Check for files in target that no longer exist in template
    if [[ -d "$dst_dir" ]]; then
      while IFS= read -r -d '' dst_file; do
        rel_path="${dst_file#"$DEST/"}"

        if [[ "$rel_path" == *__pycache__* ]]; then
          continue
        fi

        src_file="$TEMPLATE_DIR/$rel_path"
        if [[ ! -f "$src_file" ]]; then
          echo "  ? $rel_path (removed from template — review manually)"
          ((removed_from_template++))
        fi
      done < <(find "$dst_dir" -type f -print0 2>/dev/null)
    fi
  done

  # --- Update template-owned root files ---
  for file in "${TEMPLATE_FILES[@]}"; do
    src_file="$TEMPLATE_DIR/$file"
    dst_file="$DEST/$file"

    if [[ ! -f "$src_file" ]]; then
      continue
    fi

    if [[ ! -f "$dst_file" ]]; then
      if [[ "$DRY_RUN" == true ]]; then
        echo "  + $file (new)"
      else
        cp "$src_file" "$dst_file"
        echo "  + $file (new)"
      fi
      ((added++))
    elif ! diff -q "$src_file" "$dst_file" >/dev/null 2>&1; then
      if [[ "$DRY_RUN" == true ]]; then
        echo "  ~ $file (changed)"
      else
        cp "$src_file" "$dst_file"
        echo "  ~ $file (changed)"
      fi
      ((updated++))
    else
      ((skipped++))
    fi
  done

  # --- Check config files (diff only, no overwrite) ---
  for file in "${CONFIG_FILES[@]}"; do
    src_file="$TEMPLATE_DIR/$file"
    dst_file="$DEST/$file"

    if [[ ! -f "$src_file" ]] || [[ ! -f "$dst_file" ]]; then
      continue
    fi

    if ! diff -q "$src_file" "$dst_file" >/dev/null 2>&1; then
      echo ""
      echo "  ! $file differs from template (not auto-updated)"
      echo "    Review with: diff $dst_file $src_file"
      ((config_differs++))
    fi
  done

  # --- Clean __pycache__ in target ---
  if [[ "$DRY_RUN" != true ]]; then
    find "$DEST" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
  fi

  # --- Summary ---
  echo ""
  if [[ "$DRY_RUN" == true ]]; then
    echo "Dry run complete (no files written)."
  else
    echo "Update complete."
  fi
  echo "  Updated: $updated | Added: $added | Skipped (identical): $skipped"
  if [[ $removed_from_template -gt 0 ]]; then
    echo "  Removed from template: $removed_from_template (review manually)"
  fi
  if [[ $config_differs -gt 0 ]]; then
    echo "  Config files differ: $config_differs (not auto-updated — review above)"
  fi
  echo ""
  echo "Preserved: handoff/ session/ project_config.yaml settings.local.json"
  exit 0
fi

# ============================================================
# Mode: install / --force (existing behavior)
# ============================================================
if [[ -d "$DEST" ]] && [[ "$MODE" != "force" ]]; then
  echo "Error: $DEST already exists."
  echo "  Use --force to overwrite (preserves handoff/archive and session)"
  echo "  Use --update to smart-update only changed template files"
  exit 1
fi

# Preserve target's handoff archive and session state if overwriting
TEMP_DIR=""
if [[ -d "$DEST" ]] && [[ "$MODE" == "force" ]]; then
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

## Accomplished

- Template installed from dot-claude-template

## Open Items

### Blocking
- Run /cc-prime-cw to discover project structure and load context

### Deferred
- None

## Next Session

### Priorities
1. Run /cc-prime-cw to initialize context
2. Run /cc-execute to begin work

### Guardrails
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
