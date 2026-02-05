#!/usr/bin/env python3
"""
Project Analyzer - Intelligent Configuration Discovery

Scans a project to discover:
1. File types and extensions present
2. Directory structure patterns
3. Framework/library indicators
4. Language-specific patterns
5. Test infrastructure
6. Build systems

Then generates configuration suggestions for:
- domains.yaml (domain patterns to analyze)
- workflow.yaml (project commands and detection)

Usage:
    python project_analyzer.py                    # Full analysis as JSON
    python project_analyzer.py --suggest-domains  # Suggest domain configs
    python project_analyzer.py --suggest-commands # Suggest test/build commands
    python project_analyzer.py --apply            # Write suggestions to project_config.yaml

This enables the .claude system to adapt to ANY project type automatically.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional, List, Dict, Set

__all__ = [
    'analyze_project',
    'ProjectAnalysis',
    'DomainSuggestion',
    'FrameworkDetection',
    'CommandSuggestion',
]

# File extension to language mapping
EXTENSION_LANGUAGES = {
    # Systems programming
    '.c': 'c', '.h': 'c',
    '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.hpp': 'cpp', '.hh': 'cpp',
    '.rs': 'rust',
    '.go': 'go',
    '.zig': 'zig',
    # Web/scripting
    '.py': 'python',
    '.js': 'javascript', '.mjs': 'javascript', '.cjs': 'javascript',
    '.ts': 'typescript', '.tsx': 'typescript', '.jsx': 'javascript',
    '.rb': 'ruby',
    '.php': 'php',
    '.lua': 'lua',
    '.pl': 'perl', '.pm': 'perl',
    # JVM
    '.java': 'java',
    '.kt': 'kotlin', '.kts': 'kotlin',
    '.scala': 'scala',
    '.groovy': 'groovy',
    '.clj': 'clojure',
    # .NET
    '.cs': 'csharp',
    '.fs': 'fsharp',
    '.vb': 'vb',
    # Mobile
    '.swift': 'swift',
    '.m': 'objc', '.mm': 'objc',
    '.dart': 'dart',
    # Data/config
    '.json': 'json',
    '.yaml': 'yaml', '.yml': 'yaml',
    '.toml': 'toml',
    '.xml': 'xml',
    '.ini': 'ini',
    '.cfg': 'config',
    # Shell
    '.sh': 'shell', '.bash': 'shell', '.zsh': 'shell',
    '.ps1': 'powershell',
    '.bat': 'batch', '.cmd': 'batch',
    # Markup
    '.md': 'markdown', '.mdx': 'markdown',
    '.rst': 'rst',
    '.tex': 'latex',
    '.html': 'html', '.htm': 'html',
    '.css': 'css', '.scss': 'scss', '.sass': 'sass', '.less': 'less',
    # Database
    '.sql': 'sql',
    '.prisma': 'prisma',
    # Embedded/hardware
    '.ino': 'arduino',
    '.v': 'verilog', '.sv': 'systemverilog',
    '.vhd': 'vhdl', '.vhdl': 'vhdl',
    # Other
    '.proto': 'protobuf',
    '.graphql': 'graphql', '.gql': 'graphql',
    '.tf': 'terraform',
    '.dockerfile': 'docker',
}

# Framework indicators - file patterns that suggest specific frameworks
FRAMEWORK_INDICATORS = {
    # Python
    'django': ['manage.py', 'settings.py', 'wsgi.py', 'asgi.py'],
    'flask': ['app.py', 'wsgi.py'],
    'fastapi': ['main.py'],  # with fastapi imports
    'pytest': ['conftest.py', 'pytest.ini', 'pyproject.toml'],
    # JavaScript/TypeScript
    'react': ['src/App.tsx', 'src/App.jsx', 'src/App.js'],
    'nextjs': ['next.config.js', 'next.config.mjs', 'next.config.ts'],
    'vue': ['vue.config.js', 'nuxt.config.js', 'nuxt.config.ts'],
    'angular': ['angular.json', 'angular.cli.json'],
    'express': ['app.js', 'server.js'],
    'nestjs': ['nest-cli.json'],
    # Rust
    'cargo': ['Cargo.toml', 'Cargo.lock'],
    'tokio': [],  # detected via Cargo.toml deps
    # Go
    'gomod': ['go.mod', 'go.sum'],
    'gin': [],  # detected via go.mod deps
    # Build systems
    'make': ['Makefile', 'makefile', 'GNUmakefile'],
    'cmake': ['CMakeLists.txt'],
    'bazel': ['BUILD', 'BUILD.bazel', 'WORKSPACE'],
    'gradle': ['build.gradle', 'build.gradle.kts'],
    'maven': ['pom.xml'],
    # Embedded
    'platformio': ['platformio.ini'],
    'arduino': ['*.ino'],
    'ros2': ['package.xml', 'colcon.meta'],
    'zephyr': ['prj.conf', 'west.yml'],
    'esp-idf': ['sdkconfig', 'sdkconfig.defaults'],
    # Containers/infra
    'docker': ['Dockerfile', 'docker-compose.yml', 'docker-compose.yaml'],
    'kubernetes': ['k8s/', 'kubernetes/', 'helm/'],
    'terraform': ['*.tf', 'main.tf'],
}

# Default ignore patterns
IGNORE_PATTERNS = {
    'node_modules', '__pycache__', '.git', '.svn', '.hg',
    'venv', '.venv', 'env', '.env',
    'build', 'dist', 'target', 'out', 'bin', 'obj',
    '.idea', '.vscode', '.vs',
    'coverage', '.coverage', 'htmlcov',
    '.pytest_cache', '.mypy_cache', '.ruff_cache',
    '.next', '.nuxt', '.output',
    'vendor', 'third_party', 'external',
}


@dataclass
class FileStats:
    """Statistics about a single file."""
    path: str
    extension: str
    language: str
    lines: int
    size_bytes: int


@dataclass
class DirectoryPattern:
    """A discovered directory pattern."""
    path: str
    purpose: str  # 'source', 'test', 'config', 'docs', 'scripts', etc.
    file_count: int
    languages: List[str]
    patterns: List[str]  # glob patterns that match this directory


@dataclass
class FrameworkDetection:
    """A detected framework or tool."""
    name: str
    confidence: float  # 0.0 to 1.0
    indicators_found: List[str]
    suggested_commands: Dict[str, List[str]]  # test, lint, build


@dataclass
class DomainSuggestion:
    """A suggested domain configuration."""
    name: str
    description: str
    patterns: List[str]
    keywords: List[str]
    report_sections: List[str]
    source: str  # 'discovered', 'inferred', 'template'


@dataclass
class ProjectAnalysis:
    """Complete project analysis result."""
    base_directory: str
    languages: Dict[str, int]  # language -> file count
    extensions: Dict[str, int]  # extension -> file count
    total_files: int
    total_lines: int
    directories: List[DirectoryPattern]
    frameworks: List[FrameworkDetection]
    domain_suggestions: List[DomainSuggestion]
    command_suggestions: Dict[str, List[str]]
    warnings: List[str] = field(default_factory=list)


def should_ignore(path: Path) -> bool:
    """Check if path should be ignored."""
    parts = set(path.parts)
    return bool(parts & IGNORE_PATTERNS)


def get_language(extension: str) -> str:
    """Get language name from file extension."""
    return EXTENSION_LANGUAGES.get(extension.lower(), 'unknown')


def count_lines(file_path: Path) -> int:
    """Count lines in a file, handling binary files gracefully."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            return sum(1 for _ in f)
    except (OSError, IOError):
        return 0


