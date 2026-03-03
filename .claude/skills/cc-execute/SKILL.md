---
name: cc-execute
description: Execute tasks with agent team orchestration and adversarial review
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Task, Bash, Edit, Write, NotebookEdit, AskUserQuestion, TeamCreate, TeamDelete, SendMessage, TaskCreate, TaskList, TaskUpdate, TaskGet
argument-hint: [task description]
---

# Task Execution

**Task**: $ARGUMENTS

**Prerequisite**: Run `/cc-prime-cw` first to load project context (recommended but not required).

## Project Context

!`_err=$(mktemp) && uv run --with pyyaml python3 .claude/skills/cc-execute/discover.py --pretty 2>"$_err" || { python3 -c "import json,sys; print(json.dumps({'error':'Discovery failed','stderr':open(sys.argv[1]).read()}))" "$_err"; rm -f "$_err"; false; } && rm -f "$_err"`

## Git Context

!`python3 .claude/lib/git_context.py --pretty 2>/dev/null || echo '{"git_available": false}'`

## Session Summary

!`python3 .claude/lib/session_state.py summary 2>/dev/null || echo '{}'`

---

## Workflow

cc-execute uses **agent teams** for every task. You (the lead) reason about team composition based on the task, codebase state, and goals.

### 1. Analyze & Plan

Break the task into specific, verifiable todos (use TaskCreate).

Then **reason about your team**. Consider:
- What work needs to happen (research, implementation, testing, refactoring, web research)
- How the work decomposes into independent responsibilities
- Which responsibilities need write access vs read-only
- What model capability each responsibility demands

There is no fixed roster. You decide the number and type of agents based on the task.

**Agent types available:**

| Type | Tools | Use For |
|------|-------|---------|
| `Explore` | Read, Glob, Grep, Bash, WebFetch, WebSearch | Deep file reads, code search, web research, architecture analysis, adversarial challenge. **Cannot edit files.** |
| `general-purpose` | All tools including Edit, Write, Bash | Implementation, refactoring, test execution, any work requiring code changes |

**Model selection:** Use `sonnet` (default) for most work. Use `opus` for tasks requiring deep reasoning about complex architecture or subtle design decisions.

### 2. Create Team & Deploy

```
TeamCreate(team_name="cc-exec-{short-task-slug}")
```

Spawn agents with descriptive, task-specific names:

```
Task(
  subagent_type="general-purpose",
  team_name="cc-exec-{slug}",
  name="auth-refactorer",
  prompt="You are on the cc-exec team. Your responsibility: [specific assignment].
    [Include all necessary context — teammates do NOT see the lead's conversation history or primed context.]"
)
```

Create tasks via TaskCreate and assign via TaskUpdate(owner="agent-name").

**Log team creation** for session tracking:
```
Bash: python3 .claude/lib/session_state.py log --type team_created --team-name "cc-exec-{slug}" --members "agent1:type:model,agent2:type:model"
```

### 3. Supervise & Coordinate

- Monitor progress via TaskList
- Use SendMessage to share findings between agents, redirect work, or assign follow-ups
- Help unblock agents when they encounter obstacles
- Agents can message each other for peer coordination

### 4. Verify

Check CLAUDE.md for the project's testing philosophy.

- Run existing tests to check for regressions
- Do NOT write new tests unless the user explicitly asks
- Prefer live verification — run actual commands to confirm behavior

### 5. Adversarial Challenge

**Required for every task.** After implementation and verification, spawn a Devil's Advocate on the team:

```
Task(
  subagent_type="Explore",
  team_name="cc-exec-{slug}",
  name="adversary",
  prompt="""You are the Devil's Advocate for the cc-exec team. Your job: find holes
using first principles and verified codebase evidence.

**What changed**:
[list every modified file and what each change does]

**Instructions**:
1. Read every modified file completely
2. Run `git diff` to see exact line-level changes
3. Read adjacent code that interacts with the changes
4. Challenge from first principles:
   - Does the implementation actually solve the stated problem?
   - Are there code paths that break under real usage?
   - Does this integrate correctly with existing architecture?
   - Are there implicit assumptions that aren't validated?
   - Is there dead code or unreachable paths introduced?

Do NOT focus on test coverage gaps or style nits.
Do NOT read .env, credentials, or secret files.

**Report**:
- **Files reviewed**: [list with line counts]
- **Holes found**: [specific issues with file:line evidence]
- **Strengths**: [what's solid about the implementation]
- **Verdict**: CHALLENGED | ACCEPTED

Every hole must cite specific file:line evidence from the codebase.""")
```

**Log the adversary verdict** for session tracking:
```
Bash: python3 .claude/lib/session_state.py log --type adversary_verdict --team-name "cc-exec-{slug}" --verdict "ACCEPTED" --findings "summary"
```

If CHALLENGED: address the findings, then re-challenge (maximum 2 rounds total). If still challenged, present findings to user for decision.

### 6. Complete

- Shutdown all team agents: SendMessage(type="shutdown_request") to each
- Log team closure: `python3 .claude/lib/session_state.py log --type team_closed --team-name "cc-exec-{slug}"`
- Clean up: TeamDelete
- Mark all todos complete
- Summarize: what was accomplished, files modified, adversary verdict

---

## Agent Type Reference

| Type | Tools | Best For |
|------|-------|----------|
| `Explore` | Read, Glob, Grep, Bash, WebFetch, WebSearch | Investigation, analysis, web research, adversarial challenge — **read-only, cannot edit files** |
| `general-purpose` | All tools including Edit, Write, Bash | Implementation, testing, refactoring — **full access** |

The lead decides team composition per task. There is no fixed roster.

---

## Example

```
User: /cc-execute Refactor auth module to use JWT instead of session tokens

1. Analyze: Complex refactor touching auth, routes, and middleware
   Team: 3 agents
   - "auth-analyzer" (Explore) — map current session token usage across codebase
   - "jwt-implementer" (general-purpose) — build JWT generation, validation, middleware
   - "route-migrator" (general-purpose) — update all route handlers to JWT flow

2. Create team "cc-exec-jwt-refactor", spawn agents, assign tasks

3. Supervise: auth-analyzer reports 14 files using session tokens
   → Share findings with implementer and migrator via SendMessage
   → jwt-implementer builds token module
   → route-migrator updates handlers as implementer completes

4. Verify: run existing auth tests, test login/logout flow

5. Adversary reads all changed files + git diff:
   "Token refresh not handled in middleware (auth/middleware.py:89)"
   → Verdict: CHALLENGED
   → Fix token refresh → re-challenge → ACCEPTED

6. Shutdown team, summarize changes across 14 files
```
