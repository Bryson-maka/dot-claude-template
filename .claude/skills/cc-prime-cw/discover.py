#!/usr/bin/env python3
"""
Context Priming Discovery Script

Scans the codebase based on domain definitions and generates a JSON manifest
with file metadata including line counts, size classification, and chunking info.

Usage:
    python3 discover.py              # Output manifest to stdout
    python3 discover.py --pretty     # Pretty-print the JSON output
    python3 discover.py --help       # Show this help message

Size Classifications:
    CHUNK  - >2000 lines  - Requires chunked reading with overlapping sections
    LARGE  - 500-2000     - Safe to read complete but substantial
    SMALL  - <500         - Safe to read complete

Chunking Strategy:
    Files >2000 lines are split into 1500-line sections with 100-line overlap
    to preserve context at boundaries (class definitions, method signatures).

Dependencies:
    - Python 3.8+ standard library
    - PyYAML (yaml module)

Output:
    JSON manifest to stdout containing:
    - generated_at: ISO timestamp
    - domains: dict of domain name -> domain info
        - description: domain description
        - files: list of file info dicts
        - keywords: regex patterns for content matching
        - report_sections: expected report sections

Author: Context Priming Skill
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print(
        "Error: PyYAML is required. Install with: pip install pyyaml",
        file=sys.stderr
    )
    sys.exit(1)


# Size classification thresholds
CHUNK_THRESHOLD = 2000  # Lines above this require chunking
LARGE_THRESHOLD = 500   # Lines above this are considered LARGE

# Chunking parameters
CHUNK_SIZE = 1500       # Lines per chunk
CHUNK_OVERLAP = 100     # Overlap between chunks


def get_line_count(file_path: Path) -> int:
    """Count lines in a file, handling encoding errors gracefully."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            return sum(1 for _ in f)
    except (OSError, IOError):
        return 0


def classify_size(line_count: int) -> str:
    """Classify file size based on line count thresholds."""
    if line_count > CHUNK_THRESHOLD:
        return "CHUNK"
    elif line_count > LARGE_THRESHOLD:
        return "LARGE"
    else:
        return "SMALL"


def calculate_chunks(line_count: int) -> list[list[int]] | None:
    """
    Calculate chunk ranges for files that need chunking.

    Returns list of [start, end] pairs with CHUNK_OVERLAP lines overlap.
    Returns None for files that don't need chunking.
    """
    if line_count <= CHUNK_THRESHOLD:
        return None

    chunks = []
    start = 1

    while start < line_count:
        end = min(start + CHUNK_SIZE - 1, line_count)
        chunks.append([start, end])

        if end >= line_count:
            break

        # Next chunk starts CHUNK_OVERLAP lines before current end
        start = end - CHUNK_OVERLAP + 1

    return chunks


def discover_files(pattern: str, base_dir: Path) -> list[Path]:
    """
    Discover files matching a glob pattern.

    Handles missing directories gracefully by returning empty list.
    """
    try:
        # Convert pattern to be relative to base_dir
        if pattern.startswith('/'):
            # Absolute pattern - use as-is
            return sorted(Path('/').glob(pattern.lstrip('/')))
        else:
            # Relative pattern - resolve from base_dir
            return sorted(base_dir.glob(pattern))
    except (OSError, ValueError):
        return []


def normalize_report_sections(report_sections: list) -> list[str]:
    """
    Normalize report_sections to a list of strings.

    Handles both formats:
    - List of strings: ["Section1", "Section2"]
    - List of dicts: [{"key": "description"}, ...]
    """
    if not report_sections:
        return []

    result = []
    for item in report_sections:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            # Extract keys from dict format
            result.extend(item.keys())
    return result


