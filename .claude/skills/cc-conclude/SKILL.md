---
name: cc-conclude
description: Wrap up session with summary, README updates, and git commit workflow
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash, Edit, Write, Task
argument-hint: [--commit | --no-readme]
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

**First, read the execution journal from cc-execute**:
```bash
curl -s http://localhost:8000/api/session/journal | jq '.journal'
curl -s http://localhost:8000/api/session/subagents | jq '.subagents'
curl -s http://localhost:8000/api/session/state | jq '.state.verification_results'
```

The execution journal contains:
- Tasks that were created, started, and completed
- Subagents that were spawned and their results
- Verification results (tests, lint, adversarial challenges)

Generate session summary using journal data:
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
curl -X POST http://localhost:8000/api/session/conclude
```

This:
- Sets `concluded_at` timestamp
- Archives the full session state to `~/.claude/session/history.jsonl`
- Enables the next `/cc-prime-cw` to start fresh

---

## Configuration

Edit `workflow.yaml` to customize:
- README trigger patterns
- Commit types
- Phase behavior

Check current config: `python .claude/skills/cc-conclude/analyze_changes.py --config`
