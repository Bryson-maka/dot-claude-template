---
paths:
  - ".claude/lib/**/*.py"
  - ".claude/skills/**/*.py"
---

# Python Rules for .claude Scripts

- Use type hints on all function signatures
- Use dataclasses for structured data (not dicts)
- Handle ImportError gracefully - scripts may run without optional dependencies
- Use `if __name__ == "__main__"` for CLI entry points
- Scripts should work with Python 3.10+ (no walrus operators in critical paths)
- Use json module for all serialization (not yaml for session state)
- File paths should use pathlib.Path, resolved relative to script location
- Always handle missing files gracefully (session may not be initialized)
- Prefer sys.exit(0/1) over raising exceptions in CLI scripts