def process_domain(
    domain_name: str,
    domain_config: dict[str, Any],
    base_dir: Path,
    max_files: int | None = None
) -> dict[str, Any]:
    """
    Process a single domain: discover files, get metadata.

    Args:
        domain_name: Name of the domain
        domain_config: Configuration for this domain
        base_dir: Base directory to resolve paths from
        max_files: Maximum files to include (from analyst_config.max_files_per_domain)

    Returns domain info dict with files, keywords, report_sections.
    """
    files_info = []
    seen_paths = set()  # Deduplicate across patterns

    patterns = domain_config.get('patterns', [])

    for pattern in patterns:
        discovered = discover_files(pattern, base_dir)

        for file_path in discovered:
            # Skip directories, non-files, and duplicates
            if not file_path.is_file():
                continue

            resolved = file_path.resolve()
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)

            line_count = get_line_count(file_path)
            size_class = classify_size(line_count)
            chunks = calculate_chunks(line_count)

            # Store path relative to base_dir for cleaner output
            try:
                rel_path = file_path.resolve().relative_to(base_dir)
                path_str = str(rel_path)
            except ValueError:
                path_str = str(file_path)

            files_info.append({
                'path': path_str,
                'lines': line_count,
                'size_class': size_class,
                'chunks': chunks
            })

    # Sort files by importance: entry points first (main, index, app, __init__), then by lines desc
    def file_importance(f):
        path = f['path'].lower()
        name = path.split('/')[-1]
        # Priority 1: Entry points
        if any(entry in name for entry in ['main.', 'index.', 'app.', '__init__']):
            return (0, -f['lines'], path)
        # Priority 2: Config/setup files
        if any(cfg in name for cfg in ['config', 'setup', 'settings']):
            return (1, -f['lines'], path)
        # Priority 3: All others by line count (larger files first)
        return (2, -f['lines'], path)

    files_info.sort(key=file_importance)

    # Enforce max_files_per_domain limit if configured
    if max_files and len(files_info) > max_files:
        files_info = files_info[:max_files]

    # Re-sort by path for consistent output after truncation
    files_info.sort(key=lambda x: x['path'])

    # Handle description that may be multiline
    description = domain_config.get('description', '')
    if isinstance(description, str):
        description = description.strip()

    return {
        'description': description,
        'files': files_info,
        'keywords': domain_config.get('keywords', []),
        'report_sections': normalize_report_sections(
            domain_config.get('report_sections', [])
        )
    }


