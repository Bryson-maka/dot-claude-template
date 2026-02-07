---
paths:
  - ".claude/skills/**/SKILL.md"
  - ".claude/skills/**/*.yaml"
---

# Skill Authoring Rules

When writing or modifying skills:

- SKILL.md files use YAML frontmatter (between `---` markers) for metadata
- Required frontmatter: `name`, `description`
- Use `allowed-tools` to whitelist tools the skill needs (principle of least privilege)
- Use `disable-model-invocation: true` for skills that should only be user-invoked
- Use `argument-hint` to show autocomplete hints for slash commands
- Use `!` backtick syntax for dynamic context injection (shell preprocessing)
- Use `$ARGUMENTS` to reference user input passed to the skill
- Keep SKILL.md under 500 lines - Claude's context is precious
- Skills can define scoped `hooks:` in frontmatter that only run while the skill is active
- Use `context: fork` + `agent: Explore` for skills that should run in isolated subagents
- Configuration YAML files should be separate from SKILL.md for maintainability
- All discover.py / learn.py scripts should handle missing dependencies gracefully