def scan_files(base_dir: Path) -> List[FileStats]:
    """Scan all files in the project."""
    files = []

    for root, dirs, filenames in os.walk(base_dir):
        # Filter out ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORE_PATTERNS and not d.startswith('.')]

        root_path = Path(root)
        if should_ignore(root_path.relative_to(base_dir)):
            continue

        for filename in filenames:
            if filename.startswith('.'):
                continue

            file_path = root_path / filename
            try:
                rel_path = file_path.relative_to(base_dir)
            except ValueError:
                continue

            ext = file_path.suffix
            lang = get_language(ext)

            try:
                size = file_path.stat().st_size
                lines = count_lines(file_path) if size < 1_000_000 else 0
            except (OSError, IOError):
                size = 0
                lines = 0

            files.append(FileStats(
                path=str(rel_path),
                extension=ext,
                language=lang,
                lines=lines,
                size_bytes=size,
            ))

    return files


def analyze_directories(files: List[FileStats], base_dir: Path) -> List[DirectoryPattern]:
    """Analyze directory structure to find meaningful patterns."""
    # Group files by parent directory
    dir_files: Dict[str, List[FileStats]] = defaultdict(list)
    for f in files:
        parent = str(Path(f.path).parent)
        if parent == '.':
            parent = ''
        dir_files[parent].append(f)

    patterns = []

    for dir_path, dir_file_list in dir_files.items():
        if not dir_path:
            continue

        # Determine purpose based on directory name and contents
        dir_name = Path(dir_path).name.lower()
        languages = list(set(f.language for f in dir_file_list if f.language != 'unknown'))

        # Infer purpose
        purpose = 'unknown'
        if any(x in dir_name for x in ['test', 'spec', '__test__']):
            purpose = 'tests'
        elif any(x in dir_name for x in ['src', 'lib', 'app', 'pkg', 'internal']):
            purpose = 'source'
        elif any(x in dir_name for x in ['doc', 'docs', 'documentation']):
            purpose = 'docs'
        elif any(x in dir_name for x in ['script', 'bin', 'tool', 'util']):
            purpose = 'scripts'
        elif any(x in dir_name for x in ['config', 'conf', 'cfg', 'settings']):
            purpose = 'config'
        elif any(x in dir_name for x in ['example', 'sample', 'demo']):
            purpose = 'examples'
        elif any(x in dir_name for x in ['asset', 'static', 'public', 'resource']):
            purpose = 'assets'
        elif languages:
            purpose = 'source'

        # Generate glob patterns
        glob_patterns = []
        if languages:
            for lang in languages:
                exts = [ext for ext, l in EXTENSION_LANGUAGES.items() if l == lang]
                for ext in exts[:2]:  # Limit to 2 extensions per language
                    glob_patterns.append(f"{dir_path}/**/*{ext}")
        else:
            glob_patterns.append(f"{dir_path}/**/*")

        patterns.append(DirectoryPattern(
            path=dir_path,
            purpose=purpose,
            file_count=len(dir_file_list),
            languages=languages,
            patterns=glob_patterns,
        ))

    return sorted(patterns, key=lambda p: (-p.file_count, p.path))


