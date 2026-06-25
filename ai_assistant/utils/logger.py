"""
Centralized logging utility for the AI Assistant platform.

Provides category-specific loggers and helper methods so no module
needs to construct its own logger or remember naming conventions.

Usage:
    from ai_assistant.utils.logger import log_request, log_security, log_exception

    log_request("Message dispatched", user=user, agent=agent_code)
    log_security("Permission denied", tool=tool_name, level="warning")
    log_exception("Provider call failed", exc=exc, user=user)
"""
from __future__ import annotations

import json
from typing import Any


# ── Category names ─────────────────────────────────────────────────────────────
AI_REQUEST   = "ai_assistant.request"
AI_RESPONSE  = "ai_assistant.response"
AI_ENGINE    = "ai_assistant.engine"
ACTION       = "ai_assistant.action"
APPROVAL     = "ai_assistant.approval"
WORKFLOW     = "ai_assistant.workflow"
SECURITY     = "ai_assistant.security"
PERFORMANCE  = "ai_assistant.performance"
API          = "ai_assistant.api"
SCHEDULER    = "ai_assistant.scheduler"
EXCEPTION    = "ai_assistant.exception"

# Internal cache — avoids re-creating loggers on every call
_LOGGER_CACHE: dict[str, Any] = {}


def get_logger(category: str):
    """Return a cached Frappe logger for the given category string."""
    if category not in _LOGGER_CACHE:
        import frappe
        _LOGGER_CACHE[category] = frappe.logger(category, with_more_info=False)
    return _LOGGER_CACHE[category]


# ── Serialization helpers ──────────────────────────────────────────────────────

def _safe_json(value: Any) -> str:
    """Serialize a value to a compact JSON string, falling back to str()."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, default=str, separators=(",", ":"))
    except Exception:
        return str(value)


def _build_entry(message: str, data: Any = None, **context) -> str:
    """Build a log entry dict and serialize to JSON."""
    entry: dict[str, Any] = {"msg": message}
    if data is not None:
        entry["data"] = data
    entry.update({k: v for k, v in context.items() if v is not None})
    return _safe_json(entry)


# ── Per-category helpers ───────────────────────────────────────────────────────

def log_request(message: str, data: Any = None, **ctx) -> None:
    """Log an inbound AI chat request."""
    get_logger(AI_REQUEST).info(_build_entry(message, data, **ctx))


def log_response(message: str, data: Any = None, **ctx) -> None:
    """Log an outbound AI provider response."""
    get_logger(AI_RESPONSE).info(_build_entry(message, data, **ctx))


def log_engine(message: str, data: Any = None, level: str = "info", **ctx) -> None:
    """Log an AI engine lifecycle event."""
    log = get_logger(AI_ENGINE)
    entry = _build_entry(message, data, **ctx)
    getattr(log, level, log.info)(entry)


def log_action(message: str, data: Any = None, **ctx) -> None:
    """Log an Action Center execution event."""
    get_logger(ACTION).info(_build_entry(message, data, **ctx))


def log_approval(message: str, data: Any = None, **ctx) -> None:
    """Log an Approval Center event."""
    get_logger(APPROVAL).info(_build_entry(message, data, **ctx))


def log_workflow(message: str, data: Any = None, **ctx) -> None:
    """Log a Workflow Automation event."""
    get_logger(WORKFLOW).info(_build_entry(message, data, **ctx))


def log_security(message: str, data: Any = None, level: str = "warning", **ctx) -> None:
    """Log a security event (permission check, denial, etc.)."""
    log = get_logger(SECURITY)
    entry = _build_entry(message, data, **ctx)
    getattr(log, level, log.warning)(entry)


def log_performance(name: str, elapsed_s: float, **ctx) -> None:
    """Log a performance timing measurement."""
    entry = _build_entry(
        f"{name}: {elapsed_s:.4f}s",
        elapsed_s=round(elapsed_s, 6),
        **ctx,
    )
    get_logger(PERFORMANCE).info(entry)


def log_api(message: str, data: Any = None, **ctx) -> None:
    """Log an API endpoint event."""
    get_logger(API).info(_build_entry(message, data, **ctx))


def log_scheduler(message: str, data: Any = None, **ctx) -> None:
    """Log a scheduled task event."""
    get_logger(SCHEDULER).info(_build_entry(message, data, **ctx))


def log_exception(
    message: str,
    exc: BaseException | None = None,
    *,
    record_error_log: bool = True,
    **ctx,
) -> None:
    """
    Log an exception with optional Frappe Error Log entry.

    Never exposes Python tracebacks to end users — those stay in the
    Frappe Error Log (developer-only) while the caller receives a safe
    user_message from the exception hierarchy.
    """
    entry = _build_entry(message, str(exc) if exc else None, **ctx)
    get_logger(EXCEPTION).error(entry)

    if record_error_log:
        try:
            import frappe
            tb = frappe.get_traceback() if frappe.local else (str(exc) if exc else "")
            title = f"AI Assistant: {message}"[:140]
            frappe.log_error(title=title, message=tb or entry)
        except Exception:
            pass
