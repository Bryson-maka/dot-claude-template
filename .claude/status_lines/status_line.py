#!/usr/bin/env python3
"""Simple status line for Claude Code: model, context, cost, cwd."""

from __future__ import annotations

import json
import os
import sys
from typing import Any

# ── ANSI colors ──────────────────────────────────────────────────────────────

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

C = {
    "cyan":    "\033[36m",
    "green":   "\033[32m",
    "yellow":  "\033[33m",
    "red":     "\033[31m",
    "magenta": "\033[35m",
    "blue":    "\033[34m",
    "gray":    "\033[90m",
    "white":   "\033[97m",
    # bright variants
    "b_cyan":    "\033[96m",
    "b_green":   "\033[92m",
    "b_yellow":  "\033[93m",
    "b_red":     "\033[91m",
    "b_magenta": "\033[95m",
    "b_blue":    "\033[94m",
}

FILLED = "█"
EMPTY = "░"
SEP = f" {C['gray']}│{RESET} "


# ── Helpers ──────────────────────────────────────────────────────────────────

def use_color() -> bool:
    return sys.stdout.isatty() and not os.getenv("NO_COLOR")


def paint(text: str, *codes: str) -> str:
    if not _COLOR:
        return text
    prefix = "".join(codes)
    return f"{prefix}{text}{RESET}" if prefix else text


def safe_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def safe_int(val: Any, default: int = 0) -> int:
    try:
        return int(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def fmt_cost(val: float) -> str:
    if val >= 10:
        return f"${val:.2f}"
    if val >= 1:
        return f"${val:.3f}"
    return f"${val:.4f}"


def shorten_path(path: str) -> str:
    home = os.path.expanduser("~")
    if path.startswith(home):
        return "~" + path[len(home):]
    return path


# ── Bar color thresholds ─────────────────────────────────────────────────────

def bar_color(pct: float) -> str:
    if pct < 50:
        return "b_green"
    if pct < 75:
        return "b_yellow"
    if pct < 90:
        return "b_red"
    return "b_magenta"


# ── Section builders ─────────────────────────────────────────────────────────

def model_section(data: dict[str, Any]) -> str:
    model_info = data.get("model") or {}
    if isinstance(model_info, dict):
        name = model_info.get("display_name") or "Claude"
    else:
        name = "Claude"
    return paint(name, BOLD, C["b_cyan"])


def context_section(data: dict[str, Any]) -> str:
    cw = data.get("context_window") or {}
    if not isinstance(cw, dict):
        cw = {}

    pct = max(0.0, min(100.0, safe_float(cw.get("used_percentage"), 0.0)))
    total = max(0, safe_int(cw.get("context_window_size"), 0))
    remaining = max(0, int(round(total * (100.0 - pct) / 100.0))) if total > 0 else 0

    width = 10
    filled = max(0, min(width, int(round(pct / 100.0 * width))))
    color = bar_color(pct)

    bar = paint(FILLED * filled, C[color]) + paint(EMPTY * (width - filled), C["gray"])
    pct_str = paint(f"{pct:.0f}%", C[color])
    left_str = paint(f"~{fmt_tokens(remaining)} left", DIM, C["white"])

    return f"{bar} {pct_str} {left_str}"


def cost_section(data: dict[str, Any]) -> str:
    cost = data.get("cost") or {}
    if not isinstance(cost, dict):
        return ""
    total = safe_float(cost.get("total_cost_usd"), -1.0)
    if total < 0:
        return ""
    return paint(fmt_cost(total), C["b_green"])


def cwd_section(data: dict[str, Any]) -> str:
    cwd = data.get("cwd") or ""
    if not cwd:
        try:
            cwd = os.getcwd()
        except OSError:
            return ""
    return paint(shorten_path(str(cwd)), C["b_blue"])


# ── Main ─────────────────────────────────────────────────────────────────────

_COLOR = False  # set at runtime


def build_status(data: dict[str, Any]) -> str:
    parts = [
        model_section(data),
        context_section(data),
        cost_section(data),
        cwd_section(data),
    ]
    return SEP.join(p for p in parts if p)


def main() -> int:
    global _COLOR
    _COLOR = use_color()
    try:
        raw = sys.stdin.read().strip()
        data = json.loads(raw) if raw else {}
        if not isinstance(data, dict):
            data = {}
    except (json.JSONDecodeError, OSError):
        data = {}
    print(build_status(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