def detect_frameworks(base_dir: Path, files: List[FileStats]) -> List[FrameworkDetection]:
    """Detect frameworks and tools based on indicator files."""
    detections = []
    file_set = {f.path for f in files}

    for framework, indicators in FRAMEWORK_INDICATORS.items():
        found_indicators = []

        for indicator in indicators:
            if '*' in indicator:
                # Glob pattern - check if any file matches
                pattern = indicator.replace('*', '')
                matches = [f for f in file_set if pattern in f]
                if matches:
                    found_indicators.extend(matches[:3])
            elif '/' in indicator:
                # Directory pattern
                if any(f.startswith(indicator) for f in file_set):
                    found_indicators.append(indicator)
            else:
                # Exact file match (case-insensitive for some)
                if indicator in file_set or indicator.lower() in {f.lower() for f in file_set}:
                    found_indicators.append(indicator)

        if found_indicators:
            confidence = min(1.0, len(found_indicators) / max(1, len(indicators)))

            # Generate suggested commands based on framework
            commands = get_framework_commands(framework)

            detections.append(FrameworkDetection(
                name=framework,
                confidence=confidence,
                indicators_found=found_indicators,
                suggested_commands=commands,
            ))

    return sorted(detections, key=lambda d: -d.confidence)


def get_framework_commands(framework: str) -> Dict[str, List[str]]:
    """Get suggested commands for a framework."""
    commands: Dict[str, List[str]] = {'test': [], 'lint': [], 'build': []}

    framework_commands = {
        'pytest': {'test': ['pytest', 'python -m pytest']},
        'django': {'test': ['python manage.py test'], 'build': ['python manage.py runserver']},
        'flask': {'build': ['flask run', 'python app.py']},
        'fastapi': {'build': ['uvicorn main:app --reload']},
        'cargo': {'test': ['cargo test'], 'lint': ['cargo clippy'], 'build': ['cargo build']},
        'gomod': {'test': ['go test ./...'], 'lint': ['golangci-lint run'], 'build': ['go build']},
        'make': {'test': ['make test'], 'lint': ['make lint'], 'build': ['make build', 'make']},
        'cmake': {'test': ['ctest'], 'build': ['cmake --build build']},
        'gradle': {'test': ['./gradlew test'], 'lint': ['./gradlew check'], 'build': ['./gradlew build']},
        'maven': {'test': ['mvn test'], 'build': ['mvn package']},
        'platformio': {'test': ['pio test'], 'build': ['pio run']},
        'ros2': {'test': ['colcon test'], 'build': ['colcon build']},
        'docker': {'build': ['docker build .', 'docker-compose build']},
        'nextjs': {'test': ['npm test'], 'lint': ['npm run lint', 'next lint'], 'build': ['npm run build']},
        'react': {'test': ['npm test', 'vitest'], 'lint': ['npm run lint'], 'build': ['npm run build']},
    }

    if framework in framework_commands:
        for cmd_type, cmd_list in framework_commands[framework].items():
            commands[cmd_type].extend(cmd_list)

    return commands


