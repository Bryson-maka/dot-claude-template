---
name: cc-prime-cw
description: Load codebase context via parallel analyst subagents
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Task
hooks:
  Stop:
    - hooks:
        - type: command
          command: "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/record-cc-prime-state.py stop"
          timeout: 15
  SubagentStop:
    - matcher: "Explore"
      hooks:
        - type: command
          command: "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/record-cc-prime-state.py subagent"
          timeout: 15
---

# Context Window Priming

Prime the session for later execution. Your job is to create durable, compact context, not to personally deep-read the repo.

## Codebase Manifest

!`uv run --with pyyaml python3 .claude/skills/cc-prime-cw/discover.py --pretty`

## Prior Session Constraints

!`python3 .claude/lib/session_state.py summary`

The discovery prelude above already marks the session as primed. Analyst summaries and the final prime summary are persisted by skill hooks. Do not use `Bash(...)` for session bookkeeping in this skill.

---

## Phase 1: Foundation

Read the foundation documents listed in the manifest above under the `"foundation"` key.
These are high-value documents discovered automatically based on what exists in the project.

If no foundation documents are listed, skip to Phase 2.

Do NOT start broad repo exploration yourself here. Outside the foundation docs, only read a file directly if it is required to disambiguate the handoff or to unblock an analyst prompt.

## Phase 2: Deploy Analysts

For **each domain** in the manifest above, spawn one `Task(subagent_type="Explore")` subagent.

**Prompt template for each domain:**
```
{domain.description}

**Your Files** (from manifest):
{for each file in domain.files:}
- {file.path} ({file.lines} lines) -> {
    if file.size_class == "CHUNK": "read chunks " + file.chunks
    else: "read complete"
  }

**Search for**: {domain.keywords joined by ", "}

Your context window is expendable. Read the listed files with judgment: prioritize high-signal files first and stop once the domain is clear. Do not ask the lead to reread your files.

Respond with (**STRICT LIMIT: <=700 tokens**):
- **Domain**: {domain_name}
- **Files Read**: [integer]
- **Tokens Used**: [integer or "unknown"]
- **Reusable Summary**: [<=300 chars; durable summary for later skills]

## {domain_name}
{for section in domain.report_sections:}
- **{section}**: [findings]
```

**Spawn all domain analysts in parallel** using a single message with multiple foreground Task tool calls — do NOT use `run_in_background`. They execute concurrently when issued in the same message and return results directly.

Once the analysts are launched, do NOT start parallel deep reading as the lead. Wait for them. While they run, you may only inspect up to 2 narrowly targeted files if a prompt needs clarification or the handoff has a blocking ambiguity.
Do not use `Bash` in this skill. Discovery and session recording are already handled by the slash-command prelude and hooks.

**Greenfield projects**: If the manifest shows `"greenfield": true` (fewer than 5 source files), **skip analyst spawning**. Instead:
- Report that the project is greenfield
- Suggest the user describe their intended architecture
- Note any detected frameworks/languages from auto-detection

**Monorepo projects**: If the manifest shows `"monorepo"` with packages, **note cross-package dependencies** in your synthesis. Analysts should be aware that changes in one package may affect others.

## Phase 3: Synthesize

After all Task calls return (they complete in the same turn):

1. Synthesize directly from the analyst responses. Do not emit extra bookkeeping commands.
2. Each analyst response must include the required `Domain / Files Read / Tokens Used / Reusable Summary` header so the hook can persist it.
3. Provide the user summary in this format:

```
## Context Primed

**Foundation**: [docs read]
**Discovery**: [count] domains, [count] files scanned
**Analysts**: [count] completed
**Prime Summary**: [<=800 chars; architecture, active plan, and next execution focus]

### Domain Summary
[1-2 short sentences per domain from analyst responses]
**Per analyst metrics**: [domain] — [files read], [tokens used]

Ready for work.
```

Keep the final synthesis under 1200 tokens. Do NOT emit giant file tables or restate long file lists.

---

## Token Budget

- **Subagent context is expendable**: They can spend the large context budget
- **Main agent context is precious**: Each subagent response <=700 tokens
- **Result**: The lead keeps a compact reusable summary instead of reconstructing the repo later

## Scope Boundaries

cc-prime-cw is a **read-only context loader**, not an execution tool:
- Do NOT edit or write any files — your job is to read and synthesize
- Do NOT drift into execution planning or implementation
- Do NOT duplicate the analysts' deep reading as the lead
- Do NOT start executing tasks, fixing bugs, or implementing features
- Do NOT suggest next steps or begin work — end at "Ready for work" and wait for the user
- If the user provides a task alongside `/cc-prime-cw`, load context first, then let the user invoke `/cc-execute` separately
