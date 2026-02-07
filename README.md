# dot-claude-template

A portable `.claude/` directory template that gives [Claude Code](https://docs.anthropic.com/en/docs/claude-code) an agentic layer for working with any codebase.

## What This Is

This repository provides a structured skill system for Claude Code that demonstrates advanced patterns: skills with YAML frontmatter, lifecycle hooks, session state management, and subagent orchestration. The `.claude/` directory contains:

- **Skills** - Slash commands (`/cc-prime-cw`, `/cc-execute`, `/cc-conclude`, `/cc-learn`) that orchestrate multi-agent workflows
- **Hooks** - Lifecycle event handlers for security validation, change tracking, and state preservation
- **Session Management** - Persistent state tracking across your coding session
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
├── hooks/                 # Lifecycle hook scripts
│   ├── session-init.sh        # SessionStart: env setup + state check
│   ├── validate-bash.sh       # PreToolUse: block dangerous commands
│   ├── track-file-changes.sh  # PostToolUse: log file modifications
│   ├── validate-subagent-output.sh  # SubagentStop: quality gate
│   ├── pre-compact-save.sh    # PreCompact: save before context trim
│   └── session-end.sh         # SessionEnd: log termination
├── lib/                   # Shared Python library
├── skills/                # Slash command skills
└── session/               # Runtime state (gitignored)
```

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
