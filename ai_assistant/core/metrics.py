"""
Metrics collection framework for the AI Assistant platform.

Accumulates runtime counters within the current worker process.
Designed to be extended in Phase 3 with a persistent time-series backend
(Prometheus / InfluxDB / custom Frappe table).

Usage:
    from ai_assistant.core.metrics import metrics

    metrics.record_request(success=True, tokens=1240, cost=0.0024, elapsed=1.2)
    metrics.record_action("create_task", success=True)
    metrics.record_error("ProviderError")

    snapshot = metrics.snapshot()   # {requests: {...}, actions: {...}, ...}
    metrics.reset()                 # clear all counters (e.g. on hourly tick)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Any


@dataclass
class _RequestCounters:
    total: int = 0
    success: int = 0
    error: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_time_s: float = 0.0


class MetricsCollector:
    """
    In-process metrics accumulator (one instance per worker process).

    Phase 3 upgrade path:
    - Replace in-memory counters with atomic Redis writes for site-wide aggregation.
    - Export snapshot() to a time-series store via a scheduled task.
    - Add prediction_accuracy and llm_token_efficiency counters.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._requests = _RequestCounters()
        self._actions: dict[str, int] = {}
        self._workflows: dict[str, int] = {}
        self._approvals: dict[str, int] = {}
        self._errors: dict[str, int] = {}
        self._response_times: list[float] = []

    # ── Record methods ─────────────────────────────────────────────────────────

    def record_request(
        self,
        *,
        success: bool,
        tokens: int = 0,
        cost: float = 0.0,
        elapsed: float = 0.0,
    ) -> None:
        """Record a completed AI chat request."""
        with self._lock:
            self._requests.total += 1
            if success:
                self._requests.success += 1
            else:
                self._requests.error += 1
            self._requests.total_tokens += tokens
            self._requests.total_cost_usd += cost
            self._requests.total_time_s += elapsed
            if elapsed > 0:
                self._response_times.append(elapsed)
                # Keep only the last 1000 samples to cap memory usage
                if len(self._response_times) > 1000:
                    self._response_times = self._response_times[-1000:]

    def record_action(self, action_id: str, *, success: bool) -> None:
        """Record a completed Action Center execution."""
        key = f"{action_id}:{'ok' if success else 'err'}"
        with self._lock:
            self._actions[key] = self._actions.get(key, 0) + 1

    def record_workflow(self, workflow_id: str, *, success: bool) -> None:
        """Record a completed Workflow Automation run."""
        key = f"{workflow_id}:{'ok' if success else 'err'}"
        with self._lock:
            self._workflows[key] = self._workflows.get(key, 0) + 1

    def record_approval(self, action_id: str, *, decision: str) -> None:
        """Record an Approval Center decision (approved / rejected / modified)."""
        key = f"{action_id}:{decision}"
        with self._lock:
            self._approvals[key] = self._approvals.get(key, 0) + 1

    def record_error(self, error_type: str) -> None:
        """Increment the error counter for the given type name."""
        with self._lock:
            self._errors[error_type] = self._errors.get(error_type, 0) + 1

    # ── Query methods ──────────────────────────────────────────────────────────

    def avg_response_time(self) -> float:
        """Average response time in seconds across recorded requests."""
        with self._lock:
            if not self._response_times:
                return 0.0
            return sum(self._response_times) / len(self._response_times)

    def snapshot(self) -> dict[str, Any]:
        """
        Return a point-in-time metrics snapshot.

        Safe to call at any frequency — reads are lock-protected.
        """
        with self._lock:
            req = self._requests
            total = req.total or 1  # avoid division by zero
            return {
                "requests": {
                    "total": req.total,
                    "success": req.success,
                    "error": req.error,
                    "success_rate": round(req.success / total, 4),
                    "total_tokens": req.total_tokens,
                    "total_cost_usd": round(req.total_cost_usd, 6),
                    "avg_response_time_s": round(
                        req.total_time_s / total if req.total else 0.0, 4
                    ),
                },
                "actions": dict(self._actions),
                "workflows": dict(self._workflows),
                "approvals": dict(self._approvals),
                "errors": dict(self._errors),
                "p_samples": len(self._response_times),
            }

    def reset(self) -> None:
        """Clear all counters. Call from a scheduled task if needed."""
        with self._lock:
            self._requests = _RequestCounters()
            self._actions.clear()
            self._workflows.clear()
            self._approvals.clear()
            self._errors.clear()
            self._response_times.clear()


# Module-level singleton — one collector per worker process
metrics = MetricsCollector()
