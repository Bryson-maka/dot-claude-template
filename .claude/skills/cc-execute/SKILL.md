---
name: cc-execute
description: Execute tasks with agent team orchestration and adversarial review
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Task, Bash, Edit, Write, NotebookEdit, AskUserQuestion, TeamCreate, TeamDelete, SendMessage, TaskCreate, TaskList, TaskUpdate, TaskGet
argument-hint: [task description]
hooks:
  PostToolUse:
    - matcher: "TeamCreate"
      hooks:
        - type: command
          command: "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/record-cc-execute-state.py team-create"
          timeout: 15
    - matcher: "Task"
      hooks:
        - type: command
          command: "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/record-cc-execute-state.py task-complete"
          timeout: 15
    - matcher: "TeamDelete"
      hooks:
        - type: command
          command: "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/record-cc-execute-state.py team-delete"
          timeout: 15
---

# Task Execution

**Task**: $ARGUMENTS

**Prerequisite**: Run `/cc-prime-cw` first to load project context (recommended but not required).
If priming data exists, treat it as the default starting point instead of re-researching the repo.

## Project Context

!`uv run --with pyyaml python3 .claude/skills/cc-execute/discover.py --pretty`

## Git Context

!`python3 .claude/lib/git_context.py --pretty`

## Session Summary

!`python3 .claude/lib/session_state.py summary`

---

## Workflow

cc-execute uses **agent teams** for every task. You are the lead: scope the work, brief the team, supervise progress, review diffs, and run final verification. Launch the team early. Do not become a second parallel implementer or researcher unless an agent is clearly blocked and you are explicitly taking over.

### 0. Check for Existing Plan

Before planning from scratch, check if there's an active plan:

1. Read `.claude/handoff/active.md` — check for a `**Plan doc**:` reference
2. If a plan doc exists, read it FIRST. You are continuing execution, not re-planning.
3. Pick up from where the last session left off (check Open Items and Priorities)
4. Do NOT create new design/planning docs when a plan doc exists
5. Do NOT modify the plan doc during execution — it's the reference. If something in the plan is wrong, note it in your summary and fix the code.

Also inspect the `session` object in Project Context before doing any new research:
- `session.prime_summary` is the compact reusable overview from `/cc-prime-cw`
- `session.analyst_summaries` are per-domain findings you should reuse when briefing agents
- `session.topology` and `session.handoff_constraints` are enough for initial scoping in most cases
- If the user supplied a diff/range or asked for a team review, start from that artifact plus the saved session context. Do not read extra code just to recreate the same brief yourself.

### 1. Analyze & Plan

Break the task into specific, verifiable todos (use TaskCreate).

Start from the saved priming context. Do NOT launch codebase-wide research if the task is already covered by the active handoff, plan doc, or analyst summaries. Only gather new information when there is a bounded unanswered question.

Then **reason about your team**. Consider:
- What work needs to happen (research, implementation, testing, refactoring, web research)
- How the work decomposes into independent responsibilities
- Which responsibilities need write access vs read-only
- What model capability each responsibility demands

There is no fixed roster. You decide the number and type of agents based on the task.

Use the smallest team that preserves real parallelism:
- Default for plan-driven implementation work: 1 `general-purpose` implementer
- Add 1 `Explore` researcher only for a narrowly bounded unknown
- Add more agents only when workstreams are independent and do not touch the same files
- Never create a "large team" by default
- For code changes, a `general-purpose` agent must own the edits; the lead should not edit the same files in parallel

**Agent types available:**

| Type | Tools | Use For |
|------|-------|---------|
| `Explore` | Read, Glob, Grep, Bash, WebFetch, WebSearch | Deep file reads, code search, web research, architecture analysis, adversarial challenge. **Cannot edit files.** |
| `general-purpose` | All tools including Edit, Write, Bash | Implementation, refactoring, test execution, any work requiring code changes |

**Model selection:** Use `sonnet` (default) for most work. Use `opus` for tasks requiring deep reasoning about complex architecture or subtle design decisions.

Lead behavior rules:
- Read the handoff, plan doc, and only the files directly implicated by the current step
- Use saved priming summaries to brief agents instead of restudying the repo
- When the task is review-heavy, prefer launching reviewers before reading implementation files yourself
- Once agents are in flight, do not do parallel deep file exploration "while waiting"
- Prefer `TaskList`, `TaskGet`, and `SendMessage` to unblock or redirect agents
- Read full files yourself when reviewing diffs, integrating conflicting findings, or running final verification
- Do not settle design holes solo and then send agents to confirm you; have them investigate first

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
    [Include all necessary context — teammates do NOT see the lead's conversation history or primed context. Reuse the saved prime summary / analyst summaries instead of pasting broad new research.]"
)
```

Create tasks via TaskCreate and assign via TaskUpdate(owner="agent-name").

Team lifecycle is recorded automatically by skill hooks. Do not issue `session_state.py` bookkeeping commands for team creation, adversary verdicts, or team shutdown.

### 3. Supervise & Coordinate

- Monitor progress via TaskList
- Use SendMessage to share findings between agents, redirect work, or assign follow-ups
- Help unblock agents when they encounter obstacles
- Agents can message each other for peer coordination
- If a researcher is running, wait for the result before doing the same investigation yourself
- If a single implementer owns a file set, keep ownership stable instead of opening overlapping edit tracks
- Idle time is not a cue to start your own duplicate review pass

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

Keep the adversary agent named `adversary` and preserve the `**Verdict**:` line in its report. Skill hooks record the verdict automatically.

If CHALLENGED: address the findings, then re-challenge (maximum 2 rounds total). If still challenged, present findings to user for decision.

### 6. Complete

- Shutdown all team agents: SendMessage(type="shutdown_request") to each
- Clean up: TeamDelete
- Mark all todos complete
- Summarize to the user: what was accomplished, files modified, adversary verdict

**Do NOT update `.claude/handoff/active.md`.** Handoff generation and archiving are owned by `/cc-conclude`. Your summary is an in-conversation report only.

---

## Agent Type Reference

| Type | Tools | Best For |
|------|-------|----------|
| `Explore` | Read, Glob, Grep, Bash, WebFetch, WebSearch | Investigation, analysis, web research, adversarial challenge — **read-only, cannot edit files** |
| `general-purpose` | All tools including Edit, Write, Bash | Implementation, testing, refactoring — **full access** |

The lead decides team composition per task. Smaller, purpose-built teams are preferred.

---

## Example

```
User: /cc-execute Refactor auth module to use JWT instead of session tokens

1. Analyze: Complex refactor touching auth, routes, and middleware
   Team: 2 agents
   - "auth-analyzer" (Explore) — answer one bounded question about current token flow
   - "jwt-implementer" (general-purpose) — own the code changes end-to-end

2. Create team "cc-exec-jwt-refactor", spawn agents, assign tasks

3. Supervise: auth-analyzer reports 14 files using session tokens
   → Share findings with implementer via SendMessage
   → jwt-implementer builds token module and updates the dependent handlers

4. Verify: run existing auth tests, test login/logout flow

5. Adversary reads all changed files + git diff:
   "Token refresh not handled in middleware (auth/middleware.py:89)"
   → Verdict: CHALLENGED
   → Fix token refresh → re-challenge → ACCEPTED

6. Shutdown team, summarize changes across 14 files
```
