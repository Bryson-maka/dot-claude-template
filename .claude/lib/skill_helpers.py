"""
Shared utilities for Claude Code skill scripts.

Consolidates common patterns used across cc-prime-cw, cc-execute, and cc-conclude
skill discovery scripts: YAML config loading, session context reading, and
base directory resolution.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def get_base_dir(script_path: str, levels_up: int = 3) -> Path:
    """Calculate project base directory from a script's location.

    Args:
        script_path: __file__ from the calling script
        levels_up: How many parent directories to traverse (default 3 for .claude/skills/skill-name/)
    """
    path = Path(script_path).parent.resolve()
    for _ in range(levels_up):
        path = path.parent
    return path.resolve()


def load_yaml_config(config_path: Path, fallback: dict) -> dict:
    """Load YAML config with graceful fallback.

    Args:
        config_path: Path to the YAML config file
        fallback: Default config to use if file missing or YAML unavailable
    """
    try:
        import yaml
    except ImportError:
        return fallback

    if not config_path.exists():
        return fallback

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config or fallback
    except Exception as e:
        print(f"Warning: Could not load {config_path.name}: {e}", file=sys.stderr)
        return fallback


def get_session_context(base_dir: Path) -> Optional[dict]:
    """Load session context from state.json and manifest.json.

    Returns dict with: primed, domains, foundation_docs, manifest_path,
    state_path, execution_journal, subagents_spawned, verifications,
    files_modified_by_session.
    Returns None if no session data exists.
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
        'files_modified_by_session': [],
    }

    has_data = False

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
            context['files_modified_by_session'] = state.get('files_modified', [])
            has_data = True
        except (json.JSONDecodeError, IOError):
            pass

    manifest_path = base_dir / '.claude' / 'session' / 'manifest.json'
    if manifest_path.exists():
        context['manifest_path'] = str(manifest_path)
        if not context['primed']:
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                context['primed'] = True
                context['domains'] = list(manifest.get('domains', {}).keys())
                context['foundation_docs'] = [
                    f['path'] for f in manifest.get('foundation', [])
                ]
                has_data = True
            except (json.JSONDecodeError, IOError):
                pass

    return context if has_data else None
