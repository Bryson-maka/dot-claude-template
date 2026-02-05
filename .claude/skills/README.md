# Claude Code Development Skills

**Purpose**: Skills for Claude Code (the CLI) when working with any project.

These skills help Claude Code understand codebases, follow efficient patterns, and maintain consistency when making changes.

## Skill Directories

| Skill | Command | Purpose |
|-------|---------|---------|
| `cc-prime-cw/` | `/cc-prime-cw` | Dynamic codebase discovery and session initialization |
| `cc-execute/` | `/cc-execute` | Subagent workflow patterns for complex tasks |
| `cc-conclude/` | `/cc-conclude` | Session wrap-up, README updates, and git commit workflow |

**Note**: In Claude Code, skill directory names become slash commands automatically. The `SKILL.md` file in each directory defines the command behavior.

## How to Use

### Context Priming (`/cc-prime-cw`)

Run at the start of a session to load project context:

```
/cc-prime-cw              # Basic context priming
/cc-prime-cw --with-history  # Include last session analysis (if applicable)
```

This command:
1. Discovers files using glob patterns from `domains.yaml`
2. Spawns analyst subagents to read and synthesize findings
3. Loads dense project understanding into your context window

### Task Execution (`/cc-execute`)

Run to execute structured work using subagents:

```
/cc-execute Fix the authentication bug
/cc-execute Add input validation to the API
/cc-execute  # Will ask what to work on
```

This command provides:
- Structured phase workflow (understand → plan → investigate → execute → verify)
- Subagent templates for investigation, implementation, verification
- Adversarial challenge protocol for high-stakes claims

### Session Conclude (`/cc-conclude`)

Run at the end of a session to wrap up work:

```
/cc-conclude              # Full workflow with prompts
/cc-conclude --commit     # Quick commit workflow
/cc-conclude --no-readme  # Skip README update check
```

This command provides:
- Session summary generation from git state and context
- README.md update detection and drafting
- Git commit workflow with intelligent message generation
- Optional push with remote status context

## Session Lifecycle

```
/cc-prime-cw     → Load context (session start)
        ↓
   [saves .claude/session/manifest.json]
        ↓
/cc-execute      → Do work (session active)
        ↓              ↑
   [reads session]  [reads project config]
        ↓
/cc-conclude     → Wrap up (session end)
        ↓              ↑
   [reads session]  [reads git state]
```

**Session State Flow**:
1. `/cc-prime-cw` discovers domains/files and saves manifest to `.claude/session/`
2. `/cc-execute` reads session context + detects test/build commands from project files
3. `/cc-conclude` reads session context + git state for intelligent summaries

## Customization

### Configuration Files

| Skill | Config File | Purpose |
|-------|-------------|---------|
| cc-prime-cw | `domains.yaml` | Domain patterns, foundation docs, report sections |
| cc-execute | `workflow.yaml` | Subagent roles, test commands, adversarial config |
| cc-conclude | `workflow.yaml` | README triggers, commit types, git config |

### Adding Project-Specific Domains

Edit `.claude/skills/cc-prime-cw/domains.yaml` to add domains relevant to your project:

```yaml
domains:
  - name: my_domain
    description: |
      Description of what this domain covers.
    patterns:
      - "src/my_module/**/*.py"
    keywords:
      - "MyClass|my_function"
    report_sections:
      - key_components: "Main classes and functions"
```

### Adding Project-Specific Test Commands

Edit `.claude/skills/cc-execute/workflow.yaml` under `project_detection`:

```yaml
project_detection:
  my_framework:
    indicators:
      - my_config.toml
    test_commands:
      - "my-test-runner"
    lint_commands:
      - "my-linter"
```

### Token Budget Philosophy

**Subagent context is expendable** - they read thoroughly and synthesize.
**Main agent context is precious** - receive only dense findings.

This allows understanding 50,000+ lines of code while consuming only ~10K tokens.
