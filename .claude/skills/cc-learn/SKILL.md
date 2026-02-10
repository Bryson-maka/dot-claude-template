---
name: cc-learn
description: Analyze project and auto-detect languages, frameworks, and configuration
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Bash, AskUserQuestion
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

