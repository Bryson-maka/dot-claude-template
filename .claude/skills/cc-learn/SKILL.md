---
name: cc-learn
description: Analyze project and evolve .claude configuration based on discovered patterns
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Bash, Edit, Write, AskUserQuestion
argument-hint: [--apply | --preview]
---

# Configuration Learning

Analyze your project and intelligently evolve the `.claude` configuration based on what's actually in the codebase.

## Project Analysis

!`python3 .claude/skills/project_analyzer.py --pretty 2>/dev/null | head -80 || echo '{"error": "Analysis failed"}'`

---

## Arguments

- `--apply`: Automatically apply suggested configuration changes
- `--preview`: Show what would change without applying (default)
- `--domains-only`: Only update domain patterns
- `--commands-only`: Only update test/build commands

---

## Workflow

### Phase 1: Analyze

The analysis above shows:
- **Languages**: Programming languages found in the project
- **Frameworks**: Detected frameworks, build systems, and tools
- **Directories**: Purpose-classified directory patterns
- **Suggestions**: Recommended domain and command configurations

### Phase 2: Review Suggestions

For each domain suggestion, evaluate:
1. Does this pattern capture meaningful project structure?
2. Are the keywords appropriate for the language(s)?
3. Will this help future context priming?

For command suggestions, verify:
1. Are the test commands correct for this project?
2. Are required tools installed (pytest, cargo, npm, etc.)?

### Phase 3: Apply or Customize

**Option A: Auto-apply** (if `--apply` argument)
```bash
python3 .claude/skills/project_analyzer.py --apply
```
This writes to `.claude/project_config.yaml`, which is merged with base configs at runtime.

**Option B: Manual customization**
1. Review the YAML output from `--suggest-domains`
2. Add selected domains to `.claude/skills/cc-prime-cw/domains.yaml`
3. Add commands to `.claude/skills/cc-execute/workflow.yaml`

**Option C: Ask user** (default)
Present the analysis summary and ask:
- Which domains should be added?
- Which should be skipped?
- Any custom modifications?

### Phase 4: Validate

After applying changes, run `/cc-prime-cw` to verify the new configuration works:
- Are new patterns discovering files correctly?
- Are keywords matching relevant code?

---

## Configuration Layers

The system uses a **merge-based** configuration approach:

```
.claude/project_config.yaml    <- Project-specific (merged first)
        +
domains.yaml / workflow.yaml   <- Template defaults (merged second)
        =
     Final config              <- Combined result
```

**Merge behavior for domains with same name**:
- **Lists** (patterns, keywords, report_sections): Combined, project values first
- **Strings** (description): Project version used if provided

**New domains** in project_config.yaml are added alongside base domains.

This means project-specific patterns get priority while preserving base template intelligence.

---

## When to Run

Run `/cc-learn` when:
- Starting work on a new project (initial configuration)
- Adding a new language or framework to the project
- Significant directory restructuring
- Test infrastructure changes

The analysis is fast and non-destructive. Changes only apply when you explicitly approve them.

---

## Example Session

```
User: /cc-learn

Analysis shows:
- Languages: Python (45 files), TypeScript (23 files)
- Frameworks: pytest, fastapi, react
- New directories: api/, frontend/, shared/

Suggested domains:
1. api (source) - FastAPI backend code
2. frontend (source) - React TypeScript frontend
3. shared (source) - Shared utilities

Suggested commands:
- test: pytest, npm test
- lint: ruff check, npm run lint
- build: npm run build

Apply these changes? [Yes/No/Customize]

User: Yes

Configuration applied to .claude/project_config.yaml
Run /cc-prime-cw to load the updated configuration.
```

---

## Manual Domain Example

If you want to add a custom domain manually:

```yaml
# In domains.yaml or project_config.yaml
domains:
  - name: my_custom_domain
    description: |
      Description of what this domain covers.
    patterns:
      - "my_module/**/*.py"
      - "other_path/**/*.ts"
    keywords:
      - "class\\s+\\w+"
      - "def\\s+\\w+"
    report_sections:
      - components
      - patterns
      - dependencies
```

---

## Cleanup

To reset to template defaults:
```bash
rm .claude/project_config.yaml
```

To see what would be discovered fresh:
```bash
python3 .claude/skills/project_analyzer.py --pretty
```
