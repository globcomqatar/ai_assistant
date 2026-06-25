"""Whitelisted health check endpoints — System Manager only."""

from __future__ import annotations

import frappe
from frappe import _


@frappe.whitelist()
def get_health_status(include_provider: bool = False) -> dict:
    """
    Return platform health status for all critical components.

    System Manager only. Set include_provider=1 to test live AI connectivity
    (makes an outbound HTTP call — use sparingly).
    """
    from ai_assistant.security.security import is_system_manager
    if not is_system_manager():
        frappe.throw(_("Health check requires System Manager role."), frappe.PermissionError)

    from ai_assistant.services.health_service import HealthService
    return HealthService().check_all(include_provider=frappe.utils.cint(include_provider) == 1)


@frappe.whitelist()
def get_metrics_snapshot() -> dict:
    """
    Return current in-process metrics snapshot.

    System Manager only. Metrics are per-worker and reset on restart.
    """
    from ai_assistant.security.security import is_system_manager
    if not is_system_manager():
        frappe.throw(_("Metrics require System Manager role."), frappe.PermissionError)

    from ai_assistant.core.metrics import metrics
    return metrics.snapshot()
