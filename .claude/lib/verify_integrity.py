#!/usr/bin/env python3
"""
Template Integrity Verifier

Validates that the .claude/ directory hasn't drifted from template requirements.
Catches the specific failure modes documented in HARDENING_BRIEF.md:
  1. Read(.env*) deny rule injection in settings.json
  2. Hook registration stripped from settings.json
  3. validate-bash.sh tier ordering regression
  4. Missing security-policy.yaml

Usage:
    python3 .claude/lib/verify_integrity.py          # Exit 0 if clean, 1 if warnings
    python3 .claude/lib/verify_integrity.py --json    # Machine-readable output

Called by session-init.sh on SessionStart to catch drift early.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# Import shared utility
try:
    from . import get_project_root
except ImportError:
    def get_project_root() -> Path:
        current = Path.cwd()
        for parent in [current] + list(current.parents):
            if (parent / '.claude').is_dir():
                return parent
        return current


def verify_integrity(base_dir: Path | None = None) -> list[str]:
    """Run all integrity checks.

    Returns list of warning strings. Empty list = all checks passed.
    """
    if base_dir is None:
        base_dir = get_project_root()

    claude_dir = base_dir / '.claude'
    warnings: list[str] = []

    # Check 1: settings.json exists and has required structure
    settings_path = claude_dir / 'settings.json'
    if not settings_path.exists():
        warnings.append("CRITICAL: .claude/settings.json is missing")
        return warnings  # Can't check further without settings

    try:
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        warnings.append(f"CRITICAL: .claude/settings.json is invalid JSON: {e}")
        return warnings

    # Check 2: Deny list does NOT contain Read(.env patterns
    deny_list = settings.get('permissions', {}).get('deny', [])
    for rule in deny_list:
        if 'Read(' in rule and '.env' in rule:
            warnings.append(
                f"DRIFT: deny rule '{rule}' blocks safe files like .env.example. "
                "Remove it — .env protection is handled by validate-read.sh hook "
                "which allows .env.example/.env.sample/.env.template."
            )

    # Check 3: Required hook registrations exist
    hooks = settings.get('hooks', {})

    # 3a: PreToolUse must have both Bash and Read matchers
    pre_tool_use = hooks.get('PreToolUse', [])
    pre_matchers = {entry.get('matcher', '') for entry in pre_tool_use}

    if 'Bash' not in pre_matchers:
        warnings.append(
            "DRIFT: PreToolUse hook for 'Bash' (validate-bash.sh) is missing from settings.json. "
            "This disables the 4-tier security model for command validation."
        )
    if 'Read' not in pre_matchers:
        warnings.append(
            "DRIFT: PreToolUse hook for 'Read' (validate-read.sh) is missing from settings.json. "
            "This disables secret file protection — .env files will be readable."
        )

    # 3b: PostToolUse must have Edit|Write matcher
    post_tool_use = hooks.get('PostToolUse', [])
    has_edit_write = any(
        'Edit' in entry.get('matcher', '') or 'Write' in entry.get('matcher', '')
        for entry in post_tool_use
    )
    if not has_edit_write:
        warnings.append(
            "DRIFT: PostToolUse hook for 'Edit|Write' (track-file-changes.sh) is missing. "
            "File modification tracking is disabled."
        )

    # 3c: SessionStart hook
    if not hooks.get('SessionStart'):
        warnings.append("DRIFT: SessionStart hook (session-init.sh) is missing.")

    # Check 4: All referenced hook scripts exist and are executable
    for event_name, event_hooks in hooks.items():
        for entry in event_hooks:
            for hook in entry.get('hooks', []):
                cmd = hook.get('command', '')
                # Resolve $CLAUDE_PROJECT_DIR to actual base_dir
                resolved = cmd.replace('"$CLAUDE_PROJECT_DIR"', str(base_dir))
                resolved = resolved.replace('$CLAUDE_PROJECT_DIR', str(base_dir))
                script_path = Path(resolved)
                if script_path.suffix in ('.sh', '.py') or '/hooks/' in str(script_path):
                    if not script_path.exists():
                        warnings.append(
                            f"MISSING: Hook script '{script_path.name}' referenced in "
                            f"settings.json [{event_name}] does not exist at {script_path}"
                        )
                    elif script_path.suffix == '.sh' and not os.access(script_path, os.X_OK):
                        warnings.append(
                            f"PERMISSIONS: Hook script '{script_path.name}' is not executable. "
                            f"Run: chmod +x {script_path}"
                        )

    # Check 5: security-policy.yaml exists
    policy_path = claude_dir / 'security-policy.yaml'
    if not policy_path.exists():
        warnings.append(
            "MISSING: .claude/security-policy.yaml — validate-bash.sh can't read "
            "safe_delete_paths (every 'rm' will trigger ASK even for __pycache__)."
        )

    # Check 6: validate-bash.sh tier ordering (blocked before safe)
    bash_hook = claude_dir / 'hooks' / 'validate-bash.sh'
    if bash_hook.exists():
        try:
            content = bash_hook.read_text(encoding='utf-8')
            # Find positions of blocked check and safe pass-through
            blocked_pos = _find_pattern_position(content, r'BLOCKED_PATTERNS|TIER 1.*BLOCKED')
            safe_pos = _find_pattern_position(content, r'SAFE PASS-THROUGH')

            if blocked_pos is not None and safe_pos is not None:
                if safe_pos < blocked_pos:
                    warnings.append(
                        "SECURITY: validate-bash.sh checks safe pass-through BEFORE blocked patterns. "
                        "This allows bypass via chaining (e.g., 'git add . && rm -rf /'). "
                        "Blocked patterns MUST be checked first."
                    )
        except IOError:
            pass

    # Check 7: Required lib scripts exist
    required_libs = ['session_state.py', 'project_analyzer.py']
    for lib_name in required_libs:
        lib_path = claude_dir / 'lib' / lib_name
        if not lib_path.exists():
            warnings.append(f"MISSING: .claude/lib/{lib_name}")

    return warnings


def _find_pattern_position(text: str, pattern: str) -> int | None:
    """Find the character position of a regex pattern in text."""
    match = re.search(pattern, text)
    return match.start() if match else None


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Verify .claude/ template integrity')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--base-dir', type=Path, help='Project root directory')
    args = parser.parse_args()

    warnings = verify_integrity(args.base_dir)

    if args.json:
        print(json.dumps({
            "passed": len(warnings) == 0,
            "warnings": warnings,
            "checks_run": 7,
        }))
    elif warnings:
        for w in warnings:
            print(f"  [{w.split(':')[0]}] {w}", file=sys.stderr)
        print(f"\n{len(warnings)} integrity issue(s) found.", file=sys.stderr)
    else:
        print("All integrity checks passed.", file=sys.stderr)

    sys.exit(0 if not warnings else 1)


if __name__ == '__main__':
    main()
