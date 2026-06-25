"""
KPI Registry

Central registry for all business KPI definitions used by the Predictive
Intelligence engine. Phase 3 will drive anomaly detection, proactive alerting,
and the Morning Brief from entries in this registry.

Each KPI entry is a configuration-only definition. Calculation logic will be
implemented in Phase 3 via the Prediction Engine and dedicated KPI calculators.

Structure of a KPI entry:
    {
        "kpi_id":              str   — unique identifier
        "name":                str   — display name
        "description":         str   — business meaning
        "unit":                str   — currency, %, count, days
        "source_doctype":      str   — primary ERPNext DocType
        "aggregation":         str   — sum, avg, count, ratio
        "threshold_warning":   float — % of target triggering a warning (0.0–1.0)
        "threshold_critical":  float — % of target triggering a critical alert
        "is_placeholder":      bool  — True until Phase 3 calculation engine
    }
"""
from __future__ import annotations

KPI_REGISTRY: list[dict] = [
    {
        "kpi_id": "monthly_revenue",
        "name": "Monthly Revenue",
        "description": "Total invoiced revenue for the current calendar month.",
        "unit": "QAR",
        "source_doctype": "Sales Invoice",
        "aggregation": "sum",
        "threshold_warning": 0.80,
        "threshold_critical": 0.60,
        "is_placeholder": True,
    },
    {
        "kpi_id": "gross_margin",
        "name": "Gross Margin",
        "description": "Gross profit as a percentage of revenue for the current period.",
        "unit": "%",
        "source_doctype": "Sales Invoice",
        "aggregation": "ratio",
        "threshold_warning": 0.85,
        "threshold_critical": 0.70,
        "is_placeholder": True,
    },
    {
        "kpi_id": "cash_flow",
        "name": "Net Cash Flow",
        "description": "Net cash inflows minus outflows for the current month.",
        "unit": "QAR",
        "source_doctype": "Payment Entry",
        "aggregation": "sum",
        "threshold_warning": 0.75,
        "threshold_critical": 0.50,
        "is_placeholder": True,
    },
    {
        "kpi_id": "overdue_collections",
        "name": "Overdue Receivables",
        "description": "Total outstanding receivables past their due date.",
        "unit": "QAR",
        "source_doctype": "Sales Invoice",
        "aggregation": "sum",
        "threshold_warning": 0.15,   # warning when >15% of revenue is overdue
        "threshold_critical": 0.30,
        "is_placeholder": True,
    },
    {
        "kpi_id": "pipeline_value",
        "name": "Sales Pipeline Value",
        "description": "Total value of open quotations and opportunities in the pipeline.",
        "unit": "QAR",
        "source_doctype": "Quotation",
        "aggregation": "sum",
        "threshold_warning": 0.70,
        "threshold_critical": 0.50,
        "is_placeholder": True,
    },
    {
        "kpi_id": "inventory_turnover",
        "name": "Inventory Turnover",
        "description": "Number of times inventory is sold and replaced in a period.",
        "unit": "ratio",
        "source_doctype": "Stock Entry",
        "aggregation": "ratio",
        "threshold_warning": 0.80,
        "threshold_critical": 0.60,
        "is_placeholder": True,
    },
    {
        "kpi_id": "workshop_utilisation",
        "name": "Workshop Bay Utilisation",
        "description": "Percentage of available workshop capacity currently utilised.",
        "unit": "%",
        "source_doctype": "Maintenance Visit",
        "aggregation": "ratio",
        "threshold_warning": 0.60,   # warning when <60% utilised
        "threshold_critical": 0.40,
        "is_placeholder": True,
    },
    {
        "kpi_id": "customer_satisfaction",
        "name": "Customer Satisfaction Score",
        "description": "Average satisfaction rating from post-service feedback.",
        "unit": "score",
        "source_doctype": "Customer Feedback",
        "aggregation": "avg",
        "threshold_warning": 0.75,
        "threshold_critical": 0.60,
        "is_placeholder": True,
    },
    {
        "kpi_id": "revenue_growth",
        "name": "Revenue Growth Rate",
        "description": "Month-over-month revenue growth percentage.",
        "unit": "%",
        "source_doctype": "Sales Invoice",
        "aggregation": "ratio",
        "threshold_warning": 0.0,    # warning when growth turns negative
        "threshold_critical": -0.10,
        "is_placeholder": True,
    },
    {
        "kpi_id": "forecast_accuracy",
        "name": "Revenue Forecast Accuracy",
        "description": "Accuracy of the Prediction Engine revenue forecast vs. actual. (Phase 3)",
        "unit": "%",
        "source_doctype": "AI Usage Log",
        "aggregation": "ratio",
        "threshold_warning": 0.85,
        "threshold_critical": 0.70,
        "is_placeholder": True,
    },
]


def get_kpi_registry() -> list[dict]:
    """Return all registered KPI definitions."""
    return list(KPI_REGISTRY)


def get_kpi(kpi_id: str) -> dict | None:
    """Return a single KPI definition by ID, or None if not found."""
    for kpi in KPI_REGISTRY:
        if kpi.get("kpi_id") == kpi_id:
            return dict(kpi)
    return None
