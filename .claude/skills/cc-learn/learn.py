#!/usr/bin/env python3
"""
Configuration Learning Script

Analyzes the project and generates/updates configuration based on discovered patterns.
This is the main script for the /cc-learn skill.

Usage:
    python learn.py                    # Analyze and show suggestions
    python learn.py --apply            # Apply suggestions to project_config.yaml
    python learn.py --preview          # Preview what would be written
    python learn.py --diff             # Show diff between current and suggested config

Dependencies:
    - Python 3.8+
    - PyYAML (optional, for YAML output)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional, Dict, List

# Add lib to path for imports (consistent naming: lib_dir)
lib_dir = Path(__file__).parent.parent.parent / 'lib'
sys.path.insert(0, str(lib_dir))

try:
    from project_analyzer import (
        analyze_project,
        ProjectAnalysis,
        DomainSuggestion,
        FrameworkDetection,
    )
except ImportError as e:
    print(f"Error: Could not import project_analyzer: {e}", file=sys.stderr)
    print(f"Expected at: {lib_dir / 'project_analyzer.py'}", file=sys.stderr)
    sys.exit(1)

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def get_project_root() -> Path:
    """Find project root from script location."""
    # Script is at .claude/skills/cc-learn/learn.py
    # Project root is 3 levels up
    return Path(__file__).parent.parent.parent.parent.resolve()


def get_config_path(base_dir: Path) -> Path:
    """Get path to project_config.yaml."""
    return base_dir / '.claude' / 'project_config.yaml'


def load_current_config(config_path: Path) -> Dict[str, Any]:
    """Load existing project configuration if present."""
    if not config_path.exists():
        return {}

    try:
        if HAS_YAML:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        else:
            # Try JSON fallback
            json_path = config_path.with_suffix('.json')
            if json_path.exists():
                with open(json_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
    except (yaml.YAMLError, json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load existing config: {e}", file=sys.stderr)

    return {}


def generate_config(analysis: ProjectAnalysis) -> Dict[str, Any]:
    """Generate configuration dict from analysis."""
    config = {
        'generated_by': 'cc-learn',
        'project_info': {
            'languages': list(analysis.languages.keys())[:10],
            'frameworks': [fw.name for fw in analysis.frameworks if fw.confidence >= 0.5],
            'total_files': analysis.total_files,
        },
        'domains': [],
        'commands': analysis.command_suggestions,
    }

    # Convert domain suggestions to config format
    for suggestion in analysis.domain_suggestions:
        domain_config = {
            'name': suggestion.name,
            'description': suggestion.description,
            'patterns': suggestion.patterns,
            'keywords': suggestion.keywords,
            'report_sections': suggestion.report_sections,
        }
        config['domains'].append(domain_config)

    return config


def write_config(config: Dict[str, Any], config_path: Path) -> bool:
    """Write configuration to file."""
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)

        if HAS_YAML:
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        else:
            # Fallback to JSON
            json_path = config_path.with_suffix('.json')
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            print(f"Note: YAML not available, wrote to {json_path}", file=sys.stderr)

        return True
    except IOError as e:
        print(f"Error writing config: {e}", file=sys.stderr)
        return False


def format_summary(analysis: ProjectAnalysis) -> str:
    """Format analysis summary for display."""
    lines = [
        "## Project Analysis Summary",
        "",
        f"**Files**: {analysis.total_files} ({analysis.total_lines:,} lines)",
        "",
    ]

    if analysis.languages:
        top_langs = list(analysis.languages.items())[:5]
        lang_str = ", ".join(f"{lang} ({count})" for lang, count in top_langs)
        lines.append(f"**Languages**: {lang_str}")

    if analysis.frameworks:
        fw_names = [f"{fw.name} ({fw.confidence:.0%})" for fw in analysis.frameworks[:5]]
        lines.append(f"**Frameworks**: {', '.join(fw_names)}")

    lines.append("")

    if analysis.domain_suggestions:
        lines.append(f"**Suggested Domains**: {len(analysis.domain_suggestions)}")
        for d in analysis.domain_suggestions[:5]:
            lines.append(f"  - {d.name}: {len(d.patterns)} patterns")

    if any(analysis.command_suggestions.values()):
        lines.append("")
        lines.append("**Suggested Commands**:")
        for cmd_type, cmds in analysis.command_suggestions.items():
            if cmds:
                lines.append(f"  - {cmd_type}: {cmds[0]}")

    if analysis.warnings:
        lines.append("")
        lines.append("**Warnings**:")
        for warn in analysis.warnings:
            lines.append(f"  - {warn}")

    return '\n'.join(lines)


def format_diff(current: Dict[str, Any], suggested: Dict[str, Any]) -> str:
    """Format diff between current and suggested configuration."""
    lines = ["## Configuration Diff", ""]

    # Compare domains
    current_domains = {d.get('name') for d in current.get('domains', [])}
    suggested_domains = {d.get('name') for d in suggested.get('domains', [])}

    new_domains = suggested_domains - current_domains
    removed_domains = current_domains - suggested_domains

    if new_domains:
        lines.append(f"**New domains**: {', '.join(sorted(new_domains))}")
    if removed_domains:
        lines.append(f"**Removed domains**: {', '.join(sorted(removed_domains))}")
    if not new_domains and not removed_domains:
        lines.append("**Domains**: No changes")

    # Compare commands
    lines.append("")
    for cmd_type in ['test', 'lint', 'build']:
        current_cmds = current.get('commands', {}).get(cmd_type, [])
        suggested_cmds = suggested.get('commands', {}).get(cmd_type, [])
        if current_cmds != suggested_cmds:
            lines.append(f"**{cmd_type}**: {current_cmds} → {suggested_cmds}")

    return '\n'.join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Analyze project and generate/update .claude configuration',
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Apply suggestions to project_config.yaml',
    )
    parser.add_argument(
        '--preview',
        action='store_true',
        help='Preview configuration that would be written',
    )
    parser.add_argument(
        '--diff',
        action='store_true',
        help='Show diff between current and suggested config',
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON instead of formatted text',
    )
    parser.add_argument(
        '--base-dir',
        type=Path,
        default=None,
        help='Project root directory (default: auto-detect)',
    )

    args = parser.parse_args()

    # Find project root
    base_dir = args.base_dir.resolve() if args.base_dir else get_project_root()

    if not base_dir.exists():
        print(f"Error: Directory not found: {base_dir}", file=sys.stderr)
        sys.exit(1)

    # Run analysis
    analysis = analyze_project(base_dir)

    # Generate suggested config
    suggested_config = generate_config(analysis)

    # Load current config for comparison
    config_path = get_config_path(base_dir)
    current_config = load_current_config(config_path)

    if args.json:
        output = {
            'analysis': {
                'languages': analysis.languages,
                'frameworks': [fw.name for fw in analysis.frameworks],
                'total_files': analysis.total_files,
                'warnings': analysis.warnings,
            },
            'suggested_config': suggested_config,
            'current_config': current_config,
            'config_path': str(config_path),
        }
        print(json.dumps(output, indent=2))

    elif args.preview:
        print("## Suggested Configuration")
        print("")
        if HAS_YAML:
            print("```yaml")
            print(yaml.dump(suggested_config, default_flow_style=False, sort_keys=False))
            print("```")
        else:
            print("```json")
            print(json.dumps(suggested_config, indent=2))
            print("```")

    elif args.diff:
        print(format_diff(current_config, suggested_config))

    elif args.apply:
        success = write_config(suggested_config, config_path)
        if success:
            print(f"Configuration written to: {config_path}")
            print("")
            print(format_summary(analysis))
            print("")
            print("Run `/cc-prime-cw` to load the new configuration.")
        else:
            sys.exit(1)

    else:
        # Default: show summary
        print(format_summary(analysis))
        print("")
        if analysis.domain_suggestions or any(analysis.command_suggestions.values()):
            print("---")
            print("Use `--apply` to write configuration, or `--preview` to see full config.")


if __name__ == '__main__':
    main()
