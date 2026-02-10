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

**Spawn all domain analysts in parallel** using a single message with multiple Task tool calls.

## Phase 3: Synthesize

After subagents complete, provide a summary:

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

