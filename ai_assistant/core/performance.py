"""
Performance monitoring utilities for the AI Assistant platform.

Provides a context manager and a per-request tracker for measuring
execution times across the AI pipeline stages.

Usage:
    from ai_assistant.core.performance import timed, PerformanceTracker

    # Context manager
    with timed("provider_call", user=user, agent=agent_code):
        response = provider.chat(messages, system_prompt)

    # Per-request tracker
    tracker = PerformanceTracker()
    tracker.start("routing")
    agent_code = supervisor.route_to_agent(message, user)
    routing_ms = tracker.stop("routing")

    tracker.start("execution")
    results = execute_actions(actions, user, ...)
    tracker.stop("execution")

    print(tracker.summary())
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator


@dataclass
class Timing:
    """A single named elapsed-time measurement."""
    name: str
    elapsed: float          # seconds
    metadata: dict = field(default_factory=dict)

    @property
    def elapsed_ms(self) -> float:
        return self.elapsed * 1000

    @property
    def is_slow(self) -> bool:
        from ai_assistant.config.settings import SLOW_QUERY_THRESHOLD_MS
        return self.elapsed_ms > SLOW_QUERY_THRESHOLD_MS


@contextmanager
def timed(name: str, log: bool = True, **metadata) -> Generator[None, None, None]:
    """
    Context manager that measures elapsed time and optionally logs it.

    Slow operations (exceeding SLOW_QUERY_THRESHOLD_MS) emit a warning.

    Args:
        name:     Human-readable name for this timed block.
        log:      When True, emit a performance log entry on exit.
        metadata: Extra fields attached to the log entry.
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        timing = Timing(name=name, elapsed=elapsed, metadata=metadata)

        if log:
            try:
                from ai_assistant.utils.logger import log_performance
                log_performance(name, elapsed, **metadata)
            except Exception:
                pass

        if timing.is_slow:
            try:
                from ai_assistant.utils.logger import get_logger, PERFORMANCE
                get_logger(PERFORMANCE).warning(
                    f"Slow: {name} took {elapsed * 1000:.1f}ms"
                )
            except Exception:
                pass


class PerformanceTracker:
    """
    Tracks multiple named timing segments within a single request.

    start() / stop() pairs are lightweight — no threading required because
    each Frappe request runs in its own greenlet/worker.
    """

    def __init__(self) -> None:
        self._starts: dict[str, float] = {}
        self._timings: list[Timing] = []

    def start(self, name: str) -> None:
        """Begin timing for ``name``."""
        self._starts[name] = time.perf_counter()

    def stop(self, name: str, **metadata) -> float:
        """
        Stop timing for ``name`` and record the measurement.

        Returns the elapsed seconds (0.0 if start() was never called for name).
        """
        if name not in self._starts:
            return 0.0
        elapsed = time.perf_counter() - self._starts.pop(name)
        self._timings.append(Timing(name=name, elapsed=elapsed, metadata=metadata))
        return elapsed

    def all_timings(self) -> list[Timing]:
        """Return all completed timing measurements."""
        return list(self._timings)

    def total(self) -> float:
        """Sum of all measured elapsed times in seconds."""
        return sum(t.elapsed for t in self._timings)

    def slow_timings(self) -> list[Timing]:
        """Return only measurements that exceeded SLOW_QUERY_THRESHOLD_MS."""
        return [t for t in self._timings if t.is_slow]

    def summary(self) -> dict[str, Any]:
        """Serializable summary suitable for log entries or debug output."""
        return {
            "total_s": round(self.total(), 4),
            "steps": [
                {
                    "name": t.name,
                    "elapsed_ms": round(t.elapsed_ms, 2),
                    "slow": t.is_slow,
                }
                for t in self._timings
            ],
        }