def generate_domain_suggestions(
    files: List[FileStats],
    directories: List[DirectoryPattern],
    frameworks: List[FrameworkDetection],
) -> List[DomainSuggestion]:
    """Generate domain configuration suggestions based on analysis."""
    suggestions = []

    # Group directories by purpose
    purpose_dirs: Dict[str, List[DirectoryPattern]] = defaultdict(list)
    for d in directories:
        purpose_dirs[d.purpose].append(d)

    # Generate suggestions for each discovered purpose
    for purpose, dirs in purpose_dirs.items():
        if purpose == 'unknown':
            continue

        # Collect all patterns and languages
        all_patterns = []
        all_languages = set()
        for d in dirs:
            all_patterns.extend(d.patterns)
            all_languages.update(d.language for d in dirs for d.language in d.languages)

        # Generate keywords based on languages
        keywords = generate_keywords_for_languages(list(all_languages))

        # Generate report sections based on purpose
        report_sections = get_report_sections(purpose)

        description = get_purpose_description(purpose, list(all_languages))

        suggestions.append(DomainSuggestion(
            name=purpose,
            description=description,
            patterns=all_patterns[:10],  # Limit patterns
            keywords=keywords[:6],
            report_sections=report_sections,
            source='discovered',
        ))

    # Add framework-specific domains if high confidence
    for fw in frameworks:
        if fw.confidence >= 0.5:
            fw_domain = get_framework_domain(fw)
            if fw_domain:
                suggestions.append(fw_domain)

    return suggestions


def generate_keywords_for_languages(languages: List[str]) -> List[str]:
    """Generate regex keywords for searching in specific languages."""
    keywords = []

    language_keywords = {
        'python': ['class\\s+\\w+', 'def\\s+\\w+', 'async\\s+def', 'import\\s+', '@\\w+'],
        'javascript': ['function\\s+\\w+', 'class\\s+\\w+', 'const\\s+\\w+', 'export\\s+', 'import\\s+'],
        'typescript': ['interface\\s+\\w+', 'type\\s+\\w+', 'class\\s+\\w+', 'export\\s+', 'async\\s+'],
        'rust': ['fn\\s+\\w+', 'struct\\s+\\w+', 'impl\\s+', 'pub\\s+', 'mod\\s+'],
        'go': ['func\\s+\\w+', 'type\\s+\\w+', 'interface\\s+', 'package\\s+'],
        'c': ['void\\s+\\w+', 'int\\s+\\w+', '#include', '#define', 'struct\\s+'],
        'cpp': ['class\\s+\\w+', 'void\\s+\\w+', 'template', 'namespace', '#include'],
        'java': ['public\\s+class', 'private\\s+', 'void\\s+\\w+', '@Override', 'interface\\s+'],
    }

    for lang in languages:
        if lang in language_keywords:
            keywords.extend(language_keywords[lang][:3])

    return list(dict.fromkeys(keywords))  # Deduplicate while preserving order


def get_report_sections(purpose: str) -> List[str]:
    """Get report sections for a purpose."""
    sections = {
        'source': ['main_components', 'architecture_patterns', 'entry_points', 'key_abstractions'],
        'tests': ['test_structure', 'fixtures', 'coverage_areas', 'test_patterns'],
        'config': ['project_metadata', 'dependencies', 'build_config', 'environment'],
        'docs': ['project_overview', 'setup_instructions', 'api_docs', 'architecture_docs'],
        'scripts': ['build_scripts', 'automation', 'dev_tools', 'ci_cd'],
        'examples': ['sample_usage', 'demo_apps', 'tutorials'],
        'assets': ['static_files', 'resources', 'media'],
    }
    return sections.get(purpose, ['overview', 'components', 'patterns'])


