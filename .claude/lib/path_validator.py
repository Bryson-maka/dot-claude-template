"""
Directory-scoped write restriction utilities.

Provides path validation for Claude Code hooks to enforce write restrictions
at the filesystem level. Designed as a shared library called by both
validate-write.sh and validate-bash.sh.

Key design decisions:
    - Uses os.path.realpath() for symlink resolution (portable, no coreutils)
    - Feature is opt-in: empty/missing allowed_write_directories = no restriction
    - Paths in config are relative to project root, resolved at validation time
    - Uses os.path.commonpath for prefix matching (prevents /src-evil matching /src)
    - Bash write extraction is best-effort; unparseable commands flagged for ASK tier

Usage from hooks (via python3 -c):
    python3 -c "
    import sys, json
    sys.path.insert(0, sys.argv[1])
    from path_validator import check_write_path
    result = check_write_path(sys.argv[2], sys.argv[3])
    print(json.dumps(result))
    " "$LIB_DIR" "$FILE_PATH" "$PROJECT_DIR"
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Optional


def load_allowed_dirs(
    policy_path: str, project_dir: str
) -> Optional[list[str]]:
    """Load allowed_write_directories from security-policy.yaml.

    Returns:
        List of resolved absolute directory paths, or None if feature
        is disabled (key missing, empty list, or file not found).
    """
    if not os.path.isfile(policy_path):
        return None

    try:
        import yaml
    except ImportError:
        # Without PyYAML, fall back to basic parsing
        return _parse_allowed_dirs_basic(policy_path, project_dir)

    try:
        with open(policy_path) as f:
            policy = yaml.safe_load(f) or {}
    except Exception:
        return None

    return _resolve_dir_list(policy.get('allowed_write_directories'), project_dir)


def _parse_allowed_dirs_basic(
    policy_path: str, project_dir: str
) -> Optional[list[str]]:
    """Fallback YAML parser for allowed_write_directories when PyYAML unavailable.

    Handles the simple list format:
        allowed_write_directories:
          - src
          - tests
    """
    try:
        with open(policy_path) as f:
            lines = f.readlines()
    except Exception:
        return None

    in_section = False
    raw_dirs: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#') or not stripped:
            if in_section and not stripped.startswith('#'):
                continue
            if in_section and stripped.startswith('#'):
                continue
            continue

        if stripped.startswith('allowed_write_directories:'):
            value = stripped.split(':', 1)[1].strip()
            if value == '[]':
                return None
            in_section = True
            continue

        if in_section:
            if stripped.startswith('- '):
                entry = stripped[2:].strip().strip('"').strip("'")
                if entry:
                    raw_dirs.append(entry)
            elif not stripped.startswith('#'):
                break  # New top-level key

    if not raw_dirs:
        return None

    return _resolve_dir_list(raw_dirs, project_dir)


def _resolve_dir_list(
    dirs: Optional[list], project_dir: str
) -> Optional[list[str]]:
    """Resolve a list of directory entries to absolute paths."""
    if not dirs:
        return None

    resolved = []
    for d in dirs:
        if not isinstance(d, str) or not d.strip():
            continue
        d = d.strip()
        if os.path.isabs(d):
            resolved.append(os.path.realpath(d))
        else:
            resolved.append(os.path.realpath(os.path.join(project_dir, d)))

    return resolved if resolved else None


def resolve_path(file_path: str) -> str:
    """Resolve a file path, following symlinks.

    Uses os.path.realpath which is portable across macOS and Linux
    (no coreutils dependency). Works even if the path doesn't exist yet
    (resolves as far as possible).
    """
    return os.path.realpath(file_path)


def is_path_allowed(
    resolved_path: str, allowed_dirs: Optional[list[str]]
) -> bool:
    """Check if a resolved path falls within any allowed directory.

    Args:
        resolved_path: Absolute, symlink-resolved path to check.
        allowed_dirs: List of allowed absolute directory paths,
            or None if feature is disabled.

    Returns:
        True if path is allowed (or feature disabled), False if denied.
    """
    if allowed_dirs is None:
        return True

    resolved_path = os.path.normpath(resolved_path)

    for allowed in allowed_dirs:
        allowed = os.path.normpath(allowed)
        # Use string prefix with separator to prevent /src-evil matching /src
        if resolved_path == allowed or resolved_path.startswith(allowed + os.sep):
            return True

    return False


def check_write_path(
    file_path: str, project_dir: str,
    policy_path: Optional[str] = None
) -> dict:
    """Full validation: load config, resolve path, check permission.

    Returns dict with:
        allowed: bool
        reason: str (human-readable explanation)
        resolved_path: str (the resolved absolute path)
        feature_enabled: bool
    """
    if policy_path is None:
        policy_path = os.path.join(project_dir, '.claude', 'security-policy.yaml')

    allowed_dirs = load_allowed_dirs(policy_path, project_dir)
    resolved = resolve_path(file_path)

    if allowed_dirs is None:
        return {
            'allowed': True,
            'reason': 'Directory restrictions not configured',
            'resolved_path': resolved,
            'feature_enabled': False,
        }

    if is_path_allowed(resolved, allowed_dirs):
        return {
            'allowed': True,
            'reason': f'Path is within allowed directory',
            'resolved_path': resolved,
            'feature_enabled': True,
        }

    return {
        'allowed': False,
        'reason': f'Path outside allowed directories: {resolved}',
        'resolved_path': resolved,
        'feature_enabled': True,
    }


# ---------------------------------------------------------------------------
# Bash write path extraction
# ---------------------------------------------------------------------------

# Patterns that indicate a bash command writes to the filesystem.
# Each entry: (regex_pattern, group_index_for_path_or_None)
# None means "we know it writes but can't extract the path reliably"
_BASH_WRITE_PATTERNS: list[tuple[str, Optional[int]]] = [
    # Output redirection: cmd > /path or cmd >> /path
    # Captures the path after > or >>
    (r'(?:>>?)\s+([^\s;|&]+)', 1),
    # tee: cmd | tee /path or cmd | tee -a /path
    (r'\btee\s+(?:-[a-zA-Z]+\s+)*([^\s;|&]+)', 1),
    # cp: cp [flags] src dst (last arg is destination)
    (r'\bcp\s+(?:-[a-zA-Z]+\s+)*(?:[^\s;|&]+\s+)+([^\s;|&]+)', 1),
    # mv: mv [flags] src dst
    (r'\bmv\s+(?:-[a-zA-Z]+\s+)*(?:[^\s;|&]+\s+)+([^\s;|&]+)', 1),
    # mkdir: mkdir [flags] /path
    (r'\bmkdir\s+(?:-[a-zA-Z]+\s+)*([^\s;|&]+)', 1),
    # touch: touch /path
    (r'\btouch\s+([^\s;|&]+)', 1),
    # install: install [flags] src dst
    (r'\binstall\s+(?:-[a-zA-Z]+\s+)*(?:[^\s;|&]+\s+)+([^\s;|&]+)', 1),
    # curl -o /path or curl --output /path
    (r'\bcurl\s+.*?(?:-o|--output)\s+([^\s;|&]+)', 1),
    # wget -O /path or wget --output-document /path
    (r'\bwget\s+.*?(?:-O|--output-document)\s+([^\s;|&]+)', 1),
    # sed -i: sed -i 's/...' /path (in-place edit)
    (r"\bsed\s+-i(?:\s+'[^']*'|\s+\"[^\"]*\")\s+([^\s;|&]+)", 1),
]

# Commands that write but paths are not reliably extractable
_UNPARSEABLE_WRITE_INDICATORS = [
    r'\bpython[23]?\s+-c\b',
    r'\bnode\s+-e\b',
    r'\bruby\s+-e\b',
    r'\bperl\s+-e\b',
    r'\btar\s+.*(?:-C\b|--directory\b)',
    r'\bunzip\s+.*-d\b',
    r'\brsync\b',
    r'\bpatch\b',
    r'\beval\s',
    r'\bdd\b.*\bof=',
]


def extract_bash_write_paths(command: str) -> dict:
    """Extract write target paths from a bash command string.

    Returns dict with:
        paths: list[str] — extracted absolute/relative paths
        has_unparseable_writes: bool — command has write indicators
            we can't parse
        unparseable_reasons: list[str] — which patterns triggered
    """
    paths: list[str] = []
    unparseable_reasons: list[str] = []

    for pattern, group_idx in _BASH_WRITE_PATTERNS:
        for match in re.finditer(pattern, command):
            if group_idx is not None:
                path = match.group(group_idx)
                # Skip shell variables and subshells — can't resolve statically
                if path and not path.startswith('$') and not path.startswith('('):
                    paths.append(path)

    for pattern in _UNPARSEABLE_WRITE_INDICATORS:
        if re.search(pattern, command):
            # Extract a readable name from the pattern
            unparseable_reasons.append(pattern)

    return {
        'paths': paths,
        'has_unparseable_writes': bool(unparseable_reasons),
        'unparseable_reasons': unparseable_reasons,
    }


def check_bash_write_paths(
    command: str, project_dir: str,
    policy_path: Optional[str] = None
) -> dict:
    """Full bash command validation: extract paths, check each against allowed dirs.

    Returns dict with:
        allowed: bool — True if all extracted paths are allowed
        denied_paths: list[str] — paths that fell outside allowed dirs
        has_unparseable_writes: bool
        unparseable_reasons: list[str]
        feature_enabled: bool
    """
    if policy_path is None:
        policy_path = os.path.join(project_dir, '.claude', 'security-policy.yaml')

    allowed_dirs = load_allowed_dirs(policy_path, project_dir)

    if allowed_dirs is None:
        return {
            'allowed': True,
            'denied_paths': [],
            'has_unparseable_writes': False,
            'unparseable_reasons': [],
            'feature_enabled': False,
        }

    extraction = extract_bash_write_paths(command)
    denied: list[str] = []

    for path in extraction['paths']:
        # Resolve relative paths against project dir (cwd approximation)
        if not os.path.isabs(path):
            path = os.path.join(project_dir, path)
        resolved = resolve_path(path)
        if not is_path_allowed(resolved, allowed_dirs):
            denied.append(resolved)

    return {
        'allowed': len(denied) == 0,
        'denied_paths': denied,
        'has_unparseable_writes': extraction['has_unparseable_writes'],
        'unparseable_reasons': extraction['unparseable_reasons'],
        'feature_enabled': True,
    }


# ---------------------------------------------------------------------------
# CLI interface for hook scripts
# ---------------------------------------------------------------------------

def main():
    """CLI entry point for hook scripts.

    Usage:
        python3 path_validator.py check-write <file_path> <project_dir>
        python3 path_validator.py check-bash <command> <project_dir>
        python3 path_validator.py extract-paths <command>
    """
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Usage: path_validator.py <command> [args...]'}))
        sys.exit(1)

    action = sys.argv[1]

    if action == 'check-write':
        if len(sys.argv) < 4:
            print(json.dumps({'error': 'Usage: check-write <file_path> <project_dir>'}))
            sys.exit(1)
        result = check_write_path(sys.argv[2], sys.argv[3])
        print(json.dumps(result))

    elif action == 'check-bash':
        if len(sys.argv) < 4:
            print(json.dumps({'error': 'Usage: check-bash <command> <project_dir>'}))
            sys.exit(1)
        result = check_bash_write_paths(sys.argv[2], sys.argv[3])
        print(json.dumps(result))

    elif action == 'extract-paths':
        if len(sys.argv) < 3:
            print(json.dumps({'error': 'Usage: extract-paths <command>'}))
            sys.exit(1)
        result = extract_bash_write_paths(sys.argv[2])
        print(json.dumps(result))

    else:
        print(json.dumps({'error': f'Unknown action: {action}'}))
        sys.exit(1)


if __name__ == '__main__':
    main()
