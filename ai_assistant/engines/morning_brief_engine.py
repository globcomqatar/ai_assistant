"""Morning Brief Engine — Phase 3 placeholder."""
from __future__ import annotations

from typing import TYPE_CHECKING

from ai_assistant.engines.base import BaseEngine

if TYPE_CHECKING:
    from ai_assistant.kernel.context_manager import AIContext


class MorningBriefEngine(BaseEngine):
    """
    Daily executive priorities, alerts, and recommended actions.

    Phase 3 implementation will:
    - Aggregate KPI anomalies and risk signals at the start of each business day
    - Produce a personalized priority list per executive user
    - Trigger playbooks for overdue collections, critical opportunities, and stock alerts
    - Deliver the brief via AI Chat and optionally via email/WhatsApp

    Not yet implemented.
    """

    engine_id = "morning_brief"
    name = "Morning Brief"
    version = "0.0"
    is_placeholder = True

    def execute(self, context: "AIContext", payload: dict) -> dict:
        raise NotImplementedError(
            "MorningBriefEngine is a Phase 3 placeholder and has not been implemented. "
            "Enable the 'morning_brief' feature flag once Phase 3 is released."
        )
