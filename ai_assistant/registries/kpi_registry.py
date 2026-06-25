"""
KPI Registry — Phase 3 placeholder.

Central registry for all business KPI definitions used by the Predictive
Intelligence engine. Phase 3 will drive the anomaly detection dashboard
and proactive alerting from entries in this registry.

Structure of a KPI entry (future):
    {
        "kpi_id": "monthly_revenue",
        "name": "Monthly Revenue",
        "unit": "QAR",
        "source": "Sales Invoice",
        "aggregation": "sum",
        "threshold_warning": 0.80,
        "threshold_critical": 0.60,
    }
"""
from __future__ import annotations

KPI_REGISTRY: list[dict] = []


def get_kpi_registry() -> list[dict]:
    """Return all registered KPI definitions."""
    return list(KPI_REGISTRY)


def get_kpi(kpi_id: str) -> dict | None:
    """Return a single KPI definition by ID, or None if not found."""
    for kpi in KPI_REGISTRY:
        if kpi.get("kpi_id") == kpi_id:
            return dict(kpi)
    return None
