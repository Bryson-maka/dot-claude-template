# settings.json Guard Rules

**DO NOT** modify `.claude/settings.json` without reading this file first.

## Critical Rules

1. **Do NOT add `Read(.env*)` to the deny list.**
   `.env` protection is handled by `validate-read.sh` hook which allows safe files
   like `.env.example`, `.env.sample`, `.env.template`. Adding `Read(.env*)` to deny
   will block ALL `.env*` files including safe ones, AND cause sibling tool call
   cascade failures that break parallel reads.

2. **Do NOT remove hook registrations.**
   Every hook in settings.json serves a specific purpose:
   - `PreToolUse/Bash` → `validate-bash.sh`: 4-tier security model
   - `PreToolUse/Read` → `validate-read.sh`: Secret file protection (reads)
   - `PreToolUse/Edit|Write` → `validate-write.sh`: Secret file protection (writes)
   - `PostToolUse/Edit|Write` → `track-file-changes.sh`: Change tracking
   - `PostToolUse/Bash` → `notify-bash-success.sh`: Silent command acknowledgment
   - `PostToolUseFailure/Bash` → `notify-bash-failure.sh`: Denial/failure feedback to agent
   - `SessionStart` → `session-init.sh`: Environment setup (fires on startup, resume, clear, compact)
   - `PreCompact` → `pre-compact-save.sh`: State preservation before context trim
   - `SubagentStop` → `validate-subagent-output.sh`: Quality gate for subagent responses
   - `SessionEnd` → `session-end.sh`: Session archival

3. **Do NOT reorder tiers in `validate-bash.sh`.**
   Blocked patterns MUST be checked BEFORE safe pass-through. Wrong order allows
   bypass via chaining (e.g., `git add . && rm -rf /`).

4. **Do NOT remove `disableBypassPermissionsMode`.**
   This prevents `--dangerously-skip-permissions` from disabling the entire
   security model. Must remain set to `"disable"`.

5. **Do NOT create deny/ask conflicts.**
   Deny rules take absolute precedence — if a pattern appears in both deny and ask,
   the ask prompt will never fire. Keep destructive commands in ask only; reserve
   deny for catastrophic-only patterns (e.g., `rm -rf /`).

## Integrity Check

Run `python3 .claude/lib/verify_integrity.py` to validate the `.claude/` directory
hasn't drifted from template requirements.

Template version: see `.claude/TEMPLATE_VERSION`
