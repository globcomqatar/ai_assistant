"""
Standardized API response helpers for AI Assistant endpoints.

All whitelisted endpoints should return a dict produced by ok() or error().
This ensures a consistent shape that the frontend can rely on regardless of
which endpoint was called.

Standard shape:
    {
        "success": bool,
        "ok": bool,           # alias for success
        "message": str,
        "request_id": str,    # 8-char random ID for log correlation
        "execution_time": float,
        "warnings": list,
        "errors": list,
        ...data fields...     # merged at the top level for backward compat
    }

Usage:
    from ai_assistant.core.response import ok, error, RequestTimer

    timer = RequestTimer()
    try:
        data = do_work()
        return ok("Report generated.", data, execution_time=timer.elapsed())
    except Exception as exc:
        return error("Report failed.", execution_time=timer.elapsed())
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class APIResponse:
    """
    Structured API response container.

    Call .to_dict() to produce the final response dict for Frappe whitelist
    endpoints. Data fields are merged at the top level to preserve backward
    compatibility with existing frontend code.
    """

    success: bool
    message: str
    data: Any = None
    warnings: list[str] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    execution_time: float = 0.0
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def to_dict(self) -> dict:
        result: dict[str, Any] = {
            "success": self.success,
            "ok": self.success,
            "message": self.message,
            "request_id": self.request_id,
        }
        # Merge dict data at top level for backward compat; wrap other types
        if self.data is not None:
            if isinstance(self.data, dict):
                result.update(self.data)
            else:
                result["data"] = self.data
        if self.warnings:
            result["warnings"] = self.warnings
        if self.errors:
            result["errors"] = self.errors
        if self.execution_time:
            result["execution_time"] = round(self.execution_time, 4)
        return result


def ok(
    message: str,
    data: Any = None,
    *,
    warnings: list[str] | None = None,
    execution_time: float = 0.0,
    **extra,
) -> dict:
    """
    Build a successful API response dict.

    ``extra`` kwargs are merged at the top level (for backward compatibility
    with callers that expect specific top-level keys alongside standard fields).
    """
    result = APIResponse(
        success=True,
        message=message,
        data=data,
        warnings=warnings or [],
        execution_time=execution_time,
    ).to_dict()
    result.update(extra)
    return result


def error(
    message: str,
    *,
    user_message: str | None = None,
    errors: list[dict] | None = None,
    recovery: str | None = None,
    execution_time: float = 0.0,
    **extra,
) -> dict:
    """
    Build an error API response dict.

    ``message`` is the developer-facing detail (logged internally).
    ``user_message`` is shown to the end user — defaults to a generic phrase.
    Python stack traces are NEVER included.
    """
    safe_message = user_message or "An error occurred. Please try again."
    result = APIResponse(
        success=False,
        message=safe_message,
        errors=errors or [{"message": message}],
        execution_time=execution_time,
    ).to_dict()
    if recovery:
        result["recovery"] = recovery
    result.update(extra)
    return result


def from_exception(exc: Exception, execution_time: float = 0.0) -> dict:
    """
    Build an error response from an AIAssistantError subclass.

    Falls back to a generic message for any other exception type so that
    internal details are never leaked to the frontend.
    """
    from ai_assistant.core.exceptions import AIAssistantError
    if isinstance(exc, AIAssistantError):
        return error(
            str(exc),
            user_message=exc.user_message,
            recovery=exc.recovery,
            errors=[exc.to_dict()],
            execution_time=execution_time,
        )
    return error(
        str(exc),
        user_message="An unexpected error occurred.",
        recovery="Please try again or contact your administrator.",
        execution_time=execution_time,
    )


class RequestTimer:
    """
    Lightweight request timer.

    Instantiate at the start of an API handler, call elapsed() or attach()
    at the end to record the wall-clock duration.

    Usage:
        timer = RequestTimer()
        result = do_work()
        return ok("Done.", result, execution_time=timer.elapsed())
    """

    def __init__(self) -> None:
        self._start: float = time.perf_counter()

    def elapsed(self) -> float:
        """Seconds since construction."""
        return time.perf_counter() - self._start

    def attach(self, response: dict) -> dict:
        """Set 'execution_time' on an existing response dict and return it."""
        response["execution_time"] = round(self.elapsed(), 4)
        return response
