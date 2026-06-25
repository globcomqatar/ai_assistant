"""
AI Engine Registry

Centralized registry for all AI engines — both Phase 2 (active) and
Phase 3 (placeholder). Engines register metadata at module import time;
the registry exposes lookup, availability checks, and listing.

Phase 3 engines are pre-registered as placeholders so the system is
aware of them and can surface their availability status to administrators.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EngineRegistration:
    """Metadata record for one AI engine in the registry."""
    engine_id: str
    name: str
    description: str
    version: str = "1.0"
    is_available: bool = True
    is_placeholder: bool = False
    engine_class: type | None = None  # optional reference to the engine class


class EngineRegistry:
    """Manages registration and lookup of all AI engines."""

    def __init__(self) -> None:
        self._engines: dict[str, EngineRegistration] = {}

    def register(self, registration: EngineRegistration) -> None:
        """Register an engine, replacing any existing entry for the same engine_id."""
        self._engines[registration.engine_id] = registration

    def get(self, engine_id: str) -> EngineRegistration | None:
        """Return the registration for an engine, or None."""
        return self._engines.get(engine_id)

    def is_registered(self, engine_id: str) -> bool:
        return engine_id in self._engines

    def is_available(self, engine_id: str) -> bool:
        reg = self._engines.get(engine_id)
        return reg is not None and reg.is_available and not reg.is_placeholder

    def list_available(self) -> list[EngineRegistration]:
        """Return Phase 2 engines that are active and ready to use."""
        return [e for e in self._engines.values() if e.is_available and not e.is_placeholder]

    def list_placeholders(self) -> list[EngineRegistration]:
        """Return Phase 3 engines registered as placeholders."""
        return [e for e in self._engines.values() if e.is_placeholder]

    def list_all(self) -> list[EngineRegistration]:
        return list(self._engines.values())

    def summary(self) -> dict:
        return {
            "total": len(self._engines),
            "available": len(self.list_available()),
            "placeholders": len(self.list_placeholders()),
        }


# ── Module-level singleton ─────────────────────────────────────────────────────

engine_registry = EngineRegistry()

# Phase 2 engines (available, fully implemented)
_PHASE2_ENGINES = [
    ("report_engine",         "Report Engine",         "Business intelligence reports and executive dashboards."),
    ("recommendation_engine", "Recommendation Engine", "AI-driven recommendations from BI report analysis."),
    ("action_engine",         "Action Engine",         "AI-suggested actions for documents and workflows."),
    ("approval_engine",       "Approval Engine",       "Multi-level approval plan creation and execution."),
    ("workflow_engine",       "Workflow Engine",       "Multi-step automated workflow building and execution."),
]

for _eid, _name, _desc in _PHASE2_ENGINES:
    engine_registry.register(EngineRegistration(
        engine_id=_eid,
        name=_name,
        description=_desc,
        is_available=True,
        is_placeholder=False,
    ))

# Phase 3 engine placeholders (registered but not yet implemented)
_PHASE3_ENGINES = [
    ("prediction_engine",  "Prediction Engine",  "Time-series forecasting and demand anomaly detection."),
    ("risk_engine",        "Risk Engine",         "Business risk identification, scoring, and early warning."),
    ("opportunity_engine", "Opportunity Engine",  "Opportunity prioritisation and lead scoring."),
    ("learning_engine",    "Learning Engine",     "Continuous learning from user feedback and outcomes."),
    ("morning_brief",      "Morning Brief",       "Daily executive priorities, alerts, and recommended actions."),
    ("insight_engine",     "Insight Engine",      "Cross-domain pattern recognition and insight surfacing."),
]

for _eid, _name, _desc in _PHASE3_ENGINES:
    engine_registry.register(EngineRegistration(
        engine_id=_eid,
        name=_name,
        description=_desc,
        is_available=False,
        is_placeholder=True,
    ))
