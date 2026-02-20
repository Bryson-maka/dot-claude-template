# dot-claude-template

A portable `.claude/` directory template that gives [Claude Code](https://docs.anthropic.com/en/docs/claude-code) an agentic layer for working with any codebase.

## What This Is

This repository provides a structured skill system for Claude Code that demonstrates advanced patterns: skills with YAML frontmatter, lifecycle hooks, session state management, and subagent orchestration. The `.claude/` directory contains:

- **Skills** - Slash commands (`/cc-prime-cw`, `/cc-execute`, `/cc-conclude`, `/cc-learn`) that orchestrate multi-agent workflows
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
```

### Option 2: Add to Existing Project

```bash
# Copy .claude directory into your project
cp -r /path/to/dot-claude-template/.claude /path/to/your-project/
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
├── status_lines/          # Claude Code status line scripts
│   └── status_line.py         # Model, context bar, cost, cwd
├── skills/                # Slash command skills
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

Paths are relative to the project root. Symlinks are resolved before checking. The feature is **opt-in** — leave as `[]` or omit the key to disable. Run `/cc-learn` to auto-detect sensible defaults for your project type.

This is defense-in-depth layered on top of the 4-tier security model. Bash commands that can't be statically analyzed for write targets escalate to the ASK tier for user review.

## Documentation

See **[.claude/skills/README.md](.claude/skills/README.md)** for skill documentation and directory structure details.

## Session Workflow

```
/cc-learn        (optional) Auto-detect project config
      |
/cc-prime-cw     Load codebase context via analyst subagents
      |
/cc-execute      Execute tasks with structured subagent orchestration
      |               hooks: validate commands, track changes
/cc-conclude     Generate commit messages, update docs, archive session
```

## License

[MIT](LICENSE)
