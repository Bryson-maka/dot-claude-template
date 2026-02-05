#!/usr/bin/env python3
"""
Session State Manager

Provides file-based session state management for Claude Code skills.
State is stored in .claude/session/state.json and persists across skill invocations.

Usage:
    from session_state import SessionState

    state = SessionState()
    state.mark_primed(domains=['source', 'config'])
    state.log_task_created('Fix bug', task_id='1')
    state.log_subagent('investigator', 'Explore', 'sonnet', 'Find config issue')
    state.log_verification('test', passed=True, details='18 tests passed')
    state.conclude()

State Schema (v1.0):
    {
        "schema_version": "1.0",
        "primed_at": "ISO timestamp or null",
        "concluded_at": "ISO timestamp or null",
        "domains": ["source", "config", ...],
        "foundation_docs": ["README.md", ...],
        "execution_journal": [
            {"ts": "...", "type": "task_created", "subject": "...", "task_id": "..."},
            {"ts": "...", "type": "subagent_spawned", "role": "...", "model": "..."},
            ...
        ],
        "subagents": [
            {"role": "investigator", "type": "Explore", "model": "sonnet", "description": "..."},
            ...
        ],
        "verification_results": [
            {"type": "test", "passed": true, "details": "...", "ts": "..."},
            ...
        ],
        "files_modified": ["path/to/file.py", ...]
    }
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# Schema version for forward compatibility
SCHEMA_VERSION = "1.0"


def get_project_root() -> Path:
    """Find project root by looking for .claude directory."""
    # Start from current working directory
    current = Path.cwd()

    # Walk up looking for .claude directory
    for parent in [current] + list(current.parents):
        if (parent / '.claude').is_dir():
            return parent

    # Fallback to cwd
    return current


def get_state_path(base_dir: Optional[Path] = None) -> Path:
    """Get path to state.json file."""
    if base_dir is None:
        base_dir = get_project_root()
    return base_dir / '.claude' / 'session' / 'state.json'


def get_history_path(base_dir: Optional[Path] = None) -> Path:
    """Get path to history.jsonl file."""
    if base_dir is None:
        base_dir = get_project_root()
    return base_dir / '.claude' / 'session' / 'history.jsonl'


def timestamp() -> str:
    """Get current ISO timestamp."""
    return datetime.now(timezone.utc).isoformat()


class SessionState:
    """
    Manages session state stored in .claude/session/state.json.

    Provides methods for:
    - Marking session as primed (cc-prime-cw)
    - Logging execution journal entries (cc-execute)
    - Recording verification results (cc-execute)
    - Concluding session with archival (cc-conclude)
    """

    def __init__(self, base_dir: Optional[Path] = None):
        """Initialize session state manager.

        Args:
            base_dir: Project root directory. Auto-detected if not provided.
        """
        self.base_dir = base_dir or get_project_root()
        self.state_path = get_state_path(self.base_dir)
        self.history_path = get_history_path(self.base_dir)
        self._state: Optional[dict[str, Any]] = None

    @property
    def state(self) -> dict[str, Any]:
        """Get current state, loading from disk if needed."""
        if self._state is None:
            self._state = self._load()
        return self._state

    def _load(self) -> dict[str, Any]:
        """Load state from disk, creating default if not exists."""
        if self.state_path.exists():
            try:
                with open(self.state_path, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                # Validate schema version
                if state.get('schema_version') != SCHEMA_VERSION:
                    print(f"Warning: State schema version mismatch", file=sys.stderr)
                return state
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load state: {e}", file=sys.stderr)

        # Return default state
        return self._default_state()

    def _default_state(self) -> dict[str, Any]:
        """Create default empty state."""
        return {
            "schema_version": SCHEMA_VERSION,
            "primed_at": None,
            "concluded_at": None,
            "domains": [],
            "foundation_docs": [],
            "execution_journal": [],
            "subagents": [],
            "verification_results": [],
            "files_modified": [],
        }

    def _save(self) -> bool:
        """Save state to disk."""
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_path, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=2)
            return True
        except IOError as e:
            print(f"Error saving state: {e}", file=sys.stderr)
            return False

    # ========== cc-prime-cw Methods ==========

    def mark_primed(
        self,
        domains: list[str],
        foundation_docs: Optional[list[str]] = None,
    ) -> bool:
        """Mark session as primed with domain information.

        Called by cc-prime-cw after completing context priming.

        Args:
            domains: List of domain names that were analyzed
            foundation_docs: List of foundation documents that were read

        Returns:
            True if state was saved successfully
        """
        self.state["primed_at"] = timestamp()
        self.state["concluded_at"] = None  # Reset if re-priming
        self.state["domains"] = domains
        self.state["foundation_docs"] = foundation_docs or []

        # Clear previous execution data on new prime
        self.state["execution_journal"] = []
        self.state["subagents"] = []
        self.state["verification_results"] = []
        self.state["files_modified"] = []

        # Log priming event
        self._log_journal("session_primed", {
            "domains": domains,
            "foundation_docs": foundation_docs or [],
        })

        return self._save()

    def is_primed(self) -> bool:
        """Check if session has been primed."""
        return self.state.get("primed_at") is not None

    # ========== cc-execute Methods ==========

    def _log_journal(self, entry_type: str, data: dict[str, Any]) -> None:
        """Add entry to execution journal."""
        entry = {
            "ts": timestamp(),
            "type": entry_type,
            **data,
        }
        self.state["execution_journal"].append(entry)

    def log_task_created(self, subject: str, task_id: Optional[str] = None) -> bool:
        """Log task creation."""
        self._log_journal("task_created", {
            "subject": subject,
            "task_id": task_id,
        })
        return self._save()

    def log_task_started(self, task_id: str, subject: Optional[str] = None) -> bool:
        """Log task start."""
        self._log_journal("task_started", {
            "task_id": task_id,
            "subject": subject,
        })
        return self._save()

    def log_task_completed(self, task_id: str, subject: Optional[str] = None) -> bool:
        """Log task completion."""
        self._log_journal("task_completed", {
            "task_id": task_id,
            "subject": subject,
        })
        return self._save()

    def log_subagent(
        self,
        role: str,
        agent_type: str,
        model: str,
        description: str,
    ) -> bool:
        """Log subagent spawn."""
        subagent_entry = {
            "role": role,
            "type": agent_type,
            "model": model,
            "description": description,
            "spawned_at": timestamp(),
        }
        self.state["subagents"].append(subagent_entry)

        self._log_journal("subagent_spawned", {
            "role": role,
            "type": agent_type,
            "model": model,
        })

        return self._save()

    def log_subagent_completed(self, role: str, result_summary: Optional[str] = None) -> bool:
        """Log subagent completion."""
        self._log_journal("subagent_completed", {
            "role": role,
            "result_summary": result_summary,
        })
        return self._save()

    def log_verification(
        self,
        verification_type: str,
        passed: bool,
        details: Optional[str] = None,
    ) -> bool:
        """Log verification result (test, lint, adversarial).

        Args:
            verification_type: 'test', 'lint', or 'adversarial'
            passed: Whether verification passed
            details: Optional details about the result
        """
        result = {
            "type": verification_type,
            "passed": passed,
            "details": details,
            "ts": timestamp(),
        }
        self.state["verification_results"].append(result)

        self._log_journal("verification", {
            "verification_type": verification_type,
            "passed": passed,
        })

        return self._save()

    def log_file_modified(self, file_path: str) -> bool:
        """Log a file modification."""
        if file_path not in self.state["files_modified"]:
            self.state["files_modified"].append(file_path)
        return self._save()

    def log_files_modified(self, file_paths: list[str]) -> bool:
        """Log multiple file modifications."""
        for path in file_paths:
            if path not in self.state["files_modified"]:
                self.state["files_modified"].append(path)
        return self._save()

    # ========== cc-conclude Methods ==========

    def get_execution_summary(self) -> dict[str, Any]:
        """Get summary of execution for cc-conclude.

        Returns dict with:
            - tasks_completed: count
            - subagents_spawned: count by role
            - verifications: list of results
            - files_modified: list
        """
        journal = self.state.get("execution_journal", [])

        tasks_completed = sum(1 for e in journal if e["type"] == "task_completed")

        subagents = self.state.get("subagents", [])
        subagent_counts: dict[str, int] = {}
        for s in subagents:
            role = s.get("role", "unknown")
            subagent_counts[role] = subagent_counts.get(role, 0) + 1

        return {
            "primed_at": self.state.get("primed_at"),
            "tasks_completed": tasks_completed,
            "subagents_spawned": len(subagents),
            "subagent_counts": subagent_counts,
            "verifications": self.state.get("verification_results", []),
            "files_modified": self.state.get("files_modified", []),
        }

    def conclude(self) -> bool:
        """Conclude the session and archive to history.

        Called by cc-conclude after committing.
        Archives full state to history.jsonl and resets for next session.

        Returns:
            True if conclude and archive succeeded
        """
        self.state["concluded_at"] = timestamp()
        self._log_journal("session_concluded", {})

        # Archive to history
        archived = self._archive_to_history()

        # Save final state
        saved = self._save()

        return archived and saved

    def _archive_to_history(self) -> bool:
        """Append current state to history.jsonl."""
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)

            # Create archive entry
            archive_entry = {
                "archived_at": timestamp(),
                "state": self.state.copy(),
            }

            with open(self.history_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(archive_entry) + '\n')

            return True
        except IOError as e:
            print(f"Error archiving to history: {e}", file=sys.stderr)
            return False

    def reset(self) -> bool:
        """Reset state for new session.

        Preserves history but clears current state.
        """
        self._state = self._default_state()
        return self._save()

    # ========== Utility Methods ==========

    def to_dict(self) -> dict[str, Any]:
        """Return state as dictionary."""
        return self.state.copy()

    def to_json(self, pretty: bool = False) -> str:
        """Return state as JSON string."""
        indent = 2 if pretty else None
        return json.dumps(self.state, indent=indent)


# ========== CLI Interface ==========

def main():
    """CLI for session state management."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Manage Claude Code session state',
    )
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # show command
    show_parser = subparsers.add_parser('show', help='Show current state')
    show_parser.add_argument('--pretty', action='store_true', help='Pretty print')

    # prime command
    prime_parser = subparsers.add_parser('prime', help='Mark session as primed')
    prime_parser.add_argument('--domains', nargs='+', required=True, help='Domains analyzed')
    prime_parser.add_argument('--docs', nargs='*', help='Foundation docs read')

    # log command
    log_parser = subparsers.add_parser('log', help='Log an event')
    log_parser.add_argument('--type', required=True,
                           choices=['task_created', 'task_started', 'task_completed',
                                   'subagent', 'verification', 'file_modified'])
    log_parser.add_argument('--subject', help='Task subject')
    log_parser.add_argument('--task-id', help='Task ID')
    log_parser.add_argument('--role', help='Subagent role')
    log_parser.add_argument('--model', help='Subagent model')
    log_parser.add_argument('--passed', action='store_true', help='Verification passed')
    log_parser.add_argument('--verification-type',
                           choices=['test', 'lint', 'adversarial'],
                           default='test',
                           help='Verification type (default: test)')
    log_parser.add_argument('--details', help='Event details')
    log_parser.add_argument('--file', help='File path')

    # conclude command
    subparsers.add_parser('conclude', help='Conclude session and archive')

    # reset command
    subparsers.add_parser('reset', help='Reset state for new session')

    # summary command
    subparsers.add_parser('summary', help='Show execution summary')

    args = parser.parse_args()

    state = SessionState()

    if args.command == 'show':
        print(state.to_json(pretty=args.pretty))

    elif args.command == 'prime':
        state.mark_primed(args.domains, args.docs)
        print(f"Session primed with domains: {args.domains}")

    elif args.command == 'log':
        if args.type == 'task_created':
            state.log_task_created(args.subject or '', args.task_id)
        elif args.type == 'task_started':
            state.log_task_started(args.task_id or '', args.subject)
        elif args.type == 'task_completed':
            state.log_task_completed(args.task_id or '', args.subject)
        elif args.type == 'subagent':
            state.log_subagent(args.role or '', 'Explore', args.model or 'sonnet', args.details or '')
        elif args.type == 'verification':
            state.log_verification(args.verification_type, args.passed, args.details)
        elif args.type == 'file_modified':
            state.log_file_modified(args.file or '')
        print(f"Logged: {args.type}")

    elif args.command == 'conclude':
        state.conclude()
        print("Session concluded and archived")

    elif args.command == 'reset':
        state.reset()
        print("Session state reset")

    elif args.command == 'summary':
        summary = state.get_execution_summary()
        print(json.dumps(summary, indent=2))

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
