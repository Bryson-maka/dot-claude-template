#!/usr/bin/env python3
"""
Task Execution Discovery Script

Detects project type and available commands (test, lint, build) based on
indicator files and configuration.

Usage:
    python discover.py              # Full discovery as JSON
    python discover.py --commands   # Just the available commands
    python discover.py --config     # Show loaded configuration

Output:
    JSON with detected project types, available commands, and session context.

Configuration:
    Loads detection rules from workflow.yaml in the same directory.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# Default project detection (used if workflow.yaml not found)
DEFAULT_PROJECT_DETECTION = {
    'python': {
        'indicators': ['pyproject.toml', 'setup.py', 'requirements.txt'],
        'test_commands': ['pytest', 'python -m pytest'],
        'lint_commands': ['ruff check', 'flake8'],
        'build_commands': ['python -m build'],
    },
    'node': {
        'indicators': ['package.json'],
        'test_commands': ['npm test'],
        'lint_commands': ['npm run lint'],
        'build_commands': ['npm run build'],
    },
    'make': {
        'indicators': ['Makefile', 'makefile'],
        'test_commands': ['make test'],
        'lint_commands': ['make lint'],
        'build_commands': ['make build'],
    },
}


def load_config() -> dict:
    """Load configuration from workflow.yaml."""
    if not HAS_YAML:
        return {'project_detection': DEFAULT_PROJECT_DETECTION}

    config_path = Path(__file__).parent / 'workflow.yaml'

    if not config_path.exists():
        return {'project_detection': DEFAULT_PROJECT_DETECTION}

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config or {'project_detection': DEFAULT_PROJECT_DETECTION}
    except (yaml.YAMLError, IOError) as e:
        print(f"Warning: Could not load workflow.yaml: {e}", file=sys.stderr)
        return {'project_detection': DEFAULT_PROJECT_DETECTION}


def detect_project_types(base_dir: Path, detection_config: dict) -> list[str]:
    """Detect which project types are present based on indicator files."""
    detected = []

    for project_type, config in detection_config.items():
        indicators = config.get('indicators', [])
        for indicator in indicators:
            indicator_path = base_dir / indicator
            if indicator_path.exists():
                detected.append(project_type)
                break  # One indicator is enough

    return detected


def get_available_commands(
    base_dir: Path,
    detected_types: list[str],
    detection_config: dict
) -> dict:
    """Get available commands based on detected project types."""
    commands = {
        'test': [],
        'lint': [],
        'build': [],
    }

    for project_type in detected_types:
        config = detection_config.get(project_type, {})

        # Add test commands
        for cmd in config.get('test_commands', []):
            if cmd not in commands['test']:
                commands['test'].append(cmd)

        # Add lint commands
        for cmd in config.get('lint_commands', []):
            if cmd not in commands['lint']:
                commands['lint'].append(cmd)

        # Add build commands
        for cmd in config.get('build_commands', []):
            if cmd not in commands['build']:
                commands['build'].append(cmd)

    # Check for Makefile targets specifically
    makefile_path = base_dir / 'Makefile'
    if not makefile_path.exists():
        makefile_path = base_dir / 'makefile'

    if makefile_path.exists():
        try:
            content = makefile_path.read_text(encoding='utf-8')
            # Check for common targets
            if 'test:' in content and 'make test' not in commands['test']:
                commands['test'].insert(0, 'make test')
            if 'lint:' in content and 'make lint' not in commands['lint']:
                commands['lint'].insert(0, 'make lint')
            if 'build:' in content and 'make build' not in commands['build']:
                commands['build'].insert(0, 'make build')
        except IOError:
            pass

    return commands


def get_session_context(base_dir: Path) -> dict | None:
    """
    Load session context from session state and manifest.

    This allows cc-execute to reference domains/files discovered during priming,
    as well as the execution journal for continuity.
    """
    context = {
        'primed': False,
        'domains': [],
        'foundation_docs': [],
        'manifest_path': None,
        'state_path': None,
        'execution_journal': [],
        'subagents_spawned': 0,
        'verifications': [],
    }

    # Check for session state (primary source)
    state_path = base_dir / '.claude' / 'session' / 'state.json'
    if state_path.exists():
        try:
            with open(state_path, 'r', encoding='utf-8') as f:
                state = json.load(f)
            context['primed'] = state.get('primed_at') is not None
            context['domains'] = state.get('domains', [])
            context['foundation_docs'] = state.get('foundation_docs', [])
            context['state_path'] = str(state_path)
            context['execution_journal'] = state.get('execution_journal', [])
            context['subagents_spawned'] = len(state.get('subagents', []))
            context['verifications'] = state.get('verification_results', [])
        except (json.JSONDecodeError, IOError):
            pass

    # Also check manifest for detailed file info
    manifest_path = base_dir / '.claude' / 'session' / 'manifest.json'
    if manifest_path.exists():
        context['manifest_path'] = str(manifest_path)
        # If state wasn't found, fall back to manifest for basic info
        if not context['primed']:
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                context['primed'] = True
                context['domains'] = list(manifest.get('domains', {}).keys())
                context['foundation_docs'] = [
                    f['path'] for f in manifest.get('foundation', [])
                ]
            except (json.JSONDecodeError, IOError):
                pass

    return context


def discover(base_dir: Path) -> dict:
    """Run full discovery."""
    config = load_config()
    detection_config = config.get('project_detection', DEFAULT_PROJECT_DETECTION)

    detected_types = detect_project_types(base_dir, detection_config)
    commands = get_available_commands(base_dir, detected_types, detection_config)
    session = get_session_context(base_dir)

    # Get subagent config
    subagents = config.get('subagents', {})
    adversarial = config.get('adversarial', {})
    token_budget = config.get('token_budget', {})

    return {
        'base_directory': str(base_dir),
        'project_types': detected_types,
        'commands': commands,
        'session': session,
        'subagents': subagents,
        'adversarial': adversarial,
        'token_budget': token_budget,
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Discover project commands for task execution',
    )
    parser.add_argument(
        '--commands',
        action='store_true',
        help='Output available commands only',
    )
    parser.add_argument(
        '--config',
        action='store_true',
        help='Show loaded configuration',
    )
    parser.add_argument(
        '--base-dir',
        type=Path,
        default=None,
        help='Base directory (default: project root)',
    )
    parser.add_argument(
        '--pretty',
        action='store_true',
        help='Pretty-print JSON output',
    )

    args = parser.parse_args()

    # Determine base directory
    script_dir = Path(__file__).parent.resolve()
    if args.base_dir:
        base_dir = args.base_dir.resolve()
    else:
        # Go up from .claude/skills/cc-execute/ to project root
        base_dir = script_dir.parent.parent.parent.resolve()

    if args.config:
        config = load_config()
        indent = 2 if args.pretty else None
        print(json.dumps(config, indent=indent))
        return

    result = discover(base_dir)

    if args.commands:
        # Just output commands in a readable format
        commands = result['commands']
        print("Available commands:")
        if commands['test']:
            print(f"  Test: {commands['test'][0]}")
        if commands['lint']:
            print(f"  Lint: {commands['lint'][0]}")
        if commands['build']:
            print(f"  Build: {commands['build'][0]}")
    else:
        indent = 2 if args.pretty else None
        print(json.dumps(result, indent=indent))


if __name__ == '__main__':
    main()
