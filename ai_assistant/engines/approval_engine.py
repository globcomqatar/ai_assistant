"""Approval Engine — delegates to services/approval_service.py."""
from __future__ import annotations

from typing import TYPE_CHECKING

from ai_assistant.engines.base import BaseEngine

if TYPE_CHECKING:
    from ai_assistant.kernel.context_manager import AIContext


class ApprovalEngine(BaseEngine):
    """
    Wraps ApprovalService in the standard BaseEngine interface.
    Handles multi-level approval plan creation and decision tracking.
    """

    engine_id = "approval_engine"
    name = "Approval Engine"
    version = "1.0"

    def execute(self, context: "AIContext", payload: dict) -> dict:
        from ai_assistant.services.approval_service import approval_service

        operation = payload.get("operation", "create")
        data = payload.get("data", {})

        try:
            if operation == "create":
                result = approval_service.create_plan(data)
            elif operation == "approve":
                result = approval_service.approve(data)
            elif operation == "reject":
                result = approval_service.reject(data)
            elif operation == "modify":
                result = approval_service.modify(data)
            else:
                return {"status": "error", "message": f"Unknown operation: {operation}"}
            return {"status": "success", "data": result}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
