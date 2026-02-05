---
name: cc-execute
description: Structured task execution with subagent deployment and todo tracking
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Task, Bash, Edit, Write, NotebookEdit, AskUserQuestion
argument-hint: [task description]
---

# Task Execution

**Task**: $ARGUMENTS

**Prerequisite**: Run `/cc-prime-cw` first to load project context (recommended but not required).

## Project Context

!`uv run --with pyyaml python3 .claude/skills/cc-execute/discover.py --pretty 2>/dev/null || echo '{"error": "Discovery failed - check manually"}'`

---

## Workflow

### 1. Create Todos

Based on the task, create specific, verifiable todos:
- Good: "Fix undefined variable at src/main.py:432"
- Bad: "Fix bugs" (too vague)

### 2. Investigate

Before implementing, spawn **Explore** subagents to verify assumptions:

```
Task(subagent_type="Explore", description="Find X", prompt="""
Read [file] completely. Your context is expendable.

Find: [specific thing]

Report (max 500 tokens):
- Location: [file:line]
- Finding: [what you found]
- Recommendation: [what to do]
""")
```

**Spawn multiple investigators in parallel** for thorough, multi-perspective analysis.

### 3. Execute

- **Small changes** (<10 lines): Spawn `general-purpose` subagent to implement
- **Complex changes**: Spawn multiple `general-purpose` subagent to implement and take various perspectives to proactively catch hidden assumptions

### 4. Verify

Spawn subagent to confirm changes work. Use the test command from `commands.test` in the Project Context above:
```
Task(subagent_type="general-purpose", description="Verify fix", prompt="Run [test command from context], confirm the change works...")
```

### 5. Adversarial Challenge

Before claiming "implementation complete", spawn a Devil's Advocate:

```
Task(subagent_type="Explore", description="Challenge: [claim]", prompt="""
The main agent claims: "[your claim]"

Your job is to DISPROVE this. Find evidence that:
- The fix is incomplete or incorrect
- Edge cases not handled
- Tests passing for wrong reasons

Report:
- **Holes found**: [issues]
- **Verdict**: CHALLENGED | ACCEPTED
""")
```

Maximum 2 adversarial rounds. If still challenged, ask user.

### 6. Complete

- Mark todos complete
- Summarize what was accomplished
- List files modified

---

## Session State Integration

cc-execute writes to the execution journal so cc-conclude knows what was done.

**After each significant action, log to the journal**:
```bash
# Log task completion
curl -X POST http://localhost:8000/api/session/journal \
  -H "Content-Type: application/json" \
  -d '{"type": "task_completed", "subject": "Fixed config parsing bug", "task_id": "1"}'

# Log subagent spawn
curl -X POST http://localhost:8000/api/session/subagents \
  -H "Content-Type: application/json" \
  -d '{"role": "investigator", "type": "Explore", "model": "sonnet", "description": "Find config issue"}'

# Log verification result
curl -X POST http://localhost:8000/api/session/verification \
  -H "Content-Type: application/json" \
  -d '{"type": "test", "passed": true, "details": "18 tests passed"}'

# Log adversarial challenge
curl -X POST http://localhost:8000/api/session/verification \
  -H "Content-Type: application/json" \
  -d '{"type": "adversarial", "passed": true, "details": "ACCEPTED after round 2"}'
```

**Journal entry types**: task_created, task_started, task_completed, subagent_spawned, subagent_completed, verification, adversarial

This enables cc-conclude to generate accurate commit messages and session summaries.

---

## Subagent Roles

| Role | Type | Model | When to Use |
|------|------|-------|-------------|
| **Investigator** | Explore | Sonnet | Read files, verify assumptions |
| **Implementer** | general-purpose | Sonnet | Make code changes |
| **Verifier** | general-purpose | Sonnet | Run tests, confirm changes |
| **Adversary** | Explore | Sonnet | Challenge claims, find holes |
| **Reasoner** | Explore | Opus | Complex analysis, design decisions |

---

## Token Philosophy

**Your context is precious. Subagent context is expendable.**

| Approach | Tokens Used | Understanding |
|----------|-------------|---------------|
| Read 10 files directly | ~100K | Raw code, limited reasoning room |
| 10 subagents report | ~5K | Synthesized findings, full reasoning room |

Subagents read MORE (entire files), report LESS (500-1000 tokens each).

---

## Anti-Patterns

| Don't | Do Instead |
|-------|------------|
| Read large files directly | Spawn Explore subagent |
| Assume file structure | Investigate first |
| Implement without verifying | Always verify |
| Use Haiku for reasoning | Use Sonnet or Opus |
| Skip adversarial on big claims | Challenge before claiming complete |

---

## Quick Example

```
User: /cc-execute Fix the config parsing bug

1. Create todos: [find bug, fix it, verify, Challenge]
2. Spawn investigators (parallel):
   - "Read config.py, find parsing issue"
   - "Read tests/test_config.py, what's tested"
3. Investigators report: Line 142 expects dict, gets string
4. Small fix - edit directly: Add type check at line 145
5. Spawn verifier: "Run pytest tests/test_config.py"
6. Verifier: Tests pass
7. Adversarial Challenge: run up to 2 chanllenges and reflect on output of each and reason about how to intelligently address
8. Mark todos complete, summarize full scope of execution
```
