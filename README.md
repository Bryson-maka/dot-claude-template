# dot-claude-template

A portable `.claude/` directory template that gives [Claude Code](https://docs.anthropic.com/en/docs/claude-code) an agentic layer for working with any codebase.

## What This Is

This repository provides a structured skill system for Claude Code that demonstrates advanced patterns: skills with YAML frontmatter, lifecycle hooks, session state management, and agent team orchestration. The `.claude/` directory contains:

- **Skills** - Slash commands (`/cc-prime-cw`, `/cc-execute`, `/cc-conclude`) that orchestrate multi-agent workflows
- **Hooks** - Lifecycle event handlers for security validation, change tracking, and state preservation
- **Session Management** - Persistent state tracking across your coding session
- **Status Line Telemetry** - Command-driven status line with context usage, cost, and workflow state
- **Adaptive Configuration** - Auto-detection of project languages, frameworks, and patterns

## Quick Start

### Option 1: Clone as Project Starter

```bash
git clone https://github.com/Bryson-maka/dot-claude-template.git my-project
cd my-project
rm -rf .git && git init  # Start fresh git history
# Placeholder active.md is already correct for a fresh project
```

### Option 2: Add to Existing Project

```bash
# Use the install script (recommended — handles cleanup)
/path/to/dot-claude-template/.claude/install.sh /path/to/your-project

# Or copy manually and run /cc-prime-cw to initialize
cp -r /path/to/dot-claude-template/.claude /path/to/your-project/
```

### Option 3: Update an Existing Installation

```bash
# Preview what would change
/path/to/dot-claude-template/.claude/install.sh /path/to/your-project --update --dry

# Apply updates (only changed template files — preserves handoff, session, project config)
/path/to/dot-claude-template/.claude/install.sh /path/to/your-project --update
```

### Then

```bash
# Start Claude Code and prime the context
/cc-prime-cw
```

The system automatically adapts to your project structure.

## What's Inside

```
.claude/
├── settings.json          # Shared hooks + permissions (committed)
├── settings.local.json    # Personal settings (gitignored)
├── security-policy.yaml   # Project-specific security tier overrides
├── hooks/                 # Lifecycle hook scripts
│   ├── session-init.sh        # SessionStart: env setup + state check
│   ├── validate-bash.sh       # PreToolUse/Bash: 4-tier command validation + directory scope
│   ├── validate-read.sh       # PreToolUse/Read: secret file protection
│   ├── validate-write.sh      # PreToolUse/Edit|Write|NotebookEdit: secret + directory scope
│   ├── track-file-changes.sh  # PostToolUse/Edit|Write|NotebookEdit: log file modifications
│   ├── notify-bash-success.sh # PostToolUse/Bash: silent acknowledgment
│   ├── notify-bash-failure.sh # PostToolUseFailure/Bash: denial feedback
│   ├── validate-subagent-output.sh  # SubagentStop: quality gate
│   ├── pre-compact-save.sh    # PreCompact: save before context trim
│   └── session-end.sh         # SessionEnd: log termination
├── TEMPLATE_VERSION       # Template version for drift detection
├── SETTINGS_GUARD.md      # Rules for modifying settings.json
├── lib/                   # Shared Python library
│   ├── session_state.py       # Session state tracking (schema v1.1, team-aware)
│   ├── git_context.py         # Git intelligence (volatility, coupling, recent changes)
│   ├── project_analyzer.py    # Auto-detect languages, frameworks, patterns
│   ├── path_validator.py      # Symlink-safe path resolution
│   └── verify_integrity.py    # Configuration drift detection
├── status_lines/          # Claude Code status line scripts
│   └── status_line.py         # Model, context bar, cost, cwd
├── skills/                # Slash command skills
├── handoff/               # Session handoff pipeline
│   ├── active.md              # Current handoff (read by cc-prime-cw)
│   └── archive/               # Archived handoffs ({date}_{slug}.md)
└── session/               # Runtime state (gitignored)
CLAUDE.md                  # Root project context for Claude Code
```

## Integrity Checking

After copying the `.claude/` directory to a downstream project, configuration can drift over multiple Claude Code sessions. The template includes a self-integrity checker that catches common drift patterns:

```bash
# Run manually
python3 .claude/lib/verify_integrity.py

# Runs automatically on session startup via session-init.sh
```

The checker validates: settings schema, status line wiring, `disableBypassPermissionsMode`, deny/ask conflicts, required hook registrations (PreToolUse with NotebookEdit, PostToolUse, PreCompact, SessionStart), security tier ordering, script existence/permissions, security policy presence (including `allowed_write_directories` schema), SETTINGS_GUARD.md cross-reference, and MCP server settings. See [SETTINGS_GUARD.md](.claude/SETTINGS_GUARD.md) for the rules enforced.

## Status Line

The template ships with a command-based Claude Code status line in `.claude/settings.json`:

- Script: `.claude/status_lines/status_line.py`
- Shows: model name, context window bar with percentage and tokens remaining, session cost, current working directory
- Colors shift from green to yellow to red to magenta as context usage climbs

## Directory-Scoped Write Restrictions

Optionally restrict which directories Claude Code can write to. When enabled, Edit, Write, NotebookEdit, and Bash file-writing commands are denied if the target path falls outside the allowed list. Reads are never restricted.

Configure in `.claude/security-policy.yaml`:

```yaml
allowed_write_directories:
  - src
  - tests
  - docs
  - .claude/session
```

Paths are relative to the project root. Symlinks are resolved before checking. The feature is **opt-in** — leave as `[]` or omit the key to disable.

This is defense-in-depth layered on top of the 4-tier security model. Bash commands that can't be statically analyzed for write targets escalate to the ASK tier for user review.

## Documentation

See **[.claude/skills/README.md](.claude/skills/README.md)** for skill documentation and directory structure details.

## Session Workflow

```
/cc-prime-cw     Load codebase context via analyst subagents
      |               auto-detects project config if missing
/cc-execute      Execute tasks with agent team orchestration
      |               adversarial challenge on every task
/cc-conclude     Generate handoff, commit, update docs, archive
```

## License

[MIT](LICENSE)
