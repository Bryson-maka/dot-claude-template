---
name: cc-conclude
description: Generate session summary, update docs, and execute git workflow
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash, Edit, Write, Task, AskUserQuestion
argument-hint: [--commit | --no-readme | --no-handoff]
---

# Session Conclusion

Wrap up your Claude Code session with a summary, README check, and git commit.

## Current State

!`uv run --with pyyaml python3 .claude/skills/cc-conclude/analyze_changes.py`

The output above includes:
- **git_state**: Branch, remote tracking, staged/unstaged/untracked counts
- **changes**: List of modified files with status and line counts
- **triggers**: README update triggers detected
- **recommendations**: Prioritized git commands to run (stage, commit, push)
- **session**: Context from `/cc-prime-cw` and `/cc-execute` if run earlier (domains analyzed, compact priming summary, analyst summaries, teams, verification state)
- **handoff**: Session handoff state (`active_exists`, `active_title`, `active_date`, `archive_count`)

---

## Arguments

- `--commit`: Quick commit (skip README check and handoff, minimal prompts)
- `--no-readme`: Skip README check but full git workflow
- `--no-handoff`: Skip handoff generation
- (default): Full workflow with all checks

---

## No Prior Session

If `/cc-prime-cw` and `/cc-execute` were not run in this session, skip Phase 2 (Summarize session context) and proceed directly with Phase 1 (Gather git state) and Phase 4 (Git Commit). The git state analysis provides enough context for a meaningful commit workflow without prior session data.

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
- `session.teams`: Agent teams created during execution (primary)
- `session.adversary_verdicts`: Adversarial challenge results per team
- `session.verifications`: Test/lint/adversarial results
- `session.files_modified_by_session`: Files modified during execution
- `session.subagents_spawned`: Count of direct subagents (cc-prime-cw analysts)
- `session.prime_summary`: Compact priming synthesis from `/cc-prime-cw`
- `session.analyst_summaries`: Per-domain summaries persisted during priming

**To view detailed session state**:
```bash
python3 .claude/lib/session_state.py show --pretty
python3 .claude/lib/session_state.py summary
```

Generate session summary using this data:
- **Status**: COMPLETED, IN_PROGRESS, or BLOCKED
- **Priming Context**: Use `session.prime_summary` and `session.analyst_summaries` to recall the active architecture and plan context
- **Tasks**: From execution_journal task_completed entries
- **Teams**: From hook-captured teams list and composition; include legacy subagent counts if present
- **Adversarial Challenges**: If `session.adversary_verdicts` has entries, include verdict (ACCEPTED/CHALLENGED) and key findings for each
- **Verification**: Test results and adversarial challenge outcomes
- **Files Changed**: From git diff + files_modified list
- **Open Items**: Incomplete work or follow-ups

Do not reconstruct the session by rereading broad swaths of the repo. Prefer the saved session context, git diff, and handoff state. If a hook-populated field is sparse or missing, note that gap instead of replaying `/cc-prime-cw` or `/cc-execute`.

### Phase 3: README Check (unless --no-readme or --commit)

If the git state above shows README triggers detected:
1. Analyze what changed (new directories, config files, .claude content)
2. Draft README updates
3. Present draft for user approval
4. Apply if approved

### Phase 4: Handoff (unless --no-handoff or --commit)

Generate a session handoff document so the next Claude Code session can pick up where this one left off.

**Step 4a — Archive existing handoff:**

If `handoff.active_exists` is true in the analysis output:
1. Read `.claude/handoff/active.md` to get its title (first `#` heading) and date (`**Date**:` line)
2. Derive archive filename: `{date}_{slug}.md` where slug is the title kebab-cased, lowercased, non-alphanumeric stripped (e.g., "Slack Stabilization Investigation" → `slack-stabilization-investigation`)
3. Move `active.md` → `.claude/handoff/archive/{date}_{slug}.md`
4. Create `.claude/handoff/archive/` directory if it doesn't exist

**Step 4b — Generate new `active.md`:**

Write `.claude/handoff/active.md` using this template. Fill each section from git diff, session state, and your understanding of what happened this session. The title should reflect what was ACCOMPLISHED, not what was originally planned.

- If the session worked from a plan document (e.g., a design doc referenced in the previous handoff), include it as `**Plan doc**: {path}`. This ensures the next session's cc-prime-cw discovers and loads it.
- Team composition and adversarial challenge details belong in the archive, not the active handoff. Fold the adversary verdict into Accomplished as a single bullet.
- Keep Accomplished to 3-5 concrete outcome bullets. The handoff is for the NEXT session, not a retrospective.
- Reuse the persisted prime summary when it helps explain scope or active plan context; do not restate large architecture docs.
- Open Items should distinguish blocking issues from deferred/carried-forward items.

```markdown
# {Title — what was accomplished this session}

**Date**: {YYYY-MM-DD}
**Status**: {one-line status}
**Plan doc**: {path to plan if exists, otherwise omit this line}
**Prior session**: `.claude/handoff/archive/{previous archived filename}`

---

## Accomplished

- {3-5 bullets max — concrete outcomes only, not process}
- {Include adversary verdict as one bullet if applicable: "Adversary: ACCEPTED (N holes fixed)"}

## Open Items

### Blocking
- {Must fix before next work can proceed}

### Deferred
- {Carried forward — include origin date if older than 2 sessions}

## Next Session

### Priorities
1. {Most important — the specific task to execute}
2. {Second priority}
3. {Third if applicable}

### Verification
```bash
# Commands to verify current state
```

### Guardrails
- {What NOT to do — keep these sharp and current}
- {Remove stale guardrails that no longer apply}
```

**Step 4c — Review MEMORY.md:**

Check if any stable patterns were confirmed this session that should be added to `~/.claude/projects/*/memory/MEMORY.md`:
- Only add verified findings confirmed across this session's work
- Do not duplicate what's already in MEMORY.md
- Do not add speculative or single-observation conclusions
- If nothing qualifies, skip this step

### Phase 5: Git Commit

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

## Scope Boundaries

cc-conclude is a **session wrap-up tool**, not an execution tool:
- Do NOT edit source code, tests, or application files — that is cc-execute's job
- Do NOT spawn agent teams for implementation work or for reconstructing session context
- Do NOT start new features, fix bugs, or refactor code
- The ONLY files cc-conclude should write/edit are: `.claude/handoff/active.md` and `README.md` (if triggers detected)
- If unfinished work remains, document it in the handoff's Open Items — do not attempt to complete it
