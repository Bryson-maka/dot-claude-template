# Claude Code Development Skills

**Purpose**: Skills for Claude Code (the CLI) when working with any project.

These skills help Claude Code understand codebases, follow efficient patterns, and maintain consistency when making changes.

## Skill Directories

| Skill | Command | Purpose |
|-------|---------|---------|
| `cc-prime-cw/` | `/cc-prime-cw` | Dynamic codebase discovery and session initialization |
| `cc-execute/` | `/cc-execute` | Subagent workflow patterns for complex tasks |
| `cc-conclude/` | `/cc-conclude` | Session wrap-up, README updates, and git commit workflow |
| `cc-learn/` | `/cc-learn` | **Auto-discover** project patterns and evolve configuration |

**Shared Library** (`.claude/lib/`):
- `session_state.py` - Session state management used by all skills
- `project_analyzer.py` - Project analysis and configuration discovery

**Note**: In Claude Code, skill directory names become slash commands automatically. The `SKILL.md` file in each directory defines the command behavior.

## Quick Start

```bash
# 0. (Optional) Auto-configure for your project
/cc-learn --apply

# 1. Start session - load codebase context
/cc-prime-cw

# 2. Execute work with subagent orchestration
/cc-execute Fix the authentication bug

# 3. Wrap up - commit and archive
/cc-conclude
```

## Installing to a New Project

This `.claude/` directory is a **portable template**. To use it in another project:

### Option 1: Copy and Run (Recommended)

```bash
# Copy .claude directory to your project
cp -r /path/to/template/.claude /path/to/your-project/

# Navigate to your project
cd /path/to/your-project

# Run priming - this auto-discovers your project structure
/cc-prime-cw
```

That's it. The `/cc-prime-cw` command will:
- Detect your project's languages and frameworks
- Scan for relevant files in each domain
- Generate fresh `state.json` and `manifest.json` for YOUR project
- Initialize session tracking

### Option 2: Manual Reset First

If you want to explicitly clear any existing session data:

```bash
# Copy .claude directory
cp -r /path/to/template/.claude /path/to/your-project/
cd /path/to/your-project

# Reset session state
python3 .claude/lib/session_state.py reset

# Then prime
/cc-prime-cw
```

### What Gets Regenerated

| Component | Behavior |
|-----------|----------|
| `.claude/session/` | **Regenerated** - Contains runtime data specific to each project |
| `.claude/lib/` | **Portable** - Shared utilities work anywhere |
| `.claude/skills/` | **Portable** - Skills are project-agnostic |
| `.claude/project_config.yaml` | **Optional** - Run `/cc-learn --apply` to generate project-specific config |

### Session Directory Contents

The `.claude/session/` directory is gitignored and contains:

| File | Purpose | When Created |
|------|---------|--------------|
| `state.json` | Current session state (timestamps, journal, verifications) | `/cc-prime-cw` |
| `manifest.json` | Discovery manifest (domains, file lists, keywords) | `/cc-prime-cw` |
| `history.jsonl` | Archived sessions (append-only log) | `/cc-conclude` |

These are **project-specific** and **session-specific** - they should never be committed to git.

## Adaptive Configuration

This template **automatically adapts** to your project. Run `/cc-learn` to:

1. **Scan** your codebase for languages, frameworks, and directory patterns
2. **Generate** domain configurations specific to your project
3. **Detect** test, lint, and build commands
4. **Write** project-specific config to `.claude/project_config.yaml`

The system uses a layered configuration:
```
.claude/project_config.yaml    <- Auto-generated (highest priority)
domains.yaml / workflow.yaml   <- Template defaults (fallback)
```

### When to Run `/cc-learn`

- **First time**: When starting work on a new project
- **After changes**: When adding new languages, frameworks, or major restructuring
- **Periodically**: To keep configuration aligned with project evolution

### Example

```bash
# Analyze project and see suggestions
/cc-learn

# Auto-apply discovered configuration
/cc-learn --apply

# Then prime with the new config
/cc-prime-cw
```

## How to Use

### Context Priming (`/cc-prime-cw`)

Run at the start of a session to load project context:

```
/cc-prime-cw              # Basic context priming
```

This command:
1. Discovers files using glob patterns from `domains.yaml`
2. Spawns analyst subagents to read and synthesize findings
3. Loads dense project understanding into your context window
4. Writes session state to `.claude/session/state.json`

