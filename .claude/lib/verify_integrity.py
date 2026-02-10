#!/usr/bin/env python3
"""
Template Integrity Verifier

Validates that the .claude/ directory hasn't drifted from template requirements.
Checks security settings, hook registrations, tier ordering, and documentation sync.

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


CHECKS_RUN = 0


def verify_integrity(base_dir: Path | None = None) -> list[str]:
    """Run all integrity checks.

    Returns list of warning strings. Empty list = all checks passed.
    """
    global CHECKS_RUN
    CHECKS_RUN = 0

    if base_dir is None:
        base_dir = get_project_root()

    claude_dir = base_dir / '.claude'
    warnings: list[str] = []

    # Check 1: settings.json exists and has required structure
    CHECKS_RUN += 1
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

    # Check 2: $schema present for IDE validation
    CHECKS_RUN += 1
    if '$schema' not in settings:
        warnings.append(
            "MISSING: $schema key not set in settings.json. "
            "Add '\"$schema\": \"https://json.schemastore.org/claude-code-settings.json\"' "
            "for IDE validation and autocompletion."
        )

    # Check 3: disableBypassPermissionsMode is set
    CHECKS_RUN += 1
    perms = settings.get('permissions', {})
    if perms.get('disableBypassPermissionsMode') != 'disable':
        warnings.append(
            "SECURITY: disableBypassPermissionsMode is not set to 'disable'. "
            "The entire security model can be bypassed with --dangerously-skip-permissions."
        )

    # Check 4: Deny list does NOT contain Read(.env patterns
    CHECKS_RUN += 1
    deny_list = perms.get('deny', [])
    for rule in deny_list:
        if 'Read(' in rule and '.env' in rule:
            warnings.append(
                f"DRIFT: deny rule '{rule}' blocks safe files like .env.example. "
                "Remove it — .env protection is handled by validate-read.sh hook "
                "which allows .env.example/.env.sample/.env.template."
            )

    # Check 5: No deny/ask conflicts (deny takes precedence, making ask patterns dead)
    CHECKS_RUN += 1
    ask_list = perms.get('ask', [])
    for deny_rule in deny_list:
        deny_pattern = deny_rule.replace('Bash(', '').rstrip(')*')
        for ask_rule in ask_list:
            ask_pattern = ask_rule.replace('Bash(', '').rstrip(')*')
            if deny_pattern and ask_pattern and deny_pattern in ask_pattern:
                warnings.append(
                    f"CONFLICT: deny rule '{deny_rule}' overrides ask rule '{ask_rule}'. "
                    "Deny takes absolute precedence — the ask prompt will never fire."
                )

    # Check 6: Required hook registrations exist
    CHECKS_RUN += 1
    hooks = settings.get('hooks', {})

    # 6a: PreToolUse must have Bash, Read, and Edit|Write matchers
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
    has_write_hook = any(
        'Edit' in entry.get('matcher', '') or 'Write' in entry.get('matcher', '')
        for entry in pre_tool_use
    )
    if not has_write_hook:
        warnings.append(
            "DRIFT: PreToolUse hook for 'Edit|Write|NotebookEdit' (validate-write.sh) "
            "is missing. Secret files are unprotected from writes."
        )
    else:
        # Verify NotebookEdit is included in the write matcher
        has_notebook = any(
            'NotebookEdit' in entry.get('matcher', '')
            for entry in pre_tool_use
            if 'Edit' in entry.get('matcher', '') or 'Write' in entry.get('matcher', '')
        )
        if not has_notebook:
            warnings.append(
                "DRIFT: PreToolUse write hook matcher does not include 'NotebookEdit'. "
                "Notebook edits bypass secret file protection and directory restrictions. "
                "Update matcher to 'Edit|Write|NotebookEdit'."
            )

    # 6b: PostToolUse must have Edit|Write|NotebookEdit matcher
    post_tool_use = hooks.get('PostToolUse', [])
    has_edit_write = any(
        'Edit' in entry.get('matcher', '') or 'Write' in entry.get('matcher', '')
        for entry in post_tool_use
    )
    if not has_edit_write:
        warnings.append(
            "DRIFT: PostToolUse hook for 'Edit|Write|NotebookEdit' "
            "(track-file-changes.sh) is missing. File modification tracking is disabled."
        )
    else:
        has_notebook_post = any(
            'NotebookEdit' in entry.get('matcher', '')
            for entry in post_tool_use
            if 'Edit' in entry.get('matcher', '') or 'Write' in entry.get('matcher', '')
        )
        if not has_notebook_post:
            warnings.append(
                "DRIFT: PostToolUse write tracker matcher does not include 'NotebookEdit'. "
                "Notebook edits won't be tracked in the session file change log."
            )

    # 6c: PostToolUseFailure must have Bash matcher
    post_fail = hooks.get('PostToolUseFailure', [])
    has_bash_fail = any(
        'Bash' in entry.get('matcher', '')
        for entry in post_fail
    )
    if not has_bash_fail:
        warnings.append(
            "DRIFT: PostToolUseFailure hook for 'Bash' (notify-bash-failure.sh) is missing. "
            "Agent won't receive feedback when users deny ASK-tier commands."
        )

    # 6d: SessionStart hook with compact matcher
    session_start = hooks.get('SessionStart', [])
    if not session_start:
        warnings.append("DRIFT: SessionStart hook (session-init.sh) is missing.")
    else:
        matcher = session_start[0].get('matcher', '')
        if 'compact' not in matcher:
            warnings.append(
                "DRIFT: SessionStart matcher is missing 'compact'. "
                "Environment variables and context will be lost after compaction."
            )

    # 6e: PreCompact hook
    if not hooks.get('PreCompact'):
        warnings.append(
            "DRIFT: PreCompact hook (pre-compact-save.sh) is missing. "
            "Session state won't be preserved before context trimming."
        )

    # Check 7: All referenced hook scripts exist and are executable
    CHECKS_RUN += 1
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

    # Check 8: security-policy.yaml exists and has valid structure
    CHECKS_RUN += 1
    policy_path = claude_dir / 'security-policy.yaml'
    if not policy_path.exists():
        warnings.append(
            "MISSING: .claude/security-policy.yaml — validate-bash.sh can't read "
            "safe_delete_paths (every 'rm' will trigger ASK even for __pycache__)."
        )
    else:
        try:
            import yaml
            with open(policy_path, 'r', encoding='utf-8') as f:
                policy = yaml.safe_load(f) or {}

            # Validate safe_delete_paths is a list of strings
            sdp = policy.get('safe_delete_paths')
            if sdp is not None:
                if not isinstance(sdp, list):
                    warnings.append(
                        "INVALID: security-policy.yaml 'safe_delete_paths' must be a list. "
                        "validate-bash.sh will fall back to no safe paths (all rm triggers ASK)."
                    )
                elif not all(isinstance(p, str) for p in sdp):
                    warnings.append(
                        "INVALID: security-policy.yaml 'safe_delete_paths' contains non-string entries. "
                        "validate-bash.sh may fail to match safe paths correctly."
                    )

            # Validate secret_files is a list of strings (regex patterns)
            sf = policy.get('secret_files')
            if sf is not None:
                if not isinstance(sf, list):
                    warnings.append(
                        "INVALID: security-policy.yaml 'secret_files' must be a list. "
                        "validate-read.sh and validate-write.sh will ignore custom patterns."
                    )
                elif not all(isinstance(p, str) for p in sf):
                    warnings.append(
                        "INVALID: security-policy.yaml 'secret_files' contains non-string entries."
                    )

            # Validate allowed_write_directories if present
            awd = policy.get('allowed_write_directories')
            if awd is not None:
                if not isinstance(awd, list):
                    warnings.append(
                        "INVALID: security-policy.yaml 'allowed_write_directories' must be a list. "
                        "Directory-scoped write restrictions will be disabled."
                    )
                elif awd:  # Non-empty list
                    for entry in awd:
                        if not isinstance(entry, str):
                            warnings.append(
                                "INVALID: security-policy.yaml 'allowed_write_directories' "
                                "contains non-string entries."
                            )
                            break
                        if '..' in entry:
                            warnings.append(
                                f"SUSPICIOUS: allowed_write_directories entry '{entry}' "
                                "contains '..'. Use clean relative paths from project root."
                            )
                        if entry.startswith('/'):
                            warnings.append(
                                f"PORTABILITY: allowed_write_directories entry '{entry}' "
                                "is absolute. Prefer relative paths for portability "
                                "across machines and CI environments."
                            )
        except ImportError:
            warnings.append(
                "MISSING: PyYAML is not installed. security-policy.yaml structural "
                "validation skipped. Hook scripts (validate-bash.sh, validate-read.sh, "
                "validate-write.sh) will also silently ignore policy overrides at runtime. "
                "Install with: pip install pyyaml (or: uv pip install pyyaml)"
            )
        except Exception as e:
            warnings.append(
                f"INVALID: security-policy.yaml failed to parse: {e}. "
                "Hook scripts will fall back to defaults."
            )

    # Check 9: validate-bash.sh tier ordering (blocked before safe)
    CHECKS_RUN += 1
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

    # Check 10: Required lib scripts exist
    CHECKS_RUN += 1
    required_libs = ['session_state.py', 'project_analyzer.py', 'path_validator.py']
    for lib_name in required_libs:
        lib_path = claude_dir / 'lib' / lib_name
        if not lib_path.exists():
            warnings.append(f"MISSING: .claude/lib/{lib_name}")

    # Check 11: Cross-reference SETTINGS_GUARD.md hook list against actual settings.json
    CHECKS_RUN += 1
    guard_path = claude_dir / 'SETTINGS_GUARD.md'
    if guard_path.exists():
        try:
            guard_content = guard_path.read_text(encoding='utf-8')
            # Extract hook script names from guard doc
            guard_scripts = set(re.findall(r'`(\w[\w-]+\.sh)`', guard_content))
            # Extract hook script names from settings.json
            settings_scripts = set()
            for event_hooks in hooks.values():
                for entry in event_hooks:
                    for hook in entry.get('hooks', []):
                        cmd = hook.get('command', '')
                        match = re.search(r'([\w-]+\.sh)', cmd)
                        if match:
                            settings_scripts.add(match.group(1))

            # Scripts in guard but not in settings
            guard_only = guard_scripts - settings_scripts
            for script in guard_only:
                warnings.append(
                    f"DRIFT: SETTINGS_GUARD.md documents '{script}' but it's not "
                    "registered in settings.json. Guard documentation has drifted."
                )

            # Scripts in settings but not in guard
            settings_only = settings_scripts - guard_scripts
            for script in settings_only:
                warnings.append(
                    f"DRIFT: settings.json registers '{script}' but it's not "
                    "documented in SETTINGS_GUARD.md. Guard documentation needs updating."
                )
        except IOError:
            pass

    # Check 12: enableAllProjectMcpServers should be false for security
    CHECKS_RUN += 1
    if settings.get('enableAllProjectMcpServers') is not False:
        # Only warn if the key is present and set to true, or missing entirely
        if settings.get('enableAllProjectMcpServers') is True:
            warnings.append(
                "SECURITY: enableAllProjectMcpServers is true. "
                "For a security template, MCP server approval should be opt-in."
            )

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
            "checks_run": CHECKS_RUN,
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
