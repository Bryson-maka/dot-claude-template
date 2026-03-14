#!/usr/bin/env python3
"""Persist cc-prime-cw summaries from hook payloads."""

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


def _content_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if "text" in value and isinstance(value["text"], str):
            return value["text"]
        if "content" in value:
            return _content_text(value["content"])
        return ""
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    parts.append(item["text"])
                elif "text" in item:
                    parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(part for part in parts if part)
    return ""


def _last_assistant_from_transcript(path_str: str | None) -> str:
    if not path_str:
        return ""
    path = Path(path_str)
    if not path.is_file():
        return ""

    try:
        for line in reversed(path.read_text(encoding="utf-8").splitlines()):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("role") != "assistant":
                continue
            return _content_text(entry.get("content"))
    except OSError:
        return ""

    return ""


def _message_text(payload: dict[str, Any], transcript_key: str) -> str:
    direct = _content_text(payload.get("last_assistant_message"))
    if direct.strip():
        return direct
    return _last_assistant_from_transcript(payload.get(transcript_key))


def _extract_line(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
    if not match:
        return None
    return " ".join(match.group(1).strip().split())


def _parse_domain_report(text: str) -> tuple[str | None, int | None, int | None, str | None]:
    domain = _extract_line(r"^\s*-\s*\*\*Domain\*\*:\s*(.+?)\s*$", text)
    if domain:
        domain = domain.lower().replace(" ", "-")
    else:
        domain = _extract_line(r"^\s*##\s+([A-Za-z0-9_-]+)\s*$", text)
        if domain:
            domain = domain.lower()

    files_read_raw = _extract_line(r"^\s*-\s*\*\*Files Read\*\*:\s*(\d+)\s*$", text)
    tokens_used_raw = _extract_line(r"^\s*-\s*\*\*Tokens Used\*\*:\s*(\d+)\s*$", text)
    summary = _extract_line(r"^\s*-\s*\*\*Reusable Summary\*\*:\s*(.+?)\s*$", text)

    return (
        domain,
        int(files_read_raw) if files_read_raw else None,
        int(tokens_used_raw) if tokens_used_raw else None,
        summary,
    )


def _parse_prime_summary(text: str) -> str | None:
    return _extract_line(r"^\s*\*\*Prime Summary\*\*:\s*(.+?)\s*$", text)


def handle_subagent() -> int:
    payload = _read_json_stdin()
    if payload.get("stop_hook_active"):
        return 0

    text = _message_text(payload, "agent_transcript_path")
    if not text.strip():
        return 0

    domain, files_read, tokens_used, summary = _parse_domain_report(text)
    if not domain or not summary:
        return 0

    state = _load_state()
    state.record_analyst_summary(
        domain,
        summary,
        files_read=files_read,
        tokens_used=tokens_used,
    )
    return 0


def handle_stop() -> int:
    payload = _read_json_stdin()
    text = _message_text(payload, "transcript_path")
    if not text.strip():
        return 0

    summary = _parse_prime_summary(text)
    if not summary:
        return 0

    state = _load_state()
    state.record_prime_summary(summary)
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        return 0

    mode = sys.argv[1]
    if mode == "subagent":
        return handle_subagent()
    if mode == "stop":
        return handle_stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