### Task Execution (`/cc-execute`)

Run to execute structured work using subagents:

```
/cc-execute Fix the authentication bug
/cc-execute Add input validation to the API
/cc-execute  # Will ask what to work on
```

This command provides:
- Structured phase workflow (understand → plan → investigate → execute → verify)
- Subagent templates for investigation, implementation, verification
- Adversarial challenge protocol for high-stakes claims
- Execution logging to session state

### Session Conclude (`/cc-conclude`)

Run at the end of a session to wrap up work:

```
/cc-conclude              # Full workflow with prompts
/cc-conclude --commit     # Quick commit workflow
/cc-conclude --no-readme  # Skip README update check
```

This command provides:
- Session summary generation from execution journal and git state
- README.md update detection and drafting
- Git commit workflow with intelligent message generation
- Session archival to `.claude/session/history.jsonl`

## Session State System

### File Locations

| File | Purpose |
|------|---------|
| `.claude/session/state.json` | Current session tracking (primed_at, journal, verifications) |
| `.claude/session/manifest.json` | Detailed file-level discovery data |
| `.claude/session/history.jsonl` | Archived sessions (appended on conclude) |

### State Schema (v1.0)

```json
{
  "schema_version": "1.0",
  "primed_at": "2024-01-15T10:30:00Z",
  "concluded_at": null,
  "domains": ["source", "config", "tests"],
  "foundation_docs": ["README.md", "CLAUDE.md"],
  "execution_journal": [
    {"ts": "...", "type": "task_created", "subject": "Fix bug", "task_id": "1"},
    {"ts": "...", "type": "subagent_spawned", "role": "investigator", "model": "sonnet"}
  ],
  "subagents": [
    {"role": "investigator", "type": "Explore", "model": "sonnet", "description": "..."}
  ],
  "verification_results": [
    {"type": "test", "passed": true, "details": "18 tests passed"}
  ],
  "files_modified": ["src/auth.py", "tests/test_auth.py"]
}
```

### Session State CLI

```bash
# View current state
python3 .claude/lib/session_state.py show --pretty

# View execution summary
python3 .claude/lib/session_state.py summary

# Log events manually (usually done by skills)
python3 .claude/lib/session_state.py log --type task_created --subject "Fix bug" --task-id "1"
python3 .claude/lib/session_state.py log --type subagent --role investigator --model sonnet
python3 .claude/lib/session_state.py log --type verification --passed --details "Tests pass"
python3 .claude/lib/session_state.py log --type file_modified --file "src/auth.py"

# Conclude and archive session
python3 .claude/lib/session_state.py conclude

# Reset for fresh session
python3 .claude/lib/session_state.py reset
```

## Directory Structure

```
.claude/
├── session/                    # Runtime session data
│   ├── state.json              # Current session state
│   ├── manifest.json           # Discovery manifest
│   └── history.jsonl           # Archived sessions
├── lib/                        # Shared Python modules
│   ├── __init__.py
│   ├── session_state.py        # Session management
│   └── project_analyzer.py     # Project analysis
├── skills/                     # Skill commands (/slash-commands)
│   ├── README.md
│   ├── cc-prime-cw/            # Context priming
│   │   ├── SKILL.md
│   │   ├── discover.py
│   │   └── domains.yaml
│   ├── cc-execute/             # Task execution
│   │   ├── SKILL.md
│   │   ├── discover.py
│   │   └── workflow.yaml
│   ├── cc-conclude/            # Session conclusion
│   │   ├── SKILL.md
│   │   ├── analyze_changes.py
│   │   └── workflow.yaml
│   └── cc-learn/               # Configuration learning
│       ├── SKILL.md
│       ├── learn.py
│       └── config.yaml
├── project_config.yaml         # Auto-generated project config
└── settings.local.json         # User settings
```

## Session Lifecycle

```
/cc-prime-cw     → Load context (session start)
        ↓
   [writes state.json + manifest.json]
        ↓
/cc-execute      → Do work (session active)
        ↓              ↑
   [logs to state.json]  [reads project config]
        ↓
/cc-conclude     → Wrap up (session end)
        ↓              ↑
   [reads state.json]  [reads git state]
        ↓
   [archives to history.jsonl]
```

## Supported Project Types

