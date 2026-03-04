# Fix cc-execute premature handoff update

**Date**: 2026-03-04
**Status**: Complete — cc-execute now explicitly defers handoff/memory updates to cc-conclude
**Prior session**: `.claude/handoff/archive/2026-03-04_prime-refinement-and-smart-update-installation.md`

---

## Accomplished

- **Fixed premature handoff update during cc-execute** — The "Complete" section's "Summarize" instruction was ambiguous, causing the main agent to write `handoff/active.md` during execution instead of waiting for `/cc-conclude`. Added explicit boundary: summary is in-conversation only, handoff and memory updates are owned by `/cc-conclude`.

## Discovered

- The root cause was not model disobedience but **instruction ambiguity** — "Summarize: what was accomplished, files modified, adversary verdict" gave no indication that the summary should stay in-conversation. The agent's natural completion behavior filled the gap by writing the handoff document.
- When the user explicitly told the agent not to update handoff during cc-execute, the problem disappeared — confirming the fix is instructional, not architectural.

## Open Items

- No `--update` mode for CLAUDE.md (project root file outside .claude/ — manual sync if it changes)
- `settings.json` and `security-policy.yaml` are flagged but not auto-updated when projects customize them — may need a merge strategy later
- `--update` doesn't handle file permission changes (e.g., if a hook script gains +x)

## Priorities for Next Session

1. Run `/cc-prime-cw` on ceo-test-modules to verify the refined manifest output with a real codebase (non-greenfield)
2. Live-validate M5 file transfer (carried from ceo-test-modules handoff)
3. Consider adding TEMPLATE_VERSION bump automation to install.sh

## Guardrails

- Do not modify .claude/hooks/ unless extending the security model
- Do not remove .gitkeep files from handoff or session directories
- Run /cc-conclude at end of session to generate a proper handoff
- Do not auto-overwrite settings.json or security-policy.yaml in --update mode

## Key Files Modified

| File | Changes |
|------|---------|
| `.claude/skills/cc-execute/SKILL.md` | Added explicit prohibition on handoff/memory updates in Complete section |