def get_purpose_description(purpose: str, languages: List[str]) -> str:
    """Generate description for a domain purpose."""
    lang_str = ', '.join(languages[:3]) if languages else 'mixed'

    descriptions = {
        'source': f"Main application source code ({lang_str}).\nCore business logic, primary modules, and entry points.",
        'tests': f"Test files and testing infrastructure ({lang_str}).\nUnit tests, integration tests, and fixtures.",
        'config': "Configuration files and settings.\nEnvironment setup, build config, and project metadata.",
        'docs': "Documentation files.\nREADME, guides, API docs, and architecture documentation.",
        'scripts': "Build scripts, automation, and tooling.\nCI/CD, deployment scripts, and development utilities.",
        'examples': "Example code and sample applications.\nDemonstrates usage patterns and best practices.",
        'assets': "Static assets and resources.\nImages, styles, and other non-code files.",
    }
    return descriptions.get(purpose, f"Project files ({lang_str}).")


def get_framework_domain(fw: FrameworkDetection) -> Optional[DomainSuggestion]:
    """Generate a domain suggestion for a specific framework."""
    framework_domains = {
        'ros2': DomainSuggestion(
            name='ros2',
            description="ROS2 packages and nodes.\nPublishers, subscribers, services, and launch files.",
            patterns=['**/package.xml', '**/*_node.py', 'launch/**/*'],
            keywords=['rclpy|rclcpp', 'Node|Publisher|Subscriber', 'create_publisher'],
            report_sections=['nodes', 'topics', 'services', 'launch_config'],
            source='framework',
        ),
        'platformio': DomainSuggestion(
            name='embedded',
            description="Embedded/firmware code.\nMicrocontroller code, HAL, and hardware interfaces.",
            patterns=['src/**/*.c', 'src/**/*.cpp', 'lib/**/*', 'include/**/*'],
            keywords=['void setup|void loop', 'GPIO|UART|SPI|I2C', 'ISR|interrupt'],
            report_sections=['hardware_interfaces', 'drivers', 'main_loop'],
            source='framework',
        ),
    }
    return framework_domains.get(fw.name)


def aggregate_commands(frameworks: List[FrameworkDetection]) -> Dict[str, List[str]]:
    """Aggregate command suggestions from all detected frameworks."""
    commands: Dict[str, List[str]] = {'test': [], 'lint': [], 'build': []}

    for fw in frameworks:
        for cmd_type, cmd_list in fw.suggested_commands.items():
            for cmd in cmd_list:
                if cmd not in commands[cmd_type]:
                    commands[cmd_type].append(cmd)

    return commands


def analyze_project(base_dir: Path) -> ProjectAnalysis:
    """Run complete project analysis."""
    # Scan files
    files = scan_files(base_dir)

    # Count languages and extensions
    lang_counts: Counter = Counter(f.language for f in files)
    ext_counts: Counter = Counter(f.extension for f in files if f.extension)
    total_lines = sum(f.lines for f in files)

    # Analyze directories
    directories = analyze_directories(files, base_dir)

    # Detect frameworks
    frameworks = detect_frameworks(base_dir, files)

    # Generate suggestions
    domain_suggestions = generate_domain_suggestions(files, directories, frameworks)
    command_suggestions = aggregate_commands(frameworks)

    # Warnings
    warnings = []
    if not files:
        warnings.append("No source files found in project")
    if not frameworks:
        warnings.append("No frameworks detected - using generic patterns")

    return ProjectAnalysis(
        base_directory=str(base_dir),
        languages=dict(lang_counts.most_common()),
        extensions=dict(ext_counts.most_common()),
        total_files=len(files),
        total_lines=total_lines,
        directories=directories[:20],  # Limit
        frameworks=frameworks,
        domain_suggestions=domain_suggestions,
        command_suggestions=command_suggestions,
        warnings=warnings,
    )