### Standard Projects

| Type | Indicators | Test Command |
|------|------------|--------------|
| Python | `pyproject.toml`, `setup.py` | `pytest` |
| Node.js | `package.json` | `npm test` |
| Rust | `Cargo.toml` | `cargo test` |
| Go | `go.mod` | `go test ./...` |
| Make | `Makefile` | `make test` |

### Web Frameworks

| Type | Indicators | Test Command |
|------|------------|--------------|
| Next.js | `next.config.js` | `npm test`, `vitest` |
| React/Vite | `vite.config.ts` | `vitest`, `jest` |
| FastAPI | `main.py` (with FastAPI imports) | `pytest` |
| Django | `manage.py`, `settings.py` | `python manage.py test` |

### Robotics & Embedded

| Type | Indicators | Test Command |
|------|------------|--------------|
| ROS2 | `package.xml`, `colcon.meta` | `colcon test` |
| Arduino | `*.ino`, `platformio.ini` | `pio test` |
| PlatformIO | `platformio.ini` | `pio test` |
| Zephyr | `prj.conf`, `west.yml` | `west twister` |
| ESP-IDF | `sdkconfig` | `idf.py test` |
| CMake (embedded) | `CMakeLists.txt`, `toolchain.cmake` | `ctest` |

### Domain Analysis (for Robotics)

| Domain | Patterns | Focus Areas |
|--------|----------|-------------|
| `firmware` | `firmware/**/*.c`, `*.ino` | HAL, drivers, ISRs |
| `ros2` | `package.xml`, `*_node.py` | Nodes, topics, services |
| `controls` | `control/**/*`, `**/pid*.py` | PID, Kalman, sensors |
| `simulation` | `*.urdf`, `*.world` | Gazebo, physics models |

## Customization

### Configuration Files

| Skill | Config File | Purpose |
|-------|-------------|---------|
| cc-prime-cw | `domains.yaml` | Domain patterns, foundation docs, report sections |
| cc-execute | `workflow.yaml` | Subagent roles, test commands, adversarial config |
| cc-conclude | `workflow.yaml` | README triggers, commit types, git config |

### Adding Project-Specific Domains

Edit `.claude/skills/cc-prime-cw/domains.yaml`:

```yaml
domains:
  - name: my_domain
    description: |
      Description of what this domain covers.
    patterns:
      - "src/my_module/**/*.py"
    keywords:
      - "MyClass|my_function"
    report_sections:
      - key_components: "Main classes and functions"
```

### Adding Project-Specific Test Commands

Edit `.claude/skills/cc-execute/workflow.yaml`:

```yaml
project_detection:
  my_framework:
    indicators:
      - my_config.toml
    test_commands:
      - "my-test-runner"
    lint_commands:
      - "my-linter"
```

## Token Budget Philosophy

**Subagent context is expendable** - they read thoroughly and synthesize.
**Main agent context is precious** - receive only dense findings.

| Approach | Tokens Used | Understanding |
|----------|-------------|---------------|
| Read 10 files directly | ~100K | Raw code, limited reasoning room |
| 10 subagents report | ~5K | Synthesized findings, full reasoning room |

This allows understanding 50,000+ lines of code while consuming only ~10K tokens.

## Subagent Roles

| Role | Type | Model | When to Use |
|------|------|-------|-------------|
| **Investigator** | Explore | Sonnet | Read files, verify assumptions |
| **Implementer** | general-purpose | Sonnet | Make code changes |
| **Verifier** | general-purpose | Sonnet | Run tests, confirm changes |
| **Adversary** | Explore | Sonnet | Challenge claims, find holes |
| **Reasoner** | Explore | Opus | Complex analysis, design decisions |

## Troubleshooting

### State Issues

```bash
# View current state
python3 .claude/lib/session_state.py show --pretty

# Reset if state is corrupted
python3 .claude/lib/session_state.py reset
```

### Discovery Issues

```bash
# Test discovery manually
uv run --with pyyaml python3 .claude/skills/cc-prime-cw/discover.py --pretty

# Test project detection
uv run --with pyyaml python3 .claude/skills/cc-execute/discover.py --pretty
```

### Git Analysis Issues

```bash
# Test git analysis
uv run --with pyyaml python3 .claude/skills/cc-conclude/analyze_changes.py --summary
```
