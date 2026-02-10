"""
Claude Code Shared Library

Shared Python modules used by Claude Code skills.

Modules:
    session_state: Session state management (priming, journal, archival)
    project_analyzer: Project analysis and configuration discovery
    path_validator: Directory-scoped write restriction utilities

Usage:
    from lib import get_project_root, LIB_ROOT, CLAUDE_ROOT
    from lib.session_state import SessionState
    from lib.project_analyzer import analyze_project
    from lib.path_validator import check_write_path, check_bash_write_paths
"""

from __future__ import annotations

from pathlib import Path

__all__ = [
    'LIB_ROOT',
    'CLAUDE_ROOT',
    'get_project_root',
]

# Library root for path resolution
LIB_ROOT = Path(__file__).parent.resolve()
CLAUDE_ROOT = LIB_ROOT.parent.resolve()


def get_project_root() -> Path:
    """Find project root by looking for .claude directory.

    Walks up from current working directory looking for a .claude
    directory to identify the project root.

    Returns:
        Path to project root, or cwd if not found.
    """
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / '.claude').is_dir():
            return parent
    return current
