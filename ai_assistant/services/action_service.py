"""
ActionService — service layer for the AI Action Framework.

Thin class-based wrapper around action_center.py that provides a stable
API for Phase 3 composability (playbook-driven actions, batch execution).
"""
from __future__ import annotations


class ActionService:
    """Service layer for AI Action Framework operations."""

    def get_action_registry(self) -> list[dict]:
        from ai_assistant.registries.action_registry import get_action_registry
        return get_action_registry()

    def get_action(self, action_id: str) -> dict | None:
        from ai_assistant.registries.action_registry import get_action
        return get_action(action_id)

    def get_execution_plan(
        self,
        action_id: str,
        payload=None,
        modifications=None,
        user: str | None = None,
    ) -> dict:
        from ai_assistant.api.approval_service import create_execution_plan
        return create_execution_plan(action_id, payload, modifications=modifications, user=user)

    def approve_and_execute(
        self,
        action_id: str,
        payload=None,
        modifications=None,
        user: str | None = None,
    ) -> dict:
        from ai_assistant.api.approval_service import execute_approved_action
        return execute_approved_action(action_id, payload, modifications=modifications, user=user)

    def reject(self, action_id: str, payload=None, reason: str | None = None) -> dict:
        from ai_assistant.api.approval_service import reject_action
        return reject_action(action_id, payload, reason=reason)


action_service = ActionService()
