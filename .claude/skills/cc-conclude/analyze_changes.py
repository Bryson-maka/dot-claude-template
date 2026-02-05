#!/usr/bin/env python3
"""
Analyze Changes Script

Analyzes git changes to determine session summary and README update triggers.

Usage:
    python analyze_changes.py              # Full analysis as JSON
    python analyze_changes.py --summary    # Human-readable summary
    python analyze_changes.py --triggers   # Only README triggers
    python analyze_changes.py --config     # Show loaded configuration

Output:
    JSON with git state, file changes, and README update triggers.

Configuration:
    Loads triggers from workflow.yaml in the same directory.
    Falls back to defaults if the file is not found.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional, List

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# Default triggers (used if workflow.yaml not found or yaml not installed)
DEFAULT_README_TRIGGERS = {
    'new_directories': [
        'src/', 'lib/', 'app/',
        'tests/', 'test/',
        'docs/', 'doc/',
        'scripts/', 'bin/',
        'dist/', 'build/',
    ],
    'config_files': [
        'pyproject.toml', 'setup.py', 'setup.cfg',
        'package.json', 'package-lock.json',
        'Cargo.toml', 'go.mod',
        'Makefile', 'CMakeLists.txt',
        'Dockerfile', 'docker-compose.yml',
    ],
    'claude_content': [
        '.claude/commands/',
        '.claude/skills/',
    ],
    'documentation': [
        'CONTRIBUTING.md', 'CHANGELOG.md',
        'LICENSE', 'LICENSE.md',
    ],
}


def load_config() -> dict:
    """Load configuration from workflow.yaml.

    Returns the readme_triggers section, or defaults if file not found.
    """
    if not HAS_YAML:
        return DEFAULT_README_TRIGGERS

    config_path = Path(__file__).parent / 'workflow.yaml'

    if not config_path.exists():
        return DEFAULT_README_TRIGGERS

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        if config and 'readme_triggers' in config:
            return config['readme_triggers']
    except (yaml.YAMLError, IOError) as e:
        print(f"Warning: Could not load workflow.yaml: {e}", file=sys.stderr)

    return DEFAULT_README_TRIGGERS


# Load configuration at module level
README_TRIGGERS = load_config()


@dataclass
class FileChange:
    """Represents a single file change."""
    path: str
    status: str  # A=added, M=modified, D=deleted, R=renamed
    insertions: int = 0
    deletions: int = 0


@dataclass
class GitState:
    """Current git repository state."""
    branch: str
    has_remote: bool
    ahead: int
    behind: int
    staged_count: int
    unstaged_count: int
    untracked_count: int


@dataclass
class SessionContext:
    """Session context from cc-prime-cw and cc-execute."""
    primed: bool
    domains: list[str]
    foundation_docs: list[str]
    manifest_path: str | None
    state_path: str | None = None
    tasks_completed: int = 0
    subagents_spawned: int = 0
    verifications: list[dict] | None = None
    files_modified_by_session: list[str] | None = None


@dataclass
class GitRecommendation:
    """A recommended git action for Claude to take."""
    action: str  # Brief action name (e.g., "stage_files", "commit", "push")
    command: str  # The exact git command to run
    reason: str  # Why this is recommended
    priority: int  # 1=must do first, 2=should do, 3=optional


@dataclass
class AnalysisResult:
    """Complete analysis result."""
    git_state: GitState
    changes: list[FileChange]
    triggers: list[str]
    summary: str
    recommendations: list[GitRecommendation]
    session: SessionContext | None = None


def run_git(args: list[str], preserve_leading_space: bool = False) -> str:
    """Run a git command and return output.

    Args:
        args: Git command arguments
        preserve_leading_space: If True, use rstrip() instead of strip()
            to preserve leading whitespace (important for porcelain format)
    """
    try:
        result = subprocess.run(
            ['git'] + args,
            capture_output=True,
            text=True,
            check=True,
        )
        # Use rstrip for porcelain format where leading space is significant
        if preserve_leading_space:
            return result.stdout.rstrip()
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ''
    except FileNotFoundError:
        print("Error: git not found", file=sys.stderr)
        sys.exit(1)


def get_git_state() -> GitState:
    """Get current git repository state."""
    # Get branch name
    branch = run_git(['rev-parse', '--abbrev-ref', 'HEAD']) or 'unknown'

    # Check remote tracking
    remote_ref = run_git(['rev-parse', '--abbrev-ref', '@{u}'])
    has_remote = bool(remote_ref)

    ahead = behind = 0
    if has_remote:
        # Count commits ahead/behind
        ahead_behind = run_git(['rev-list', '--left-right', '--count', '@{u}...HEAD'])
        if ahead_behind:
            parts = ahead_behind.split()
            if len(parts) == 2:
                behind, ahead = int(parts[0]), int(parts[1])

    # Count file states (preserve leading space for porcelain format)
    status = run_git(['status', '--porcelain'], preserve_leading_space=True)
    staged = unstaged = untracked = 0

    for line in status.split('\n'):
        if not line:
            continue
        index_status = line[0] if len(line) > 0 else ' '
        worktree_status = line[1] if len(line) > 1 else ' '

        if index_status == '?':
            untracked += 1
        elif index_status != ' ':
            staged += 1
        if worktree_status not in (' ', '?'):
            unstaged += 1

    return GitState(
        branch=branch,
        has_remote=has_remote,
        ahead=ahead,
        behind=behind,
        staged_count=staged,
        unstaged_count=unstaged,
        untracked_count=untracked,
    )


def get_file_changes() -> list[FileChange]:
    """Get list of all changed files (staged + unstaged + untracked)."""
    changes = []

    # Get status (preserve leading space for porcelain format)
    status = run_git(['status', '--porcelain'], preserve_leading_space=True)

    for line in status.split('\n'):
        if not line or len(line) < 3:
            continue

        index_status = line[0]
        worktree_status = line[1]
        path = line[3:]

        # Handle renames (format: "R  old -> new")
        if ' -> ' in path:
            path = path.split(' -> ')[1]

        # Determine overall status
        if index_status == '?':
            status_char = 'A'  # Untracked = will be added
        elif index_status == 'A' or worktree_status == 'A':
            status_char = 'A'
        elif index_status == 'D' or worktree_status == 'D':
            status_char = 'D'
        elif index_status == 'R':
            status_char = 'R'
        else:
            status_char = 'M'

        changes.append(FileChange(path=path, status=status_char))

    # Get diff stats for modified/added files
    diff_stat = run_git(['diff', '--numstat', 'HEAD'])
    stat_map = {}

    for line in diff_stat.split('\n'):
        if not line:
            continue
        parts = line.split('\t')
        if len(parts) >= 3:
            insertions = int(parts[0]) if parts[0] != '-' else 0
            deletions = int(parts[1]) if parts[1] != '-' else 0
            path = parts[2]
            stat_map[path] = (insertions, deletions)

    # Apply stats to changes
    for change in changes:
        if change.path in stat_map:
            change.insertions, change.deletions = stat_map[change.path]

    return changes


def detect_triggers(changes: list[FileChange]) -> list[str]:
    """Detect README update triggers from changes."""
    triggers = []

    paths = {c.path for c in changes}
    added_paths = {c.path for c in changes if c.status == 'A'}

    # Check for new directories
    for pattern in README_TRIGGERS.get('new_directories', []):
        for path in added_paths:
            if path.startswith(pattern) or f'/{pattern}' in path:
                triggers.append(f"New directory: {pattern}")
                break

    # Check for config file changes
    for pattern in README_TRIGGERS.get('config_files', []):
        if pattern in paths:
            triggers.append(f"Config changed: {pattern}")

    # Check for Claude content changes
    for pattern in README_TRIGGERS.get('claude_content', []):
        for path in paths:
            if path.startswith(pattern):
                triggers.append(f"Claude config changed: {pattern}")
                break

    # Check for new documentation
    for pattern in README_TRIGGERS.get('documentation', []):
        if pattern in added_paths:
            triggers.append(f"New documentation: {pattern}")

    # Remove duplicates while preserving order
    seen = set()
    unique_triggers = []
    for t in triggers:
        if t not in seen:
            seen.add(t)
            unique_triggers.append(t)

    return unique_triggers


def generate_summary(git_state: GitState, changes: list[FileChange]) -> str:
    """Generate a human-readable summary."""
    lines = []

    # Git state
    lines.append(f"Branch: {git_state.branch}")
    if git_state.has_remote:
        if git_state.ahead > 0:
            lines.append(f"  {git_state.ahead} commit(s) ahead of remote")
        if git_state.behind > 0:
            lines.append(f"  {git_state.behind} commit(s) behind remote")

    # File counts
    total = len(changes)
    added = sum(1 for c in changes if c.status == 'A')
    modified = sum(1 for c in changes if c.status == 'M')
    deleted = sum(1 for c in changes if c.status == 'D')

    lines.append(f"\nFiles changed: {total}")
    if added:
        lines.append(f"  Added: {added}")
    if modified:
        lines.append(f"  Modified: {modified}")
    if deleted:
        lines.append(f"  Deleted: {deleted}")

    # Staged status
    if git_state.staged_count > 0:
        lines.append(f"\nStaged: {git_state.staged_count} file(s)")
    if git_state.unstaged_count > 0:
        lines.append(f"Unstaged: {git_state.unstaged_count} file(s)")
    if git_state.untracked_count > 0:
        lines.append(f"Untracked: {git_state.untracked_count} file(s)")

    return '\n'.join(lines)


def generate_recommendations(
    git_state: GitState,
    changes: list[FileChange],
) -> list[GitRecommendation]:
    """Generate intelligent git recommendations based on current state.

    Returns prioritized list of recommended git commands for Claude to execute.
    """
    recommendations = []

    # Collect file paths by state
    unstaged_files = []
    untracked_files = []
    staged_files = []

    status = run_git(['status', '--porcelain'], preserve_leading_space=True)
    for line in status.split('\n'):
        if not line or len(line) < 3:
            continue
        index_status = line[0]
        worktree_status = line[1]
        path = line[3:]

        # Handle renames
        if ' -> ' in path:
            path = path.split(' -> ')[1]

        if index_status == '?':
            untracked_files.append(path)
        elif index_status != ' ':
            staged_files.append(path)
        if worktree_status not in (' ', '?'):
            unstaged_files.append(path)

    # Priority 1: Stage unstaged files before commit
    if unstaged_files:
        # Recommend staging specific files (not git add -A)
        files_str = ' '.join(f'"{f}"' for f in unstaged_files[:5])
        if len(unstaged_files) > 5:
            files_str += f' # ... and {len(unstaged_files) - 5} more'

        recommendations.append(GitRecommendation(
            action='stage_modified',
            command=f'git add {files_str}',
            reason=f'{len(unstaged_files)} modified file(s) not staged - must stage before commit',
            priority=1,
        ))

    # Priority 1: Stage untracked files (if they should be committed)
    if untracked_files:
        # Filter out common files that shouldn't be committed
        ignore_patterns = ['.env', '.DS_Store', '__pycache__', '.pyc', 'node_modules']
        safe_untracked = [f for f in untracked_files
                         if not any(p in f for p in ignore_patterns)]

        if safe_untracked:
            files_str = ' '.join(f'"{f}"' for f in safe_untracked[:5])
            if len(safe_untracked) > 5:
                files_str += f' # ... and {len(safe_untracked) - 5} more'

            recommendations.append(GitRecommendation(
                action='stage_new',
                command=f'git add {files_str}',
                reason=f'{len(safe_untracked)} new file(s) to stage (review before adding)',
                priority=1,
            ))

    # Priority 2: Commit staged changes
    if staged_files or (not unstaged_files and not untracked_files and git_state.staged_count > 0):
        recommendations.append(GitRecommendation(
            action='commit',
            command='git commit -m "<type>: <description>"',
            reason='Staged files ready to commit',
            priority=2,
        ))

    # Priority 3: Push to remote if ahead
    if git_state.has_remote and git_state.ahead > 0:
        recommendations.append(GitRecommendation(
            action='push',
            command='git push',
            reason=f'{git_state.ahead} commit(s) ahead of remote',
            priority=3,
        ))

    # Priority 3: Pull from remote if behind
    if git_state.has_remote and git_state.behind > 0:
        recommendations.append(GitRecommendation(
            action='pull',
            command='git pull',
            reason=f'{git_state.behind} commit(s) behind remote - consider pulling first',
            priority=3,
        ))

    # No changes case
    if not changes and not recommendations:
        recommendations.append(GitRecommendation(
            action='none',
            command='# No git actions needed',
            reason='Working tree is clean',
            priority=3,
        ))

    # Sort by priority
    recommendations.sort(key=lambda r: r.priority)

    return recommendations


def get_session_context() -> SessionContext | None:
    """
    Load session context from state.json and manifest.

    Enables cc-conclude to reference what was discovered during priming
    and what was done during execution.
    """
    # Find project root (where .claude/ lives)
    script_dir = Path(__file__).parent.resolve()
    base_dir = script_dir.parent.parent.parent.resolve()

    state_path = base_dir / '.claude' / 'session' / 'state.json'
    manifest_path = base_dir / '.claude' / 'session' / 'manifest.json'

    context = SessionContext(
        primed=False,
        domains=[],
        foundation_docs=[],
        manifest_path=None,
        state_path=None,
    )

    # Load from state.json (primary source with execution data)
    if state_path.exists():
        try:
            with open(state_path, 'r', encoding='utf-8') as f:
                state = json.load(f)

            context.primed = state.get('primed_at') is not None
            context.domains = state.get('domains', [])
            context.foundation_docs = state.get('foundation_docs', [])
            context.state_path = str(state_path)

            # Execution data
            journal = state.get('execution_journal', [])
            context.tasks_completed = sum(
                1 for e in journal if e.get('type') == 'task_completed'
            )
            context.subagents_spawned = len(state.get('subagents', []))
            context.verifications = state.get('verification_results', [])
            context.files_modified_by_session = state.get('files_modified', [])

        except (json.JSONDecodeError, IOError, KeyError):
            pass

    # Also load manifest path
    if manifest_path.exists():
        context.manifest_path = str(manifest_path)

        # Fall back to manifest if state wasn't loaded
        if not context.primed:
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                context.primed = True
                context.domains = list(manifest.get('domains', {}).keys())
                context.foundation_docs = [
                    f['path'] for f in manifest.get('foundation', [])
                ]
            except (json.JSONDecodeError, IOError, KeyError):
                pass

    return context if context.primed else None


def conclude_session() -> bool:
    """
    Conclude the session and archive to history.

    Called after successful commit to archive session data.
    """
    script_dir = Path(__file__).parent.resolve()
    base_dir = script_dir.parent.parent.parent.resolve()

    # Import session_state from lib directory
    lib_dir = base_dir / '.claude' / 'lib'
    sys.path.insert(0, str(lib_dir))

    try:
        from session_state import SessionState

        state = SessionState(base_dir)
        return state.conclude()

    except ImportError as e:
        print(f"Warning: Could not import session_state: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Warning: Could not conclude session: {e}", file=sys.stderr)
        return False
    finally:
        if str(lib_dir) in sys.path:
            sys.path.remove(str(lib_dir))


def analyze() -> AnalysisResult:
    """Run full analysis."""
    git_state = get_git_state()
    changes = get_file_changes()
    triggers = detect_triggers(changes)
    summary = generate_summary(git_state, changes)
    recommendations = generate_recommendations(git_state, changes)
    session = get_session_context()

    return AnalysisResult(
        git_state=git_state,
        changes=changes,
        triggers=triggers,
        summary=summary,
        recommendations=recommendations,
        session=session,
    )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Analyze git changes for session conclusion',
    )
    parser.add_argument(
        '--summary',
        action='store_true',
        help='Output human-readable summary only',
    )
    parser.add_argument(
        '--triggers',
        action='store_true',
        help='Output README triggers only',
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Force JSON output (default)',
    )
    parser.add_argument(
        '--config',
        action='store_true',
        help='Show loaded configuration and exit',
    )
    parser.add_argument(
        '--conclude',
        action='store_true',
        help='Conclude session and archive to history',
    )

    args = parser.parse_args()

    if args.config:
        config_path = Path(__file__).parent / 'workflow.yaml'
        print(f"Config file: {config_path}")
        print(f"File exists: {config_path.exists()}")
        print(f"YAML available: {HAS_YAML}")
        print(f"\nLoaded triggers:")
        print(json.dumps(README_TRIGGERS, indent=2))
        return

    if args.conclude:
        success = conclude_session()
        if success:
            print("Session concluded and archived to history.jsonl")
        else:
            print("Failed to conclude session", file=sys.stderr)
            sys.exit(1)
        return

    result = analyze()

    if args.summary:
        print(result.summary)
        if result.triggers:
            print("\nREADME update triggers:")
            for trigger in result.triggers:
                print(f"  - {trigger}")
    elif args.triggers:
        if result.triggers:
            for trigger in result.triggers:
                print(trigger)
        else:
            print("No README update triggers detected.")
    else:
        # JSON output
        output = {
            'git_state': asdict(result.git_state),
            'changes': [asdict(c) for c in result.changes],
            'triggers': result.triggers,
            'recommendations': [asdict(r) for r in result.recommendations],
            'summary': result.summary,
            'session': asdict(result.session) if result.session else None,
        }
        print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