def load_domains_config(config_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Load and validate the domains.yaml configuration.

    Returns tuple of (domains_dict, analyst_config).
    Handles both formats:
    - Dict format: {"domains": {"name": {...}}}
    - List format: {"domains": [{"name": "...", ...}]}
    """
    if not config_path.exists():
        print(
            f"Error: Configuration file not found: {config_path}",
            file=sys.stderr
        )
        sys.exit(1)

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"Error: Invalid YAML in {config_path}: {e}", file=sys.stderr)
        sys.exit(1)

    if not config or 'domains' not in config:
        print(
            f"Error: Missing 'domains' key in {config_path}",
            file=sys.stderr
        )
        sys.exit(1)

    domains_raw = config['domains']
    analyst_config = config.get('analyst_config', {})

    # Convert list format to dict format
    if isinstance(domains_raw, list):
        domains_dict = {}
        for domain in domains_raw:
            if isinstance(domain, dict) and 'name' in domain:
                name = domain['name']
                domains_dict[name] = {k: v for k, v in domain.items() if k != 'name'}
            else:
                print(
                    f"Warning: Skipping invalid domain entry: {domain}",
                    file=sys.stderr
                )
        return domains_dict, analyst_config
    elif isinstance(domains_raw, dict):
        return domains_raw, analyst_config
    else:
        print(
            f"Error: 'domains' must be a list or dict in {config_path}",
            file=sys.stderr
        )
        sys.exit(1)


def discover_foundation_docs(
    base_dir: Path,
    foundation_patterns: list[str]
) -> list[dict[str, Any]]:
    """
    Discover foundation documents that exist in the project.

    These are high-value documents that should be read directly
    at the start of context priming (README, CLAUDE.md, architecture docs, etc.)

    Args:
        base_dir: Project root directory
        foundation_patterns: Glob patterns from analyst_config.foundation_patterns

    Returns list of file info dicts for existing foundation documents.
    """
    found_docs = []
    seen_paths = set()

    for pattern in foundation_patterns:
        for file_path in base_dir.glob(pattern):
            if not file_path.is_file():
                continue

            resolved = file_path.resolve()
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)

            try:
                rel_path = resolved.relative_to(base_dir)
                path_str = str(rel_path)
            except ValueError:
                path_str = str(file_path)

            line_count = get_line_count(file_path)

            found_docs.append({
                'path': path_str,
                'lines': line_count,
                'size_class': classify_size(line_count)
            })

    return found_docs


def generate_manifest(
    domains_config: dict[str, Any],
    analyst_config: dict[str, Any],
    base_dir: Path
) -> dict[str, Any]:
    """Generate the complete discovery manifest."""
    # Discover foundation documents using patterns from config
    foundation_patterns = analyst_config.get('foundation_patterns', [])
    foundation_docs = discover_foundation_docs(base_dir, foundation_patterns)

    manifest = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'base_directory': str(base_dir),
        'foundation': foundation_docs,
        'domains': {}
    }

    # Use priority order from analyst_config if available
    priority_order = analyst_config.get('priority_order', [])

    # Sort domains by priority, then alphabetically for any not in priority list
    def domain_sort_key(name: str) -> tuple[int, str]:
        try:
            return (priority_order.index(name), name)
        except ValueError:
            return (len(priority_order), name)

    sorted_domain_names = sorted(domains_config.keys(), key=domain_sort_key)

    # Get max_files limit from analyst_config
    max_files_per_domain = analyst_config.get('max_files_per_domain')

    for domain_name in sorted_domain_names:
        domain_config = domains_config[domain_name]
        manifest['domains'][domain_name] = process_domain(
            domain_name,
            domain_config,
            base_dir,
            max_files=max_files_per_domain
        )

    # Include analyst_config metadata if present
    if analyst_config:
        manifest['analyst_config'] = analyst_config

    return manifest


def save_session_manifest(manifest: dict[str, Any], base_dir: Path) -> Path | None:
    """
    Save manifest to session directory for cross-phase integration.

    Returns the path where manifest was saved, or None if saving failed.
    """
    session_dir = base_dir / '.claude' / 'session'

    try:
        session_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = session_dir / 'manifest.json'

        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)

        return manifest_path
    except (OSError, IOError) as e:
        print(f"Warning: Could not save session manifest: {e}", file=sys.stderr)
        return None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Discover codebase files and generate a JSON manifest for context priming.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--pretty',
        action='store_true',
        help='Pretty-print the JSON output with indentation'
    )
    parser.add_argument(
        '--base-dir',
        type=Path,
        default=None,
        help='Base directory for file discovery (default: project root)'
    )
    parser.add_argument(
        '--config',
        type=Path,
        default=None,
        help='Path to domains.yaml (default: same directory as this script)'
    )
    parser.add_argument(
        '--save-session',
        action='store_true',
        default=True,
        help='Save manifest to .claude/session/ for cross-phase integration (default: true)'
    )
    parser.add_argument(
        '--no-save-session',
        action='store_true',
        help='Do not save manifest to session directory'
    )

    args = parser.parse_args()

    # Determine script location for default config path
    script_dir = Path(__file__).parent.resolve()

    # Default config is domains.yaml in same directory
    config_path = args.config if args.config else script_dir / 'domains.yaml'

    # Default base directory is project root (3 levels up from .claude/skills/context-priming/)
    if args.base_dir:
        base_dir = args.base_dir.resolve()
    else:
        base_dir = script_dir.parent.parent.parent.resolve()

    # Load configuration
    domains_config, analyst_config = load_domains_config(config_path)

    # Generate manifest
    manifest = generate_manifest(domains_config, analyst_config, base_dir)

    # Save to session directory for cross-phase integration
    if args.save_session and not args.no_save_session:
        saved_path = save_session_manifest(manifest, base_dir)
        if saved_path:
            manifest['session_path'] = str(saved_path)

    # Output JSON
    indent = 2 if args.pretty else None
    json.dump(manifest, sys.stdout, indent=indent)

    if args.pretty:
        print()  # Add trailing newline for pretty output


if __name__ == '__main__':
    main()
