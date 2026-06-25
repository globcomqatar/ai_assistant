"""
Playbook Registry

Pre-defined multi-step response patterns for common business scenarios.
Phase 3 (Predictive Intelligence) will execute playbooks automatically
when the Prediction or Risk Engine detects a trigger condition.

Each playbook entry is a configuration-only definition — no execution logic.
Execution will be handled by a Playbook Runner in Phase 3.

Structure of a playbook entry:
    {
        "playbook_id":          str   — unique identifier
        "name":                 str   — display name
        "description":          str   — what this playbook does
        "trigger":              str   — signal that activates this playbook
        "confidence_threshold": float — minimum confidence to auto-activate (0.0–1.0)
        "steps":                list  — ordered list of step definitions (Phase 3)
        "is_placeholder":       bool  — True until Phase 3 implementation
    }
"""
from __future__ import annotations

PLAYBOOK_REGISTRY: list[dict] = [
    {
        "playbook_id": "quotation_follow_up",
        "name": "Quotation Follow-Up Playbook",
        "description": (
            "Automatically follow up on open quotations that have not been acknowledged "
            "after a configurable number of days. Escalates to the sales manager if the "
            "customer remains unresponsive."
        ),
        "trigger": "quotation_open_exceeds_followup_days",
        "confidence_threshold": 0.70,
        "steps": [],
        "is_placeholder": True,
    },
    {
        "playbook_id": "collection_recovery",
        "name": "Collection Recovery Playbook",
        "description": (
            "Multi-step recovery sequence for overdue receivables. Sends reminders, "
            "escalates to accounts manager, and optionally triggers a payment plan."
        ),
        "trigger": "overdue_ar_exceeds_threshold",
        "confidence_threshold": 0.75,
        "steps": [],
        "is_placeholder": True,
    },
    {
        "playbook_id": "customer_retention",
        "name": "Customer Retention Playbook",
        "description": (
            "Identifies at-risk customers based on declining order frequency or "
            "payment delays, and triggers a proactive retention outreach sequence."
        ),
        "trigger": "customer_churn_risk_detected",
        "confidence_threshold": 0.65,
        "steps": [],
        "is_placeholder": True,
    },
    {
        "playbook_id": "inventory_review",
        "name": "Inventory Review Playbook",
        "description": (
            "Flags slow-moving stock, near-expiry items, and reorder points. "
            "Raises purchase requests and notifies the warehouse manager."
        ),
        "trigger": "inventory_anomaly_detected",
        "confidence_threshold": 0.70,
        "steps": [],
        "is_placeholder": True,
    },
    {
        "playbook_id": "supplier_follow_up",
        "name": "Supplier Follow-Up Playbook",
        "description": (
            "Monitors open purchase orders past their expected delivery date and "
            "triggers supplier follow-up communications and escalation."
        ),
        "trigger": "purchase_order_overdue",
        "confidence_threshold": 0.80,
        "steps": [],
        "is_placeholder": True,
    },
    {
        "playbook_id": "workshop_reminder",
        "name": "Workshop Reminder Playbook",
        "description": (
            "Sends service due reminders to vehicle owners based on mileage or "
            "time intervals, and follows up on open job cards past SLA."
        ),
        "trigger": "workshop_service_due_or_overdue",
        "confidence_threshold": 0.70,
        "steps": [],
        "is_placeholder": True,
    },
    {
        "playbook_id": "sales_opportunity",
        "name": "Sales Opportunity Playbook",
        "description": (
            "Surfaces high-probability sales opportunities from lead and quotation "
            "data, assigns tasks to the responsible salesperson, and tracks progress."
        ),
        "trigger": "high_score_opportunity_identified",
        "confidence_threshold": 0.65,
        "steps": [],
        "is_placeholder": True,
    },
]


def get_playbook_registry() -> list[dict]:
    """Return all registered playbooks."""
    return list(PLAYBOOK_REGISTRY)


def get_playbook(playbook_id: str) -> dict | None:
    """Return a single playbook by ID, or None if not found."""
    for p in PLAYBOOK_REGISTRY:
        if p.get("playbook_id") == playbook_id:
            return dict(p)
    return None
