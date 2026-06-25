"""
ApprovalService — service layer for governed AI action approvals.

Thin class-based wrapper around api/approval_service.py that provides a
stable interface for the Approval Center. Phase 3 will extend this with
multi-level approval chains and audit trail integration.
"""
from __future__ import annotations


class ApprovalService:
    """Service layer for Approval Center operations."""

    def create_plan(
        self,
        action_id: str,
        payload=None,
        modifications=None,
        user: str | None = None,
    ) -> dict:
        from ai_assistant.api.approval_service import create_execution_plan
        return create_execution_plan(action_id, payload, modifications=modifications, user=user)

    def approve(
        self,
        action_id: str,
        payload=None,
        modifications=None,
        user: str | None = None,
    ) -> dict:
        from ai_assistant.api.approval_service import execute_approved_action
        return execute_approved_action(action_id, payload, modifications=modifications, user=user)

    def reject(
        self,
        action_id: str,
        payload=None,
        reason: str | None = None,
    ) -> dict:
        from ai_assistant.api.approval_service import reject_action
        return reject_action(action_id, payload, reason=reason)

    def modify(
        self,
        action_id: str,
        payload=None,
        modifications=None,
        user: str | None = None,
    ) -> dict:
        from ai_assistant.api.approval_service import modify_action
        return modify_action(action_id, payload, modifications=modifications, user=user)


approval_service = ApprovalService()
