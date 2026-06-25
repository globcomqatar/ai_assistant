"""
WorkflowService — service layer for AI Workflow Automation.

Thin class-based wrapper around workflow_engine.py that provides a stable
interface for the Workflow Center. Phase 3 will extend this with playbook
integration and parallel step execution.
"""
from __future__ import annotations


class WorkflowService:
    """Service layer for Workflow Automation operations."""

    def get_workflow_registry(self) -> list[dict]:
        from ai_assistant.registries.workflow_registry import get_workflow_registry
        return get_workflow_registry()

    def get_workflow(self, workflow_id: str) -> dict | None:
        from ai_assistant.registries.workflow_registry import get_workflow
        return get_workflow(workflow_id)

    def build_plan(
        self,
        workflow_id: str | None = None,
        payload=None,
    ) -> dict:
        from ai_assistant.api.workflow_engine import build_workflow_plan
        return build_workflow_plan(workflow_id, payload)

    def execute(
        self,
        workflow_id: str | None = None,
        payload=None,
        approved: bool = False,
        user: str | None = None,
        skip_steps=None,
        retry_from_step: str | None = None,
    ) -> dict:
        from ai_assistant.api.workflow_engine import execute_workflow
        return execute_workflow(
            workflow_id,
            payload,
            approved=approved,
            user=user,
            skip_steps=skip_steps,
            retry_from_step=retry_from_step,
        )

    def infer_workflow(self, payload: dict) -> str:
        from ai_assistant.registries.workflow_templates import infer_workflow_id
        return infer_workflow_id(payload)


workflow_service = WorkflowService()