def format_domain_yaml(suggestion: DomainSuggestion) -> str:
    """Format a domain suggestion as YAML."""
    lines = [
        f"  - name: {suggestion.name}",
        f"    description: |",
    ]
    for desc_line in suggestion.description.split('\n'):
        lines.append(f"      {desc_line}")

    lines.append("    patterns:")
    for pattern in suggestion.patterns:
        lines.append(f'      - "{pattern}"')

    lines.append("    keywords:")
    for kw in suggestion.keywords:
        lines.append(f'      - "{kw}"')

    lines.append("    report_sections:")
    for section in suggestion.report_sections:
        lines.append(f"      - {section}")

    return '\n'.join(lines)


def write_project_config(analysis: ProjectAnalysis, output_path: Path) -> None:
    """Write project-specific configuration file."""
    try:
        import yaml
        HAS_YAML = True
    except ImportError:
        HAS_YAML = False

    config = {
        'generated_by': 'project_analyzer.py',
        'project_languages': list(analysis.languages.keys())[:5],
        'project_frameworks': [fw.name for fw in analysis.frameworks if fw.confidence >= 0.5],
        'domains': [asdict(d) for d in analysis.domain_suggestions],
        'commands': analysis.command_suggestions,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if HAS_YAML:
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    else:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Analyze project and suggest .claude configurations',
    )
    parser.add_argument(
        '--base-dir',
        type=Path,
        default=None,
        help='Project root directory (default: auto-detect)',
    )
    parser.add_argument(
        '--suggest-domains',
        action='store_true',
        help='Output suggested domain configurations as YAML',
    )
    parser.add_argument(
        '--suggest-commands',
        action='store_true',
        help='Output suggested test/build commands',
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Write suggestions to .claude/project_config.yaml',
    )
    parser.add_argument(
        '--pretty',
        action='store_true',
        help='Pretty-print JSON output',
    )

    args = parser.parse_args()

    # Find project root
    if args.base_dir:
        base_dir = args.base_dir.resolve()
    else:
        # Look for .claude directory to find project root
        # Script is in .claude/skills/, so go up 2 levels to project root
        script_dir = Path(__file__).parent.resolve()
        base_dir = script_dir.parent.parent.resolve()

    # Validate the base directory exists
    if not base_dir.exists():
        print(f"Error: Base directory does not exist: {base_dir}", file=sys.stderr)
        sys.exit(1)

    if not base_dir.is_dir():
        print(f"Error: Base path is not a directory: {base_dir}", file=sys.stderr)
        sys.exit(1)

    # Run analysis
    analysis = analyze_project(base_dir)

    if args.suggest_domains:
        print("# Suggested domain configurations")
        print("# Add these to .claude/skills/cc-prime-cw/domains.yaml")
        print()
        print("domains:")
        for suggestion in analysis.domain_suggestions:
            print(format_domain_yaml(suggestion))
            print()

    elif args.suggest_commands:
        print("# Suggested project commands")
        print(f"# Detected frameworks: {', '.join(fw.name for fw in analysis.frameworks)}")
        print()
        for cmd_type, commands in analysis.command_suggestions.items():
            if commands:
                print(f"{cmd_type}:")
                for cmd in commands:
                    print(f"  - {cmd}")

    elif args.apply:
        output_path = base_dir / '.claude' / 'project_config.yaml'
        write_project_config(analysis, output_path)
        print(f"Configuration written to: {output_path}")
        print(f"  Languages: {', '.join(list(analysis.languages.keys())[:5])}")
        print(f"  Frameworks: {', '.join(fw.name for fw in analysis.frameworks)}")
        print(f"  Domains suggested: {len(analysis.domain_suggestions)}")

    else:
        # Full JSON output
        output = {
            'base_directory': analysis.base_directory,
            'summary': {
                'total_files': analysis.total_files,
                'total_lines': analysis.total_lines,
                'languages': analysis.languages,
                'frameworks': [fw.name for fw in analysis.frameworks],
            },
            'directories': [asdict(d) for d in analysis.directories[:10]],
            'frameworks': [asdict(fw) for fw in analysis.frameworks],
            'domain_suggestions': [asdict(d) for d in analysis.domain_suggestions],
            'command_suggestions': analysis.command_suggestions,
            'warnings': analysis.warnings,
        }
        indent = 2 if args.pretty else None
        print(json.dumps(output, indent=indent))


if __name__ == '__main__':
    main()
