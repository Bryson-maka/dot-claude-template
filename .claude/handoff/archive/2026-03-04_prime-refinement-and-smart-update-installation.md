# Prime Refinement and Smart Update Installation

**Date**: 2026-03-04
**Status**: Complete — P1-P5 implemented, adversary accepted, update mode added, tested on ceo-test-modules
**Prior session**: `.claude/handoff/archive/new-project.md`

---

## Accomplished

- **P1**: Added `modification_targets` to all 6 domain report_sections in domains.yaml — subagent analysts now report a lookup table of key files for agent assignment
- **P2**: Integrated compact git summary into cc-prime-cw manifest (top 5 volatile files, top 3 coupled pairs) — main agent has volatility awareness during priming without duplicating cc-execute's full git context
- **P3**: Empty domains pruned from manifest output — only domains with discovered files appear, reducing noise in the main agent's mental model
- **P4**: Added `topology` summary block to manifest (total files, total lines, per-domain stats) — compact orchestration reference that survives context compression
- **P5**: Stripped `analyst_config` from stdout output (still saved in session/manifest.json) — removes consumed metadata from main agent's context
- **install.sh --update**: Smart incremental update mode that only copies changed template-owned files, never touches handoff/session/project_config, with --dry preview support
- **README updated**: Added Option 3 documenting the update workflow
- **Tested on ceo-test-modules**: `--update` correctly applied 2 changed files, skipped 28 identical, preserved M5 handoff

## Discovered

- cc-execute already provides full git context via inline `git_context.py --pretty` — cc-prime-cw only needs a compact summary, not the full dump
- For this greenfield project (dot-claude-template itself), empty domain pruning reduces 6 domains to 1 (docs) — significant noise reduction
- The install script's `--force` mode nukes `active.md` by design — `--update` was the missing piece for seed propagation

## Team Composition

| Agent | Type | Model | Responsibility |
|-------|------|-------|---------------|
| prime-refiner | general-purpose | sonnet | Implement P1-P5 changes across discover.py and domains.yaml |
| adversary | Explore | sonnet | First-principles review of all changes |

## Adversarial Challenge

**Team**: cc-exec-prime-refinement
**Verdict**: ACCEPTED
**Findings**: 7 files reviewed, 8 challenges all passed. Greenfield timing correct (pre-prune), git import safely guarded with HAS_GIT_CONTEXT flag, topology uses post-prune data, analyst_config saved before stripping, no downstream breakage in cc-execute or cc-conclude consumers.

## Open Items

- No `--update` mode for CLAUDE.md (project root file outside .claude/ — manual sync if it changes)
- `settings.json` and `security-policy.yaml` are flagged but not auto-updated when projects customize them — may need a merge strategy later
- `--update` doesn't handle file permission changes (e.g., if a hook script gains +x)

## Priorities for Next Session

1. Run `/cc-prime-cw` on ceo-test-modules to verify the refined manifest output with a real codebase (non-greenfield)
2. Live-validate M5 file transfer (carried from ceo-test-modules handoff)
3. Consider adding TEMPLATE_VERSION bump automation to install.sh

## Testing Protocol

- `install.sh /path --update --dry` — preview changes without writing
- `install.sh /path --update` — apply and verify output summary
- `uv run --with pyyaml python3 .claude/skills/cc-prime-cw/discover.py --pretty` — verify manifest structure
- Compare before/after on a seeded project to confirm handoff preservation

## Guardrails

- Do not modify .claude/hooks/ unless extending the security model
- Do not remove .gitkeep files from handoff or session directories
- Run /cc-conclude at end of session to generate a proper handoff
- Do not auto-overwrite settings.json or security-policy.yaml in --update mode

## Key Files Modified

| File | Changes |
|------|---------|
| `.claude/skills/cc-prime-cw/discover.py` | Git summary, domain pruning, topology block, analyst_config stripping |
| `.claude/skills/cc-prime-cw/domains.yaml` | `modification_targets` in all 6 domain report_sections |
| `.claude/install.sh` | `--update` and `--dry` modes for smart incremental propagation |
| `README.md` | Option 3: update workflow documentation |
