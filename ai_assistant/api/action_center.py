"""Whitelisted AI Action Framework executor endpoints."""

from __future__ import annotations

from time import perf_counter
from typing import Any

import frappe
from frappe import _

from ai_assistant.api.action_handlers import HANDLERS, parse_payload, related_document, response
from ai_assistant.api.action_registry import get_action, get_action_registry as registry_entries
from ai_assistant.api.approval_service import (
	create_execution_plan,
	execute_approved_action,
	modify_action,
	reject_action,
)
from ai_assistant.api.workflow_engine import build_workflow_plan, execute_workflow as run_workflow
from ai_assistant.api.workflow_registry import get_workflow_registry as registry_workflows


def _text(value: Any, limit: int = 500) -> str:
	return str(value or "").strip()[:limit]


def _require_authenticated() -> None:
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in to use the Action Center."), frappe.PermissionError)


def _standardize_payload(action_id: str, payload: dict, action: dict) -> dict:
	doctype, document_name = related_document(payload)
	title = _text(payload.get("title") or payload.get("action") or payload.get("text"), 140)
	description = _text(payload.get("description") or payload.get("suggested_next_step"), 1000)
	return {
		**payload,
		"action_id": action_id,
		"title": title,
		"description": description,
		"priority": _text(payload.get("priority"), 80),
		"severity": _text(payload.get("severity"), 80),
		"confidence": payload.get("confidence") or payload.get("confidence_score"),
		"business_impact": _text(payload.get("business_impact") or payload.get("impact") or payload.get("expected_impact"), 1000),
		"estimated_time": _text(payload.get("estimated_time") or payload.get("eta"), 80),
		"doctype": doctype,
		"document_name": document_name,
		"context": payload.get("context") or {},
		"safe_action": bool(action.get("safe_action")),
		"requires_approval": bool(action.get("requires_approval")),
	}


def _validate_action(action_id: str, payload: dict) -> dict:
	action = get_action(action_id)
	if not action:
		frappe.throw(_("Unsupported AI action: {0}").format(action_id), frappe.ValidationError)
	if action.get("requires_approval"):
		frappe.throw(_("This action requires approval and cannot be executed directly yet."), frappe.PermissionError)
	if not action.get("safe_action"):
		frappe.throw(_("This action is not marked safe for direct execution."), frappe.PermissionError)

	doctype, _name = related_document(payload)
	supported = action.get("supported_doctypes") or ["*"]
	if doctype and "*" not in supported and doctype not in supported:
		frappe.throw(_("Action {0} does not support {1}.").format(action.get("label"), doctype), frappe.ValidationError)
	return action


def _validate_registry_permission(action: dict, payload: dict) -> None:
	required = action.get("required_permission")
	if not required:
		return
	ptype = required.get("ptype") or "read"
	doctype = required.get("doctype")
	if doctype:
		if not frappe.has_permission(doctype, ptype=ptype):
			frappe.throw(_("You do not have permission to {0} {1}.").format(ptype, doctype), frappe.PermissionError)
		return
	if ptype == "read" and action.get("action_id") != "open_document":
		related_doctype, related_name = related_document(payload)
		if related_doctype and related_name and frappe.db.exists("DocType", related_doctype) and frappe.db.exists(related_doctype, related_name):
			doc = frappe.get_doc(related_doctype, related_name)
			if not frappe.has_permission(related_doctype, ptype="read", doc=doc):
				frappe.throw(_("You do not have permission to read the related document."), frappe.PermissionError)


def _log_action(action_id: str, payload: dict, result: dict, execution_time: float, error: str | None = None) -> None:
	doctype, document_name = related_document(payload)
	entry = {
		"timestamp": frappe.utils.now(),
		"user": frappe.session.user,
		"action": action_id,
		"related_doctype": doctype,
		"related_document": document_name,
		"result": "success" if result.get("success") else "failed",
		"message": result.get("message"),
		"execution_time": round(execution_time, 4),
		"error": error,
	}
	try:
		frappe.logger("ai_assistant.action_framework").info(entry)
	except Exception:
		pass


def _safe_error(action_id: str, payload: dict, exc: Exception, execution_time: float) -> dict:
	frappe.db.rollback()
	frappe.log_error(frappe.get_traceback(), "AI Action Framework Error")
	message = getattr(exc, "message", None) or str(exc) or _("Action Center request failed.")
	result = response(action_id, _text(message, 500), success=False, execution_time=execution_time)
	_log_action(action_id, payload, result, execution_time, error=message)
	return result


