---
name: cc-conclude
description: Wrap up session with summary, README updates, and git commit workflow
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash, Edit, Write, Task
argument-hint: [--commit | --no-readme]
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: prompt
          prompt: "A git command is about to run: $ARGUMENTS. The user is in a session conclusion workflow (committing, pushing, archiving). Verify this command is safe for a conclude phase - it should be a read-only git command (status, diff, log) OR a standard commit/push. Block any destructive git operations (reset, rebase, force push, branch delete). Respond with {\"ok\": true} or {\"ok\": false, \"reason\": \"explanation\"}."
          timeout: 15
---

# Session Conclusion

Wrap up your Claude Code session with a summary, README check, and git commit.

## Current State

!`uv run --with pyyaml python3 .claude/skills/cc-conclude/analyze_changes.py 2>/dev/null || echo '{"error": "Analysis failed - check git status manually"}'`

The output above includes:
- **git_state**: Branch, remote tracking, staged/unstaged/untracked counts
- **changes**: List of modified files with status and line counts
- **triggers**: README update triggers detected
- **recommendations**: Prioritized git commands to run (stage, commit, push)
- **session**: Context from `/cc-prime-cw` if run earlier (domains analyzed, foundation docs)

---

## Arguments

- `--commit`: Quick commit (skip README check, minimal prompts)
- `--no-readme`: Skip README check but full git workflow
- (default): Full workflow with all checks

---

## Workflow

### Phase 1: Gather

Run git commands to understand current state:
```bash
git status --short
git diff --stat
git log --oneline -5
```

### Phase 2: Summarize

The analysis output above includes session context from `.claude/session/state.json`:
- `session.tasks_completed`: Count of completed tasks
- `session.subagents_spawned`: Count of subagents used
- `session.verifications`: Test/lint/adversarial results
- `session.files_modified_by_session`: Files modified during execution

**To view detailed session state**:
```bash
python3 .claude/lib/session_state.py show --pretty
python3 .claude/lib/session_state.py summary
```

Generate session summary using this data:
- **Status**: COMPLETED, IN_PROGRESS, or BLOCKED
- **Tasks**: From execution_journal task_completed entries
- **Subagents**: Count and roles from subagents list
- **Verification**: Test results and adversarial challenge outcomes
- **Files Changed**: From git diff + files_modified list
- **Open Items**: Incomplete work or follow-ups

### Phase 3: README Check (unless --no-readme or --commit)

If the git state above shows README triggers detected:
1. Analyze what changed (new directories, config files, .claude content)
2. Draft README updates
3. Present draft for user approval
4. Apply if approved

### Phase 4: Git Commit

**Follow the `recommendations` array above** - it contains the exact commands to run:

1. **Stage files first**: If recommendations include `stage_modified` or `stage_new`, run those commands
   - The `command` field has the exact `git add` command with file paths
   - Priority 1 recommendations MUST be done before committing

2. **Message**: Generate conventional commit message

   Format: `<type>: <description>`

   Types: feat, fix, docs, refactor, test, chore, build

3. **Commit**: Run the staged + commit in one command: `git add <files> && git commit -m "..."`
4. **Push** (optional): If recommendations include `push`, offer to push to remote

---

## Safety

- Never force pushes
- Never commits without user confirmation
- Shows exactly what will be committed
- Allows message editing before commit

---

## Session State Integration

After committing, mark the session as concluded:
```bash
python3 .claude/skills/cc-conclude/analyze_changes.py --conclude
```

This:
- Sets `concluded_at` timestamp in `.claude/session/state.json`
- Archives the full session state to `.claude/session/history.jsonl`
- Enables the next `/cc-prime-cw` to start fresh

**View session history**:
```bash
cat .claude/session/history.jsonl | jq -s '.'
```

---

## Configuration

Edit `workflow.yaml` to customize:
- README trigger patterns
- Commit types
- Phase behavior

Check current config: `python .claude/skills/cc-conclude/analyze_changes.py --config`
