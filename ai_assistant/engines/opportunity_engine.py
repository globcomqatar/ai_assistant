"""Opportunity Engine — Phase 3 placeholder."""
from __future__ import annotations

from typing import TYPE_CHECKING

from ai_assistant.engines.base import BaseEngine

if TYPE_CHECKING:
    from ai_assistant.kernel.context_manager import AIContext


class OpportunityEngine(BaseEngine):
    """
    Opportunity prioritisation, lead scoring, and conversion prediction.

    Phase 3 implementation will:
    - Score open quotations and opportunities by conversion probability
    - Prioritise follow-up actions for the Sales Agent
    - Surface cross-sell and upsell signals from transaction history
    - Integrate with the Prediction Engine for win-rate forecasting

    Not yet implemented.
    """

    engine_id = "opportunity_engine"
    name = "Opportunity Engine"
    version = "0.0"
    is_placeholder = True

    def execute(self, context: "AIContext", payload: dict) -> dict:
        raise NotImplementedError(
            "OpportunityEngine is a Phase 3 placeholder and has not been implemented. "
            "Enable the 'opportunity_engine' feature flag once Phase 3 is released."
        )
