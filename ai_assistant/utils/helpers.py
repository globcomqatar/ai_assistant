"""General-purpose utility helpers for AI Assistant modules."""

from __future__ import annotations

from typing import Any


def clamp(value: int | float, min_val: int | float, max_val: int | float) -> int | float:
    """Clamp a numeric value to [min_val, max_val]."""
    return max(min_val, min(max_val, value))


def safe_float(value: Any, default: float = 0.0) -> float:
    """Parse value as float, return default on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """Parse value as int, return default on failure."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def truncate(value: Any, limit: int = 500) -> str:
    """Convert to string and truncate to limit characters."""
    return str(value or "").strip()[:limit]


def format_currency(amount: float | None, currency: str = "QAR") -> str:
    """Format a numeric amount as a currency string."""
    if amount is None:
        return f"0.00 {currency}"
    return f"{amount:,.2f} {currency}"


def pct_change(current: float, previous: float) -> float | None:
    """Return percentage change from previous to current. None if previous is zero."""
    if not previous:
        return None
    return round((current - previous) / previous * 100, 2)


def normalize_to_100(value: float, low: float = 0.0, high: float = 1.0) -> int:
    """Map a value in [low, high] to an integer in [0, 100]."""
    if high == low:
        return 0
    normalized = (value - low) / (high - low)
    return int(clamp(normalized * 100, 0, 100))
