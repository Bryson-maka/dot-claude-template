---
name: cc-prime-cw
description: Load codebase context at session start using analyst subagents
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

!`uv run --with pyyaml python3 .claude/skills/cc-prime-cw/discover.py --pretty 2>/dev/null || echo '{"error": "Discovery failed - run manually: uv run --with pyyaml python3 .claude/skills/cc-prime-cw/discover.py --pretty"}'`

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

---

## Session State

Session state is automatically updated when priming completes. The discovery script writes to both:
- `.claude/session/manifest.json` - Detailed file-level manifest
- `.claude/session/state.json` - Session tracking state

**State fields set by cc-prime-cw**:
- `primed_at`: ISO timestamp when priming completed
- `domains`: List of analyzed domain names
- `foundation_docs`: Foundation documents that were read
- `execution_journal`: First entry added for priming completion

**Downstream skills read**:
- `/cc-execute` checks `primed_at` to know if context is loaded
- `/cc-conclude` reads domains and foundation_docs for summary generation

**Manual state management** (if needed):
```bash
# Check current state
python3 .claude/lib/session_state.py show --pretty

# Reset state for fresh session
python3 .claude/lib/session_state.py reset
```

---

## Configuration

Edit `domains.yaml` to customize which files are analyzed:
- Add/remove domain patterns
- Adjust keywords for content matching
- Modify report sections
- Configure foundation document patterns under `analyst_config.foundation_patterns`

Run discovery manually to test: `uv run --with pyyaml python3 .claude/skills/cc-prime-cw/discover.py --pretty`
