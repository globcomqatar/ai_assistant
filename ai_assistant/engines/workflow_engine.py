"""Workflow Engine — delegates to services/workflow_service.py."""
from __future__ import annotations

from typing import TYPE_CHECKING

from ai_assistant.engines.base import BaseEngine

if TYPE_CHECKING:
    from ai_assistant.kernel.context_manager import AIContext


class WorkflowEngine(BaseEngine):
    """
    Wraps WorkflowService in the standard BaseEngine interface.
    Handles multi-step automated workflow building and execution.
    """

    engine_id = "workflow_engine"
    name = "Workflow Engine"
    version = "1.0"

    def execute(self, context: "AIContext", payload: dict) -> dict:
        from ai_assistant.services.workflow_service import workflow_service

        workflow_id = payload.get("workflow_id", "")
        parameters = payload.get("parameters", {})

        if not workflow_id:
            workflow_id = workflow_service.infer_workflow(parameters)

        try:
            plan = workflow_service.build_plan(workflow_id, parameters)
            return {"status": "success", "data": plan}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
