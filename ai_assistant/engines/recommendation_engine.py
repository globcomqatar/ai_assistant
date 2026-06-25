"""Recommendation Engine — delegates to core/recommendation_engine.py."""
from __future__ import annotations

from typing import TYPE_CHECKING

from ai_assistant.engines.base import BaseEngine

if TYPE_CHECKING:
    from ai_assistant.kernel.context_manager import AIContext


class RecommendationEngine(BaseEngine):
    """
    Wraps core.RecommendationEngine in the standard BaseEngine interface.
    Produces AI-driven recommendations from BI report analysis.
    """

    engine_id = "recommendation_engine"
    name = "Recommendation Engine"
    version = "1.0"

    def execute(self, context: "AIContext", payload: dict) -> dict:
        from ai_assistant.core.recommendation_engine import RecommendationEngine as CoreEngine

        engine = CoreEngine()
        report_data = payload.get("report_data", {})
        advisory_type = payload.get("advisory_type", "general")

        try:
            result = engine.analyze(report_data, advisory_type=advisory_type)
            return {"status": "success", "data": result}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
