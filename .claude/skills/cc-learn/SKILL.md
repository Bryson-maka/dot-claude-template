---
name: cc-learn
description: Analyze project and evolve .claude configuration based on discovered patterns
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Bash, Edit, Write, AskUserQuestion
argument-hint: [--apply | --preview | --diff]
---

# Configuration Learning

Analyze your project and intelligently evolve the `.claude` configuration based on what's actually in the codebase.

## Project Analysis

!`python3 .claude/skills/cc-learn/learn.py 2>/dev/null || echo 'Analysis failed - check .claude/lib/project_analyzer.py'`

---

## Arguments

- `--apply`: Apply suggested configuration to `.claude/project_config.yaml`
- `--preview`: Show full configuration that would be written
- `--diff`: Show difference between current and suggested configuration
- (default): Show analysis summary with suggestions

---

## Workflow

### Phase 1: Analyze

The analysis above shows:
- **Languages**: Programming languages found in the project
- **Frameworks**: Detected frameworks, build systems, and tools
- **Domains**: Suggested domain configurations based on directory structure
- **Commands**: Detected test/lint/build commands

### Phase 2: Review Suggestions

For each domain suggestion, evaluate:
1. Does this pattern capture meaningful project structure?
2. Are the keywords appropriate for the language(s)?
3. Will this help future context priming?

For command suggestions, verify:
1. Are the test commands correct for this project?
2. Are required tools installed (pytest, cargo, npm, etc.)?

### Phase 3: Apply or Customize

**Option A: Auto-apply** (if `--apply` argument passed or user confirms)
```bash
python3 .claude/skills/cc-learn/learn.py --apply
```
This writes to `.claude/project_config.yaml`, which is merged with base configs at runtime.

**Option B: Preview first**
```bash
python3 .claude/skills/cc-learn/learn.py --preview
```
Review the full configuration before applying.

**Option C: Manual customization**
1. Run `--preview` to see suggested config
2. Copy desired sections to `.claude/skills/cc-prime-cw/domains.yaml`
3. Or manually edit `.claude/project_config.yaml`

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

---

## When to Run

Run `/cc-learn` when:
- Starting work on a new project (initial configuration)
- Adding a new language or framework to the project
- Significant directory restructuring
- Test infrastructure changes

The analysis is fast and non-destructive. Changes only apply when explicitly confirmed.

---

## Example Session

```
User: /cc-learn

## Project Analysis Summary

**Files**: 68 (12,450 lines)
**Languages**: Python (45), TypeScript (23)
**Frameworks**: pytest (100%), fastapi (80%), react (60%)

**Suggested Domains**: 3
  - api: 5 patterns
  - frontend: 4 patterns
  - shared: 2 patterns

**Suggested Commands**:
  - test: pytest
  - lint: ruff check
  - build: npm run build

---
Use `--apply` to write configuration, or `--preview` to see full config.

User: Apply these changes

[Runs: python3 .claude/skills/cc-learn/learn.py --apply]

Configuration written to: .claude/project_config.yaml
Run /cc-prime-cw to load the new configuration.
```

---

## Configuration

Edit `config.yaml` to customize:
- Analysis ignore patterns
- Domain generation thresholds
- Framework detection sensitivity
- Output settings

---

## Manual Domain Example

If you want to add a custom domain manually:

```yaml
# In project_config.yaml
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

To re-analyze fresh:
```bash
python3 .claude/skills/cc-learn/learn.py --preview
```
