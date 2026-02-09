# Claude Code Skills

Portable skill system for Claude Code. Clone this `.claude/` directory into any project.

## Skills

| Command | Purpose |
|---------|---------|
| `/cc-prime-cw` | Load codebase context via analyst subagents |
| `/cc-execute [task]` | Structured task execution with subagent orchestration |
| `/cc-conclude` | Session wrap-up, README updates, git commit workflow |
| `/cc-learn` | Auto-discover project patterns and evolve configuration |

## Quick Start

```bash
/cc-learn --apply     # (Optional) Auto-configure for your project
/cc-prime-cw          # Load codebase context
/cc-execute Fix bug   # Do work
/cc-conclude          # Commit and archive
```

## Session Lifecycle

```
/cc-prime-cw     -> Load context, write state.json + manifest.json
       |
/cc-execute      -> Do work, log to state.json
       |
/cc-conclude     -> Summarize, commit, archive to history.jsonl
```

## Directory Structure

```
.claude/
├── settings.json          # Hooks + permissions (committed)
├── settings.local.json    # Personal settings (gitignored)
├── hooks/                 # Lifecycle hook scripts
│   ├── session-init.sh         # SessionStart: env setup + integrity check
│   ├── validate-bash.sh        # PreToolUse/Bash: 4-tier security model
│   ├── validate-read.sh        # PreToolUse/Read: secret file protection
│   ├── track-file-changes.sh   # PostToolUse/Edit|Write: log modifications
│   ├── notify-bash-success.sh  # PostToolUse/Bash: silent cmd acknowledgment
│   ├── notify-bash-failure.sh  # PostToolUseFailure/Bash: denial feedback
│   ├── validate-subagent-output.sh  # SubagentStop: quality gate (skill-scoped)
│   ├── pre-compact-save.sh     # PreCompact: save before context trim
│   └── session-end.sh          # SessionEnd: log termination
├── lib/                   # Shared Python library
│   ├── session_state.py        # Session state management
│   └── project_analyzer.py     # Project analysis + framework detection
├── skills/                # Slash command skills (each has SKILL.md)
│   ├── cc-prime-cw/       # Context priming
│   ├── cc-execute/        # Task execution
│   ├── cc-conclude/       # Session conclusion
│   └── cc-learn/          # Configuration learning
└── session/               # Runtime state (gitignored)
```

## Installing to Another Project

```bash
cp -r /path/to/template/.claude /path/to/your-project/
cd /path/to/your-project
/cc-prime-cw    # Auto-discovers your project structure
```

## Troubleshooting

```bash
python3 .claude/lib/session_state.py show --pretty   # View state
python3 .claude/lib/session_state.py reset            # Reset state
```
