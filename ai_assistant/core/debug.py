"""
Debug mode utilities for the AI Assistant platform.

Debug mode activates when either:
- Frappe developer_mode is on (frappe.conf.developer_mode)
- The site config key ai_debug_mode is set to 1

When disabled (production), these helpers are no-ops — no performance cost,
no sensitive data leakage.

Usage:
    from ai_assistant.core.debug import is_debug_mode, debug_log, debug_timing

    if is_debug_mode():
        debug_log("Full system prompt", data=system_prompt)

    debug_timing("provider_call", elapsed=0.34, model="gpt-4o")
"""
from __future__ import annotations

from typing import Any


def is_debug_mode() -> bool:
    """Return True when AI Assistant debug mode is active."""
    try:
        import frappe
        return bool(
            frappe.conf.get("developer_mode")
            or frappe.conf.get("ai_debug_mode")
        )
    except Exception:
        return False


def debug_log(message: str, data: Any = None, category: str = "ai_assistant.debug", **ctx) -> None:
    """Log a debug message — no-op when debug mode is off."""
    if not is_debug_mode():
        return
    try:
        from ai_assistant.utils.logger import get_logger, _build_entry
        get_logger(category).debug(_build_entry(message, data, **ctx))
    except Exception:
        pass


def debug_timing(name: str, elapsed: float, **ctx) -> None:
    """Emit a performance timing log — no-op when debug mode is off."""
    if not is_debug_mode():
        return
    try:
        from ai_assistant.utils.logger import log_performance
        log_performance(name, elapsed, debug=True, **ctx)
    except Exception:
        pass


def debug_dump(label: str, obj: Any) -> None:
    """Pretty-print an object to the debug logger — useful during development."""
    if not is_debug_mode():
        return
    try:
        import json
        from ai_assistant.utils.logger import get_logger
        body = json.dumps(obj, default=str, indent=2) if not isinstance(obj, str) else obj
        get_logger("ai_assistant.debug").debug(f"[DUMP] {label}:\n{body}")
    except Exception:
        pass
