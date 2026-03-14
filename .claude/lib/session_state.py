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

State Schema (v1.2):
    {
        "schema_version": "1.2",
        "primed_at": "ISO timestamp or null",
        "concluded_at": "ISO timestamp or null",
        "domains": ["source", "config", ...],
        "foundation_docs": ["README.md", ...],
        "prime_summary": "Compact priming synthesis or null",
        "analyst_summaries": [
            {
                "domain": "source",
                "summary": "Core architecture centers on ...",
                "files_read": 16,
                "tokens_used": 59702
            }
        ],
        "execution_journal": [
            {"ts": "...", "type": "task_created", "subject": "...", "task_id": "..."},
            {"ts": "...", "type": "subagent_spawned", "role": "...", "model": "..."},
            {"ts": "...", "type": "analyst_summary", "domain": "..."},
            {"ts": "...", "type": "prime_summary_recorded"},
            {"ts": "...", "type": "team_created", "team_name": "...", "member_count": N, "members": [...]},
            {"ts": "...", "type": "team_closed", "team_name": "..."},
            {"ts": "...", "type": "adversary_verdict", "team_name": "...", "verdict": "...", "findings": "..."},
            ...
        ],
        "subagents": [
            {"role": "investigator", "type": "Explore", "model": "sonnet", "description": "..."},
            ...
        ],
        "teams": [
            {
                "name": "cc-exec-auth-refactor",
                "created_at": "ISO timestamp",
                "closed_at": "ISO timestamp or null",
                "members": [{"name": "...", "type": "...", "model": "..."}],
                "adversary_verdict": "ACCEPTED or CHALLENGED or null",
                "adversary_findings": "summary string or null"
            },
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

# Import shared utility from lib package
try:
    from . import get_project_root
except ImportError:
    # Fallback for direct script execution
    def get_project_root() -> Path:
        """Find project root by looking for .claude directory."""
        current = Path.cwd()
        for parent in [current] + list(current.parents):
            if (parent / '.claude').is_dir():
                return parent
        return current

__all__ = [
    'SCHEMA_VERSION',
    'SessionState',
    'get_state_path',
    'get_history_path',
    'timestamp',
]

# Schema version for forward compatibility
SCHEMA_VERSION = "1.2"


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
                # Migrate older schemas forward lazily.
                schema_version = state.get('schema_version')
                if schema_version == '1.0':
                    state['teams'] = state.get('teams', [])
                    schema_version = '1.1'
                if schema_version in ('1.0', '1.1'):
                    state['prime_summary'] = state.get('prime_summary')
                    state['analyst_summaries'] = state.get('analyst_summaries', [])
                    state['schema_version'] = SCHEMA_VERSION
                elif schema_version != SCHEMA_VERSION:
                    print(f"Warning: State schema version mismatch", file=sys.stderr)
                # Self-heal: ensure all required fields exist with correct types
                defaults = self._default_state()
                # Expected types for nullable string fields
                _nullable_str = {'primed_at', 'concluded_at', 'schema_version'}
                for key, default_value in defaults.items():
                    if key not in state:
                        state[key] = default_value
                    elif key in _nullable_str:
                        # Must be str or None
                        if state[key] is not None and not isinstance(state[key], str):
                            print(f"Warning: State field '{key}' has wrong type, resetting", file=sys.stderr)
                            state[key] = default_value
                    elif default_value is not None and not isinstance(state[key], type(default_value)):
                        # Type mismatch — reset to default
                        print(f"Warning: State field '{key}' has wrong type, resetting", file=sys.stderr)
                        state[key] = default_value
                return state
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load state: {e}", file=sys.stderr)
                # Try backup
                backup_path = self.state_path.with_suffix('.json.bak')
                if backup_path.exists():
                    try:
                        with open(backup_path, 'r', encoding='utf-8') as f:
                            state = json.load(f)
                        print("Recovered state from backup", file=sys.stderr)
                        return state
                    except (json.JSONDecodeError, IOError):
                        pass

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
            "prime_summary": None,
            "analyst_summaries": [],
            "execution_journal": [],
            "subagents": [],
            "teams": [],
            "verification_results": [],
            "files_modified": [],
        }

    def _save(self) -> bool:
        """Save state to disk with backup."""
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            # Backup existing state before overwrite
            if self.state_path.exists():
                backup_path = self.state_path.with_suffix('.json.bak')
                try:
                    import shutil
                    shutil.copy2(self.state_path, backup_path)
                except IOError:
                    pass  # Best-effort backup
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
        self.state["prime_summary"] = None
        self.state["analyst_summaries"] = []

        # Clear previous execution data on new prime
        self.state["execution_journal"] = []
        self.state["subagents"] = []
        self.state["teams"] = []
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
            **data,
            "type": entry_type,
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
            "agent_type": agent_type,
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

    def record_analyst_summary(
        self,
        domain: str,
        summary: str,
        files_read: Optional[int] = None,
        tokens_used: Optional[int] = None,
    ) -> bool:
        """Persist a compact analyst summary for reuse by later skills."""
        role = f"analyst-{domain}"
        entry = {
            "domain": domain,
            "summary": summary,
            "files_read": files_read,
            "tokens_used": tokens_used,
            "recorded_at": timestamp(),
        }

        # Prime analysts are long-lived enough to be useful in session state even
        # if the skill records them at completion time rather than spawn time.
        if not any(s.get("role") == role for s in self.state["subagents"]):
            self.state["subagents"].append({
                "role": role,
                "type": "Explore",
                "model": "unknown",
                "description": f"Priming domain: {domain}",
                "spawned_at": timestamp(),
            })
            self._log_journal("subagent_spawned", {
                "role": role,
                "agent_type": "Explore",
                "model": "unknown",
            })

        updated = False
        for idx, existing in enumerate(self.state["analyst_summaries"]):
            if existing.get("domain") == domain:
                self.state["analyst_summaries"][idx] = entry
                updated = True
                break
        if not updated:
            self.state["analyst_summaries"].append(entry)

        self._log_journal("analyst_summary", {
            "domain": domain,
            "files_read": files_read,
            "tokens_used": tokens_used,
        })
        self._log_journal("subagent_completed", {
            "role": role,
            "result_summary": summary,
        })
        return self._save()

    def record_prime_summary(self, summary: str) -> bool:
        """Persist the lead's compact priming synthesis for reuse."""
        self.state["prime_summary"] = summary
        self._log_journal("prime_summary_recorded", {})
        return self._save()

    # ========== Team Methods ==========

    def _get_team(self, team_name: str) -> Optional[dict[str, Any]]:
        """Return the tracked team entry for a name, if present."""
        for team in self.state["teams"]:
            if team["name"] == team_name:
                return team
        return None

    def _ensure_team(self, team_name: str) -> tuple[dict[str, Any], bool]:
        """Ensure a team entry exists and return it with a created flag."""
        existing = self._get_team(team_name)
        if existing is not None:
            return existing, False

        team_entry = {
            "name": team_name,
            "created_at": timestamp(),
            "closed_at": None,
            "members": [],
            "adversary_verdict": None,
            "adversary_findings": None,
        }
        self.state["teams"].append(team_entry)
        return team_entry, True

    def log_team_created(self, team_name: str, members: Optional[list[dict]] = None) -> bool:
        """Log team creation.

        Args:
            team_name: Name of the team (e.g. 'cc-exec-auth-refactor')
            members: List of dicts with keys: name, type, model
        """
        team_entry, created = self._ensure_team(team_name)
        incoming_members = members or []
        existing_names = {member.get("name") for member in team_entry["members"]}
        for member in incoming_members:
            name = member.get("name")
            if name and name not in existing_names:
                team_entry["members"].append(member)
                existing_names.add(name)

        if created:
            self._log_journal("team_created", {
                "team_name": team_name,
                "member_count": len(team_entry["members"]),
                "members": list(team_entry["members"]),
            })

        return self._save()

    def add_team_member(self, team_name: str, name: str, agent_type: str, model: str) -> bool:
        """Register a team member if not already present."""
        team_entry, created = self._ensure_team(team_name)
        if created:
            self._log_journal("team_created", {
                "team_name": team_name,
                "member_count": 0,
                "members": [],
            })

        if not any(member.get("name") == name for member in team_entry["members"]):
            team_entry["members"].append({
                "name": name,
                "type": agent_type,
                "model": model,
            })

        return self._save()

    def log_team_closed(self, team_name: str) -> bool:
        """Log team shutdown. Sets closed_at on matching team."""
        team, created = self._ensure_team(team_name)
        if created:
            self._log_journal("team_created", {
                "team_name": team_name,
                "member_count": 0,
                "members": [],
            })
        team["closed_at"] = timestamp()

        self._log_journal("team_closed", {
            "team_name": team_name,
        })

        return self._save()

    def log_adversary_verdict(self, team_name: str, verdict: str, findings: str = None) -> bool:
        """Log adversarial challenge result.

        Args:
            team_name: Name of the team being challenged
            verdict: 'ACCEPTED' or 'CHALLENGED'
            findings: Summary string of adversary findings
        """
        team, created = self._ensure_team(team_name)
        if created:
            self._log_journal("team_created", {
                "team_name": team_name,
                "member_count": 0,
                "members": [],
            })
        team["adversary_verdict"] = verdict
        team["adversary_findings"] = findings

        self._log_journal("adversary_verdict", {
            "team_name": team_name,
            "verdict": verdict,
            "findings": findings,
        })

        self.state["verification_results"].append({
            "type": "adversarial",
            "passed": verdict == "ACCEPTED",
            "details": findings,
            "ts": timestamp(),
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

        teams = self.state.get("teams", [])

        return {
            "primed_at": self.state.get("primed_at"),
            "tasks_completed": tasks_completed,
            "subagents_spawned": len(subagents),
            "subagent_counts": subagent_counts,
            "prime_summary_available": bool(self.state.get("prime_summary")),
            "analyst_summaries_recorded": len(self.state.get("analyst_summaries", [])),
            "teams_created": len(teams),
            "teams": [
                {
                    "name": t["name"],
                    "members": len(t["members"]),
                    "verdict": t.get("adversary_verdict"),
                }
                for t in teams
            ],
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
                                   'subagent', 'subagent_completed',
                                   'analyst_summary', 'prime_summary',
                                   'verification', 'file_modified',
                                   'session_ended', 'session_checkpoint',
                                   'team_created', 'team_closed', 'adversary_verdict'])
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
    log_parser.add_argument('--agent-type',
                           choices=['Explore', 'general-purpose', 'Bash', 'Plan'],
                           default='Explore',
                           help='Subagent type (default: Explore)')
    log_parser.add_argument('--team-name', help='Team name (for team_created/team_closed/adversary_verdict)')
    log_parser.add_argument('--members', help='Team members as name:type:model,... (for team_created)')
    log_parser.add_argument('--verdict', choices=['ACCEPTED', 'CHALLENGED'],
                           help='Adversary verdict (for adversary_verdict)')
    log_parser.add_argument('--findings', help='Adversary findings summary (for adversary_verdict)')
    log_parser.add_argument('--domain', help='Domain name (for analyst_summary)')
    log_parser.add_argument('--files-read', type=int, help='Files read count (for analyst_summary)')
    log_parser.add_argument('--tokens-used', type=int, help='Approximate tokens used (for analyst_summary)')

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
            if not args.subject:
                print("Error: --subject is required for task_created", file=sys.stderr)
                sys.exit(1)
            state.log_task_created(args.subject, args.task_id)
        elif args.type == 'task_started':
            if not args.task_id:
                print("Error: --task-id is required for task_started", file=sys.stderr)
                sys.exit(1)
            state.log_task_started(args.task_id, args.subject)
        elif args.type == 'task_completed':
            state.log_task_completed(args.task_id or '', args.subject)
        elif args.type == 'subagent':
            if not args.role:
                print("Error: --role is required for subagent", file=sys.stderr)
                sys.exit(1)
            state.log_subagent(args.role, args.agent_type, args.model or 'sonnet', args.details or '')
        elif args.type == 'subagent_completed':
            if not args.role:
                print("Error: --role is required for subagent_completed", file=sys.stderr)
                sys.exit(1)
            state.log_subagent_completed(args.role, args.details)
        elif args.type == 'analyst_summary':
            if not args.domain:
                print("Error: --domain is required for analyst_summary", file=sys.stderr)
                sys.exit(1)
            if not args.details:
                print("Error: --details is required for analyst_summary", file=sys.stderr)
                sys.exit(1)
            state.record_analyst_summary(
                args.domain,
                args.details,
                files_read=args.files_read,
                tokens_used=args.tokens_used,
            )
        elif args.type == 'prime_summary':
            if not args.details:
                print("Error: --details is required for prime_summary", file=sys.stderr)
                sys.exit(1)
            state.record_prime_summary(args.details)
        elif args.type == 'verification':
            state.log_verification(args.verification_type, args.passed, args.details)
        elif args.type == 'file_modified':
            if not args.file:
                print("Error: --file is required for file_modified", file=sys.stderr)
                sys.exit(1)
            state.log_file_modified(args.file)
        elif args.type == 'team_created':
            if not args.team_name:
                print("Error: --team-name is required for team_created", file=sys.stderr)
                sys.exit(1)
            if not args.members:
                print("Error: --members is required for team_created", file=sys.stderr)
                sys.exit(1)
            members = []
            for member_str in args.members.split(','):
                parts = member_str.strip().split(':')
                if len(parts) != 3:
                    print(f"Error: Invalid member format '{member_str}', expected name:type:model", file=sys.stderr)
                    sys.exit(1)
                members.append({"name": parts[0], "type": parts[1], "model": parts[2]})
            state.log_team_created(args.team_name, members)
        elif args.type == 'team_closed':
            if not args.team_name:
                print("Error: --team-name is required for team_closed", file=sys.stderr)
                sys.exit(1)
            state.log_team_closed(args.team_name)
        elif args.type == 'adversary_verdict':
            if not args.team_name:
                print("Error: --team-name is required for adversary_verdict", file=sys.stderr)
                sys.exit(1)
            if not args.verdict:
                print("Error: --verdict is required for adversary_verdict", file=sys.stderr)
                sys.exit(1)
            state.log_adversary_verdict(args.team_name, args.verdict, args.findings)
        elif args.type == 'session_ended':
            state._log_journal("session_ended", {"details": args.details or ''})
            state._save()
        elif args.type == 'session_checkpoint':
            state._log_journal("session_checkpoint", {"details": args.details or ''})
            state._save()
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
