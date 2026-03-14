#!/usr/bin/env python3
"""Persist cc-execute team lifecycle from hook payloads."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any


def _project_dir() -> Path:
    env_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_dir:
        return Path(env_dir)
    return Path(__file__).resolve().parents[2]


def _load_state():
    lib_dir = _project_dir() / ".claude" / "lib"
    if str(lib_dir) not in sys.path:
        sys.path.insert(0, str(lib_dir))
    from session_state import SessionState  # pylint: disable=import-outside-toplevel

    return SessionState(_project_dir())


def _read_json_stdin() -> dict[str, Any]:
    try:
        return json.load(sys.stdin)
    except json.JSONDecodeError:
        return {}


def _tool_success(response: Any) -> bool:
    if isinstance(response, dict) and response.get("success") is False:
        return False
    if isinstance(response, str) and response.strip().lower().startswith("error"):
        return False
    return True


def _content_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("stdout", "output", "message", "result", "text"):
            if isinstance(value.get(key), str) and value[key].strip():
                return value[key]
        if "content" in value:
            return _content_text(value["content"])
        return ""
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            parts.append(_content_text(item))
        return "\n".join(part for part in parts if part)
    return ""


def _extract_line(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
    if not match:
        return None
    return " ".join(match.group(1).strip().split())


def handle_team_create(payload: dict[str, Any]) -> int:
    tool_input = payload.get("tool_input", {})
    team_name = tool_input.get("team_name") or tool_input.get("name")
    if not team_name or not _tool_success(payload.get("tool_response")):
        return 0

    state = _load_state()
    state.log_team_created(team_name, [])
    return 0


def handle_team_delete(payload: dict[str, Any]) -> int:
    tool_input = payload.get("tool_input", {})
    team_name = tool_input.get("team_name") or tool_input.get("name")
    if not team_name or not _tool_success(payload.get("tool_response")):
        return 0

    state = _load_state()
    state.log_team_closed(team_name)
    return 0


def handle_task_complete(payload: dict[str, Any]) -> int:
    tool_input = payload.get("tool_input", {})
    tool_response = payload.get("tool_response")
    if not _tool_success(tool_response):
        return 0

    team_name = tool_input.get("team_name")
    if not team_name:
        return 0

    name = tool_input.get("name") or tool_input.get("agent_name") or "subagent"
    agent_type = tool_input.get("subagent_type") or tool_input.get("agent_type") or "unknown"
    model = tool_input.get("model") or tool_input.get("model_name") or "sonnet"

    state = _load_state()
    state.add_team_member(team_name, name, agent_type, model)

    prompt = _content_text(tool_input.get("prompt"))
    if name != "adversary" and "devil's advocate" not in prompt.lower():
        return 0

    response_text = _content_text(tool_response)
    verdict = _extract_line(r"^\s*(?:-\s*)?\*\*Verdict\*\*:\s*(ACCEPTED|CHALLENGED)\b", response_text)
    if not verdict:
        verdict = _extract_line(r"^\s*(?:-\s*)?Verdict:\s*(ACCEPTED|CHALLENGED)\b", response_text)
    if not verdict:
        return 0

    findings = _extract_line(r"^\s*(?:-\s*)?\*\*Holes found\*\*:\s*(.+?)\s*$", response_text)
    if not findings:
        findings = _extract_line(r"^\s*(?:-\s*)?\*\*Strengths\*\*:\s*(.+?)\s*$", response_text)

    state.log_adversary_verdict(team_name, verdict.upper(), findings)
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        return 0

    payload = _read_json_stdin()
    mode = sys.argv[1]
    if mode == "team-create":
        return handle_team_create(payload)
    if mode == "team-delete":
        return handle_team_delete(payload)
    if mode == "task-complete":
        return handle_task_complete(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
