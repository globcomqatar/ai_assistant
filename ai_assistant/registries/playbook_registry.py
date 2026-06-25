"""
Playbook Registry — Phase 3 placeholder.

Playbooks are pre-defined multi-step response patterns for common business
scenarios. Phase 3 (Predictive Intelligence) will populate this registry
with AI-driven response chains triggered by predictive signals and anomaly
detection.

Structure of a playbook entry (future):
    {
        "playbook_id": "overdue_collection",
        "name": "Overdue Collection Playbook",
        "trigger": "overdue_ar_exceeds_threshold",
        "confidence_threshold": 0.70,
        "steps": [...],
    }
"""
from __future__ import annotations

PLAYBOOK_REGISTRY: list[dict] = []


def get_playbook_registry() -> list[dict]:
    """Return all registered playbooks."""
    return list(PLAYBOOK_REGISTRY)


def get_playbook(playbook_id: str) -> dict | None:
    """Return a single playbook by ID, or None if not found."""
    for p in PLAYBOOK_REGISTRY:
        if p.get("playbook_id") == playbook_id:
            return dict(p)
    return None
