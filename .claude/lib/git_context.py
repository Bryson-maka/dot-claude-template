#!/usr/bin/env python3
"""
Git Context Provider

Extracts git intelligence for Claude Code skill inline execution.
Provides file volatility, change coupling, recent commits, and recently
modified files — all from local git history with no external dependencies.

Usage:
    python3 .claude/lib/git_context.py                  # Full JSON output
    python3 .claude/lib/git_context.py --pretty          # Pretty-printed JSON
    python3 .claude/lib/git_context.py --volatility      # Just file volatility
    python3 .claude/lib/git_context.py --coupling        # Just change coupling
    python3 .claude/lib/git_context.py --recent          # Just recent commits
    python3 .claude/lib/git_context.py --modified        # Just recently modified files
    python3 .claude/lib/git_context.py --base-dir /path  # Custom base dir
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any, Optional

# Import shared utility from lib package
try:
    from . import get_project_root
except ImportError:
    # Fallback for direct script execution
    def get_project_root() -> Path:
        """Find project root by looking for .claude directory."""
        current = Path.cwd()
        for parent in [current] + list(current.parents):
            if (parent / '.claude').is_dir():
                return parent
        return current

# Paths to exclude from analysis
EXCLUDE_PATTERNS = {
    '.claude/session/',
    '__pycache__/',
    'node_modules/',
    '.git/',
}


def _is_excluded(path: str) -> bool:
    """Check if a file path should be excluded from analysis."""
    return any(pattern in path for pattern in EXCLUDE_PATTERNS)


def _run_git(args: list[str], cwd: Path) -> tuple[bool, str]:
    """Run a git command and return (success, output).

    Args:
        args: Git subcommand and arguments (without 'git' prefix).
        cwd: Working directory for the command.

    Returns:
        Tuple of (success_bool, stdout_string).
    """
    try:
        result = subprocess.run(
            ['git'] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0, result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, ''


def _is_git_repo(base_dir: Path) -> bool:
    """Check if base_dir is inside a git repository."""
    ok, _ = _run_git(['rev-parse', '--is-inside-work-tree'], base_dir)
    return ok


def file_volatility(base_dir: Path, days: int = 30) -> list[dict[str, Any]]:
    """Get files with the most commits in the last N days.

    Args:
        base_dir: Project root directory.
        days: Number of days to look back.

    Returns:
        Top 15 files sorted by commit count descending.
        Each entry: {"path": "src/auth.py", "commits": 12}
    """
    ok, output = _run_git(
        ['log', f'--format=format:', '--name-only', f'--since={days}.days.ago'],
        base_dir,
    )
    if not ok:
        return []

    counts: Counter[str] = Counter()
    for line in output.splitlines():
        line = line.strip()
        if line and not _is_excluded(line):
            counts[line] += 1

    return [
        {"path": path, "commits": count}
        for path, count in counts.most_common(15)
    ]


def change_coupling(base_dir: Path, commits: int = 50) -> list[dict[str, Any]]:
    """Find files that are commonly modified together.

    Analyzes the last N commits to find pairs of files that frequently
    appear in the same commit.

    Args:
        base_dir: Project root directory.
        commits: Number of recent commits to analyze.

    Returns:
        Top 10 most coupled file pairs sorted by co-commit count.
        Each entry: {"files": ["a.py", "b.py"], "co_commits": 8}
    """
    ok, output = _run_git(
        ['log', f'-n{commits}', '--format=format:---COMMIT---', '--name-only'],
        base_dir,
    )
    if not ok:
        return []

    pair_counts: Counter[tuple[str, str]] = Counter()
    current_files: list[str] = []

    for line in output.splitlines():
        line = line.strip()
        if line == '---COMMIT---':
            # Process previous commit's files
            if len(current_files) >= 2:
                filtered = [f for f in current_files if not _is_excluded(f)]
                for a, b in combinations(sorted(set(filtered)), 2):
                    # Exclude pairs where both files are in .claude/
                    if a.startswith('.claude/') and b.startswith('.claude/'):
                        continue
                    pair_counts[(a, b)] += 1
            current_files = []
        elif line:
            current_files.append(line)

    # Process the last commit
    if len(current_files) >= 2:
        filtered = [f for f in current_files if not _is_excluded(f)]
        for a, b in combinations(sorted(set(filtered)), 2):
            if a.startswith('.claude/') and b.startswith('.claude/'):
                continue
            pair_counts[(a, b)] += 1

    return [
        {"files": list(pair), "co_commits": count}
        for pair, count in pair_counts.most_common(10)
    ]


def recent_commits(base_dir: Path, count: int = 5) -> list[dict[str, Any]]:
    """Get the most recent commits.

    Args:
        base_dir: Project root directory.
        count: Number of commits to return.

    Returns:
        List of recent commits.
        Each entry: {"hash": "abc123", "subject": "fix: bug", "author": "name", "date": "2026-03-03"}
    """
    ok, output = _run_git(
        ['log', f'-n{count}', '--format=%H|%s|%an|%ai'],
        base_dir,
    )
    if not ok:
        return []

    results = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split('|', 3)
        if len(parts) < 4:
            continue
        results.append({
            "hash": parts[0][:12],
            "subject": parts[1],
            "author": parts[2],
            "date": parts[3].split(' ')[0] if ' ' in parts[3] else parts[3],
        })
    return results


def recently_modified_files(base_dir: Path, count: int = 5) -> list[dict[str, Any]]:
    """Get files changed in the last N commits with their status.

    Args:
        base_dir: Project root directory.
        count: Number of recent commits to inspect.

    Returns:
        List of recently modified files (deduplicated, most recent status wins).
        Each entry: {"path": "src/auth.py", "status": "M", "commit": "abc123"}
    """
    ok, output = _run_git(
        ['log', f'-n{count}', '--format=%H', '--name-status'],
        base_dir,
    )
    if not ok:
        return []

    results: dict[str, dict[str, str]] = {}
    current_hash = ''

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        # Lines that are just a 40-char hex hash
        if len(line) == 40 and all(c in '0123456789abcdef' for c in line):
            current_hash = line[:12]
            continue
        # Status lines: "M\tpath" or "A\tpath"
        parts = line.split('\t', 1)
        if len(parts) == 2 and parts[0] in ('A', 'M', 'D', 'R', 'C', 'T'):
            path = parts[1]
            if not _is_excluded(path) and path not in results:
                results[path] = {
                    "path": path,
                    "status": parts[0],
                    "commit": current_hash,
                }

    return list(results.values())


def get_full_context(base_dir: Path, days: int = 30) -> dict[str, Any]:
    """Get complete git context for skill injection.

    Args:
        base_dir: Project root directory.
        days: Lookback period for volatility analysis.

    Returns:
        Full context dict with all sections plus metadata.
    """
    if not _is_git_repo(base_dir):
        return {"git_available": False}

    result: dict[str, Any] = {"git_available": True, "period_days": days}

    try:
        result["file_volatility"] = file_volatility(base_dir, days)
    except Exception as e:
        result["file_volatility"] = {"error": str(e)}

    try:
        result["change_coupling"] = change_coupling(base_dir)
    except Exception as e:
        result["change_coupling"] = {"error": str(e)}

    try:
        result["recent_commits"] = recent_commits(base_dir)
    except Exception as e:
        result["recent_commits"] = {"error": str(e)}

    try:
        result["recently_modified"] = recently_modified_files(base_dir)
    except Exception as e:
        result["recently_modified"] = {"error": str(e)}

    return result


# ========== CLI Interface ==========

def main():
    """CLI for git context extraction."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Extract git intelligence for Claude Code skills',
    )
    parser.add_argument('--pretty', action='store_true', help='Pretty-print JSON output')
    parser.add_argument('--volatility', action='store_true', help='Show only file volatility')
    parser.add_argument('--coupling', action='store_true', help='Show only change coupling')
    parser.add_argument('--recent', action='store_true', help='Show only recent commits')
    parser.add_argument('--modified', action='store_true', help='Show only recently modified files')
    parser.add_argument('--base-dir', type=str, default=None, help='Project root directory')
    parser.add_argument('--days', type=int, default=30, help='Lookback period in days (default: 30)')

    args = parser.parse_args()
    indent = 2 if args.pretty else None

    base_dir = Path(args.base_dir) if args.base_dir else get_project_root()

    if not _is_git_repo(base_dir):
        print(json.dumps({"git_available": False}, indent=indent))
        sys.exit(0)

    # If a specific section is requested, show only that section
    specific = args.volatility or args.coupling or args.recent or args.modified
    if specific:
        output: dict[str, Any] = {"git_available": True}
        if args.volatility:
            output["file_volatility"] = file_volatility(base_dir, args.days)
        if args.coupling:
            output["change_coupling"] = change_coupling(base_dir)
        if args.recent:
            output["recent_commits"] = recent_commits(base_dir)
        if args.modified:
            output["recently_modified"] = recently_modified_files(base_dir)
        print(json.dumps(output, indent=indent))
    else:
        print(json.dumps(get_full_context(base_dir, args.days), indent=indent))


if __name__ == '__main__':
    main()
