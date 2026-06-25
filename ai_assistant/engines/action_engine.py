"""Action Engine — delegates to services/action_service.py."""
from __future__ import annotations

from typing import TYPE_CHECKING

from ai_assistant.engines.base import BaseEngine

if TYPE_CHECKING:
    from ai_assistant.kernel.context_manager import AIContext


class ActionEngine(BaseEngine):
    """
    Wraps ActionService in the standard BaseEngine interface.
    Handles AI-suggested action generation, approval planning, and execution.
    """

    engine_id = "action_engine"
    name = "Action Engine"
    version = "1.0"

    def execute(self, context: "AIContext", payload: dict) -> dict:
        from ai_assistant.services.action_service import action_service

        action_id = payload.get("action_id", "")
        parameters = payload.get("parameters", {})

        if not action_id:
            return {"status": "error", "message": "action_id is required"}

        try:
            plan = action_service.get_execution_plan(action_id, parameters)
            return {"status": "success", "data": plan}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
