# dot-claude-template

Portable `.claude/` template providing skills, hooks, and session management for Claude Code.

## Session Workflow

```
/cc-learn        → Auto-detect project languages, frameworks, commands
/cc-prime-cw     → Load codebase context via analyst subagents
/cc-execute      → Execute tasks with structured subagent orchestration
/cc-conclude     → Generate commits, update docs, archive session
```

## Key Principles

- **Your context is precious, subagent context is expendable** — Subagents read 50-100K tokens internally, report back <=1000 tokens each
- **Hooks are deterministic, instructions are advisory** — Security enforcement lives in hooks, not prompts
- **Native permissions are the safety net, hooks add nuance** — settings.json deny/ask/allow catches basics; hooks handle complex logic like safe_delete_paths downgrades

## Security Model

4-tier hook-based validation (BLOCKED → ASK → WARN → ALLOW) layered on top of native permissions.
- `security-policy.yaml` — project-specific tier overrides and safe paths
- `validate-bash.sh` — command validation on every Bash call
- `validate-read.sh` / `validate-write.sh` — secret file protection for reads AND writes
- Bypass mode is disabled via `disableBypassPermissionsMode`

## Project Structure

- `.claude/hooks/` — Lifecycle hook scripts (security, tracking, session management)
- `.claude/skills/` — Slash command skills with YAML frontmatter
- `.claude/lib/` — Shared Python library (session_state.py, project_analyzer.py, verify_integrity.py)
- `.claude/session/` — Runtime state (gitignored)

## Development

- Python scripts use `uv run --with pyyaml python3` for YAML support
- Session state: `python3 .claude/lib/session_state.py {show|prime|log|conclude|reset|summary}`
- Integrity check: `python3 .claude/lib/verify_integrity.py`
