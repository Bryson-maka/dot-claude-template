# dot-claude-template

A portable `.claude/` directory template that gives [Claude Code](https://docs.anthropic.com/en/docs/claude-code) an agentic layer for working with any codebase.

## What This Is

This repository provides a structured skill system for Claude Code. The `.claude/` directory contains:

- **Skills** - Slash commands (`/cc-prime-cw`, `/cc-execute`, `/cc-conclude`, `/cc-learn`) that orchestrate multi-agent workflows
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

## Documentation

See **[.claude/skills/README.md](.claude/skills/README.md)** for complete documentation:

- Skill commands and workflows
- Session lifecycle
- Configuration customization
- Supported project types (Python, Node.js, Rust, Go, ROS2, Arduino, and more)

## Session Workflow

```
/cc-prime-cw     Load codebase context via analyst subagents
      |
/cc-execute      Execute tasks with structured subagent orchestration
      |
/cc-conclude     Generate commit messages, update docs, archive session
```

## License

[MIT](LICENSE)