def _execute(action_id: str, action_payload=None, approved: bool = False, **kwargs) -> dict:
	_require_authenticated()
	if not approved:
		plan = create_execution_plan(action_id, action_payload, user=kwargs.get("user"))
		plan.update({
			"success": False,
			"ok": False,
			"message": _("Approval is required before executing this AI action."),
			"approval_required": True,
		})
		return plan
	payload = parse_payload(action_payload)
	start = perf_counter()
	try:
		action = _validate_action(action_id, payload)
		payload = _standardize_payload(action_id, payload, action)
		_validate_registry_permission(action, payload)
		handler = HANDLERS.get(action.get("handler"))
		if not handler:
			frappe.throw(_("No handler configured for action {0}.").format(action_id), frappe.ValidationError)
		result = handler(payload, action, **kwargs)
		execution_time = perf_counter() - start
		result["execution_time"] = round(execution_time, 4)
		_log_action(action_id, payload, result, execution_time)
		return result
	except Exception as exc:
		return _safe_error(action_id, payload, exc, perf_counter() - start)


@frappe.whitelist()
def ping():
	return {"ok": True, "user": frappe.session.user}


@frappe.whitelist()
def get_action_registry():
	"""Return safe frontend metadata for supported AI actions."""
	_require_authenticated()
	return registry_entries()


@frappe.whitelist()
def get_workflow_registry():
	"""Return safe frontend metadata for supported AI workflows."""
	_require_authenticated()
	return registry_workflows()


@frappe.whitelist()
def execute_action(action_id=None, action_payload=None, user=None):
	"""Execute a registered safe AI action through the central executor."""
	return _execute(_text(action_id, 80), action_payload, user=user)


@frappe.whitelist()
def get_execution_plan(action_id=None, action_payload=None, modifications=None, user=None):
	"""Build an execution plan for review before approval."""
	return create_execution_plan(_text(action_id, 80), action_payload, modifications=modifications, user=user)


@frappe.whitelist()
def approve_action(action_id=None, action_payload=None, modifications=None, user=None):
	"""Approve and execute a safe AI action."""
	return execute_approved_action(_text(action_id, 80), action_payload, modifications=modifications, user=user)


@frappe.whitelist()
def reject_action_request(action_id=None, action_payload=None, reason=None):
	"""Reject an AI action recommendation."""
	return reject_action(_text(action_id, 80), action_payload, reason=reason)


@frappe.whitelist()
def modify_action_request(action_id=None, action_payload=None, modifications=None, user=None):
	"""Return a modified execution plan for review."""
	return modify_action(_text(action_id, 80), action_payload, modifications=modifications, user=user)


@frappe.whitelist()
def get_workflow_plan(workflow_id=None, recommendation_payload=None):
	"""Build a workflow execution plan from an AI recommendation."""
	return build_workflow_plan(_text(workflow_id, 120) or None, recommendation_payload)


@frappe.whitelist()
def approve_workflow(workflow_id=None, recommendation_payload=None, user=None, skip_steps=None, retry_from_step=None):
	"""Approve and execute a safe AI workflow sequentially."""
	if isinstance(skip_steps, str):
		skip_steps = frappe.parse_json(skip_steps) or []
	return run_workflow(
		_text(workflow_id, 120) or None,
		recommendation_payload,
		approved=True,
		user=user,
		skip_steps=skip_steps,
		retry_from_step=_text(retry_from_step, 120) or None,
	)


@frappe.whitelist()
def execute_workflow(workflow_id=None, recommendation_payload=None, user=None):
	"""Return approval-required workflow plan for backward compatible callers."""
	return run_workflow(_text(workflow_id, 120) or None, recommendation_payload, approved=False, user=user)


@frappe.whitelist()
def create_action_task(action_payload=None):
	"""Backward-compatible endpoint for Create Task."""
	return _execute("create_task", action_payload)


@frappe.whitelist()
def create_follow_up(action_payload=None):
	"""Backward-compatible endpoint for Follow-up."""
	return _execute("follow_up", action_payload)


@frappe.whitelist()
def assign_action_owner(action_payload=None, user=None):
	"""Backward-compatible endpoint for Assign."""
	return _execute("assign_user", action_payload, user=user)


@frappe.whitelist()
def draft_action_email(action_payload=None):
	"""Backward-compatible endpoint for Draft Email."""
	return _execute("draft_email", action_payload)


@frappe.whitelist()
def validate_related_document(action_payload=None):
	"""Backward-compatible endpoint for Open Document validation."""
	return _execute("open_document", action_payload)


@frappe.whitelist()
def get_action_center_options(action_payload=None):
	"""Backward-compatible alias for older frontend code."""
	return validate_related_document(action_payload)
