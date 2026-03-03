# Agent team orchestration, git intelligence, and smarter discovery

**Date**: 2026-03-03
**Status**: Complete — P1/P2/P3 implemented + cruft sweep, both adversary accepted
**Prior session**: Handoff pipeline integration (2026-03-02)

---

## Accomplished

### Session 2026-03-02: Handoff Pipeline
- Added `handoff/` directory with `.gitkeep` scaffolding (active.md + archive/)
- Integrated handoff pipeline into cc-conclude as Phase 4
- Added HandoffState to analyze_changes.py, handoff config to workflow.yaml
- Added active.md to cc-prime-cw/domains.yaml foundation docs
- Updated CLAUDE.md and README.md with handoff references

### Session 2026-03-03: Agent Teams + Discovery
- Converted cc-execute from ephemeral subagents to persistent agent teams (TeamCreate + SendMessage + TaskList)
- Made adversarial challenge REQUIRED for every cc-execute task (not optional)
- Added dynamic team composition — lead agent reasons about agent count/types based on task
- Created git_context.py: file volatility, change coupling, recent commits for informed decision-making
- Added session_state.py schema v1.1 with teams[] tracking, adversary verdicts, and v1.0 migration
- Absorbed cc-learn auto-detection into cc-prime-cw discover.py (runs when project_config.yaml missing)
- Added handoff parsing — cc-prime-cw reads open items and guardrails from active.md
- Added greenfield detection (< 5 source files skips analyst spawning)
- Added monorepo detection (multiple package managers at different paths)
- Added embedded domain to domains.yaml (GPIO, UART, SPI, I2C, ISR, FreeRTOS keywords)
- Updated cc-conclude to surface team composition and adversary verdicts in handoffs
- Fixed run_in_background prohibition in parallel subagent spawning
- Removed cc-learn skill directory (3 files, -461 lines) — functionality fully absorbed into cc-prime-cw
- Cleaned all cc-learn references from settings.json, CLAUDE.md, skills/README.md, domains.yaml, discover.py

## Discovered

- Claude non-deterministically interprets "spawn in parallel" as run_in_background=True — explicit prohibition in SKILL.md instructions prevents this
- Agent teams (CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1) enable persistent agents with peer messaging, task lists, and idle/resume — ideal for cc-execute's dependency chains
- Subagents (Task tool) are better for independent parallel reads like cc-prime-cw domain analysis
- The adversarial challenge caught two real bugs: missing settings.json permission for git_context.py and nonexistent --json CLI flag in session_state.py summary
- The handoff pipeline integrates cleanly into cc-conclude — just another skippable phase

## Adversarial Challenge

**Team**: cc-exec-p1p2p3
**Verdict**: ACCEPTED (round 2)
**Round 1 Findings**: (1) git_context.py not in settings.json permissions — inline block silently degrades, (2) `summary --json` flag doesn't exist — inline block always returns `{}`
**Resolution**: Added git_context.py permission to settings.json, removed `--json` flag from cc-prime-cw SKILL.md inline block

**Team**: cc-exec-cruft-sweep
**Verdict**: ACCEPTED
**Findings**: One WARN — stale handoff priority still listed cc-learn removal as future work after it was already done

## Key Files Modified

| File | Changes |
|------|---------|
| `.claude/lib/session_state.py` | Schema v1.1: teams[], log_team_created/closed/adversary_verdict, migration |
| `.claude/lib/git_context.py` | NEW: file volatility, change coupling, recent commits, recently modified |
| `.claude/settings.json` | Added git_context.py bash permission |
| `.claude/skills/cc-execute/SKILL.md` | Team-based workflow, dynamic composition, required adversarial, inline blocks |
| `.claude/skills/cc-execute/discover.py` | Output agent_types and adversarial config |
| `.claude/skills/cc-execute/workflow.yaml` | Removed fixed roster, added agent_types reference, adversarial required |
| `.claude/skills/cc-conclude/SKILL.md` | Team Composition + Adversarial Challenge sections in handoff template |
| `.claude/skills/cc-conclude/analyze_changes.py` | Extract teams and adversary_verdicts from session state |
| `.claude/skills/cc-prime-cw/discover.py` | Auto-detect, handoff parsing, greenfield, monorepo detection |
| `.claude/skills/cc-prime-cw/domains.yaml` | Added embedded domain with hardware keywords |
| `.claude/skills/cc-prime-cw/SKILL.md` | Session summary inline block, greenfield/monorepo handling |
| `.claude/skills/cc-conclude/workflow.yaml` | Added handoff phase and config section |
| `.claude/skills/cc-prime-cw/domains.yaml` | Added active.md to foundation docs |
