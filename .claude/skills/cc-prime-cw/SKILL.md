---
name: cc-prime-cw
description: Load codebase context via parallel analyst subagents
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Task, Bash
hooks:
  SubagentStop:
    - matcher: "Explore"
      hooks:
        - type: command
          command: "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/validate-subagent-output.sh"
          timeout: 15
---

# Context Window Priming

Prime your context window by deploying analyst subagents to explore the codebase. Knowledge loads into your working memory for this session.

## Codebase Manifest

!`_err=$(mktemp) && uv run --with pyyaml python3 .claude/skills/cc-prime-cw/discover.py --pretty 2>"$_err" || { python3 -c "import json,sys; print(json.dumps({'error':'Discovery failed','stderr':open(sys.argv[1]).read()}))" "$_err"; rm -f "$_err"; false; } && rm -f "$_err"`

## Prior Session Constraints

!`python3 .claude/lib/session_state.py summary 2>/dev/null || echo '{}'`

---

## Phase 1: Foundation

Read the foundation documents listed in the manifest above under the `"foundation"` key.
These are high-value documents discovered automatically based on what exists in the project.

If no foundation documents are listed, skip to Phase 2.

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

Your context window is expendable. Read thoroughly, then synthesize.

Respond with (**STRICT LIMIT: <=1000 tokens**):
## {domain_name}
{for section in domain.report_sections:}
- **{section}**: [findings]
```

**Spawn all domain analysts in parallel** using a single message with multiple foreground Task tool calls — do NOT use `run_in_background`. They execute concurrently when issued in the same message and return results directly.

**Greenfield projects**: If the manifest shows `"greenfield": true` (fewer than 5 source files), **skip analyst spawning**. Instead:
- Report that the project is greenfield
- Suggest the user describe their intended architecture
- Note any detected frameworks/languages from auto-detection

**Monorepo projects**: If the manifest shows `"monorepo"` with packages, **note cross-package dependencies** in your synthesis. Analysts should be aware that changes in one package may affect others.

## Phase 3: Synthesize

After all Task calls return (they complete in the same turn), provide a summary:

```
## Context Primed

**Foundation**: [docs read]
**Discovery**: [count] domains, [count] files scanned
**Analysts**: [count] completed

### Domain Summary
[2-3 sentences per domain from analyst responses]
**Include Files Read by each domain analysts with total tokens used**

Ready for work.
```

---

## Token Budget

- **Subagent context is expendable**: They read 50-100K tokens internally
- **Main agent context is precious**: Each subagent response <=1000 tokens
- **Result**: You understand 100K+ lines while consuming ~10K tokens total from your subagent team

