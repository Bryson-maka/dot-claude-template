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

**Hooks** (`.claude/hooks/`):
- `session-init.sh` - SessionStart: initialize environment, detect unconcluded sessions
- `validate-bash.sh` - PreToolUse: block dangerous commands with structured deny responses
- `track-file-changes.sh` - PostToolUse: log file modifications to session state
- `validate-subagent-output.sh` - SubagentStop: ensure subagent responses meet quality threshold
- `task-completion-gate.sh` - TaskCompleted: log completions, gate on validation (extensible)
- `session-checkpoint.sh` - Stop: checkpoint session state between responses
- `pre-compact-save.sh` - PreCompact: preserve state before context window trimming
- `session-end.sh` - SessionEnd: log session termination for archival

**Rules** (`.claude/rules/`):
- `hooks.md` - Path-scoped rules for writing hook scripts
- `skills.md` - Path-scoped rules for authoring SKILL.md files
- `python.md` - Path-scoped rules for .claude Python scripts

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
├── settings.json               # Shared project settings (hooks, permissions)
├── settings.local.json         # Personal settings (gitignored)
├── session/                    # Runtime session data (gitignored)
│   ├── state.json              # Current session state
│   ├── manifest.json           # Discovery manifest
│   └── history.jsonl           # Archived sessions
├── hooks/                      # Reusable hook scripts
│   ├── session-init.sh         # SessionStart: env setup, state validation
│   ├── validate-bash.sh        # PreToolUse: block dangerous commands
│   ├── track-file-changes.sh   # PostToolUse: log file modifications
│   ├── validate-subagent-output.sh  # SubagentStop: quality gate
│   ├── task-completion-gate.sh # TaskCompleted: completion validation
│   ├── session-checkpoint.sh   # Stop: checkpoint session state
│   ├── pre-compact-save.sh     # PreCompact: save before context trim
│   └── session-end.sh          # SessionEnd: log termination
├── rules/                      # Path-scoped rules (loaded by glob match)
│   ├── hooks.md                # Rules for .claude/hooks/**/*.sh
│   ├── skills.md               # Rules for .claude/skills/**/SKILL.md
│   └── python.md               # Rules for .claude/**/*.py
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
└── project_config.yaml         # Auto-generated project config
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

## Hooks System

Hooks are lifecycle event handlers that run shell commands, LLM prompts, or subagents at specific points during Claude Code operation. This template includes working examples of the three most useful hook patterns.

### Hook Events Reference

| Event | When it Fires | Can Block? | Use Case |
|-------|---------------|------------|----------|
| `SessionStart` | Session begins/resumes | No | Set environment variables, initialize state |
| `UserPromptSubmit` | User submits prompt | Yes | Input validation, prompt rewriting |
| `PreToolUse` | Before tool executes | Yes (allow/deny/ask) | **Security validation**, command blocking |
| `PostToolUse` | After tool succeeds | No | **Change tracking**, notifications |
| `PostToolUseFailure` | After tool fails | No | Error logging, retry logic |
| `PermissionRequest` | Permission dialog shown | Yes | Auto-approve/deny by policy |
| `SubagentStart` | Subagent spawns | No | Subagent monitoring |
| `SubagentStop` | Subagent finishes | Yes | Result validation |
| `Stop` | Claude finishes responding | Yes | **Session checkpoints**, completion gates |
| `TaskCompleted` | Task marked complete | Yes | Run tests before accepting completion |
| `PreCompact` | Before context compaction | No | Save state before context is trimmed |
| `SessionEnd` | Session terminates | No | Cleanup, final archival |

### Hook Types

```json
// Shell command (fastest, most common)
{ "type": "command", "command": "./script.sh", "timeout": 10 }

// Single LLM evaluation (semantic validation)
{ "type": "prompt", "prompt": "Evaluate if $ARGUMENTS is safe", "timeout": 30 }

// Multi-turn subagent (complex validation)
{ "type": "agent", "prompt": "Review changes for security issues", "timeout": 60 }
```

### Hook Configuration Locations

Hooks can be defined in multiple places (all are merged at session start):

| Location | Scope | Committed? |
|----------|-------|------------|
| `~/.claude/settings.json` | All projects (user) | N/A |
| `.claude/settings.json` | This project (shared) | Yes |
| `.claude/settings.local.json` | This project (personal) | No |
| Skill YAML frontmatter (`hooks:`) | While skill is active | Yes |

### Included Hook Scripts

**Global hooks** (always active via `settings.json`):

| Script | Event | Purpose |
|--------|-------|---------|
| `session-init.sh` | SessionStart | Set env vars via `$CLAUDE_ENV_FILE`, detect unconcluded sessions |
| `validate-bash.sh` | PreToolUse | Block destructive commands, warn on side-effect commands |
| `session-checkpoint.sh` | Stop | Checkpoint session state between responses |
| `validate-subagent-output.sh` | SubagentStop | Ensure subagent responses are substantive (>10 words) |
| `task-completion-gate.sh` | TaskCompleted | Log completions, extensible validation gate |
| `pre-compact-save.sh` | PreCompact | Save state before context window is trimmed |
| `session-end.sh` | SessionEnd | Log session termination reason |

**Skill-scoped hooks** (active only while skill runs):

| Skill | Event | Purpose |
|-------|-------|---------|
| cc-prime-cw | SubagentStop(Explore) | Validate analyst subagent outputs |
| cc-execute | PostToolUse(Edit\|Write) | Track file changes during task execution |
| cc-conclude | PreToolUse(Bash) | LLM prompt hook: verify git commands are safe for conclude phase |
| cc-learn | PostToolUse(Write) | Track config file changes |

### Writing Custom Hooks

Hook scripts receive JSON on stdin and communicate via exit codes and stdout:

```bash
#!/usr/bin/env bash
set -euo pipefail

INPUT=$(cat)
# Parse with python3 (portable, jq may not be installed)
VALUE=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['tool_input']['command'])")

# Decision: exit 0=allow, exit 2=block
if echo "$VALUE" | grep -q "dangerous"; then
  echo "Blocked: dangerous command" >&2
  exit 2
fi

# Fine-grained PreToolUse decisions:
# echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"..."}}'

exit 0
```

### Hooks in Skill Frontmatter

Skills can define scoped hooks that only run while the skill is active. Use this for hooks that are relevant to a specific skill's purpose, not global safety:

```yaml
---
name: cc-execute
hooks:
  PostToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/track-file-changes.sh"
          timeout: 5
---
```

**Scoping principle**: Global safety hooks (bash validation) go in `settings.json`. Skill-specific hooks (file change tracking during execution) go in skill frontmatter. Don't duplicate hooks across both — they would fire twice.

## Path-Scoped Rules

Rules in `.claude/rules/*.md` are automatically loaded when Claude works on files matching their `paths:` frontmatter globs. This provides targeted context without polluting the global instruction set.

```yaml
---
paths:
  - "src/api/**/*.ts"
---
# API Rules
- All endpoints must include input validation
- Use Zod schemas for request/response types
```

This template includes rules for hook scripts, skill authoring, and Python code within `.claude/`.

## Permissions

The `.claude/settings.json` file defines tool permissions using allow/deny patterns:

```json
{
  "permissions": {
    "allow": ["Bash(git status*)", "Read", "Glob"],
    "deny": ["Bash(rm -rf /)*", "Read(.env*)"]
  }
}
```

Patterns support globs. The `allow` list bypasses permission prompts; `deny` blocks entirely.

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
