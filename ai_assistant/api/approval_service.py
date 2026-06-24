"""Reusable approval service for governed AI actions."""

from __future__ import annotations

from time import perf_counter
from typing import Any

import frappe
from frappe import _

from ai_assistant.api.action_handlers import HANDLERS, parse_payload, related_document, response, text
from ai_assistant.api.action_registry import get_action


APPROVAL_RULES = {
	"safe": {"active": True, "label": "Safe Approval"},
	"manager": {"active": False, "label": "Manager Approval"},
	"finance": {"active": False, "label": "Finance Approval"},
	"multi_level": {"active": False, "label": "Multi-Level Approval"},
	"system": {"active": False, "label": "System Approval"},
}

STATUS_PENDING = "Pending Approval"
STATUS_APPROVED = "Approved"
STATUS_REJECTED = "Rejected"
STATUS_MODIFIED = "Modified"
STATUS_EXECUTED = "Executed"
STATUS_COMPLETED = "Completed"


def require_authenticated() -> None:
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in to use the Approval Center."), frappe.PermissionError)


def standardize_payload(action_id: str, payload: dict, action: dict) -> dict:
	doctype, document_name = related_document(payload)
	title = text(payload.get("title") or payload.get("action") or payload.get("text"), 140)
	description = text(payload.get("description") or payload.get("suggested_next_step"), 1000)
	return {
		**payload,
		"action_id": action_id,
		"title": title,
		"description": description,
		"priority": text(payload.get("priority"), 80),
		"severity": text(payload.get("severity"), 80),
		"confidence": payload.get("confidence") or payload.get("confidence_score"),
		"business_impact": text(payload.get("business_impact") or payload.get("impact") or payload.get("expected_impact"), 1000),
		"estimated_time": text(payload.get("estimated_time") or payload.get("eta"), 80),
		"expected_outcome": text(payload.get("expected_outcome") or payload.get("outcome"), 500),
		"ai_explanation": text(payload.get("ai_explanation") or payload.get("why") or payload.get("reasoning"), 1000),
		"business_reasoning": text(payload.get("business_reasoning") or payload.get("reasoning"), 1000),
		"estimated_impact": text(payload.get("estimated_impact") or payload.get("business_impact") or payload.get("impact"), 1000),
		"owner": text(payload.get("owner") or payload.get("owner_role") or payload.get("assigned_to") or payload.get("user"), 140),
		"doctype": doctype,
		"document_name": document_name,
		"context": payload.get("context") or {},
		"safe_action": bool(action.get("safe_action")),
		"requires_approval": True,
		"approval_rule": "safe",
		"approval_status": payload.get("approval_status") or STATUS_PENDING,
	}


def validate_action(action_id: str, payload: dict) -> dict:
	action = get_action(action_id)
	if not action:
		frappe.throw(_("Unsupported AI action: {0}").format(action_id), frappe.ValidationError)
	if not action.get("safe_action"):
		frappe.throw(_("This action is not marked safe for direct execution."), frappe.PermissionError)
	doctype, _name = related_document(payload)
	supported = action.get("supported_doctypes") or ["*"]
	if doctype and "*" not in supported and doctype not in supported:
		frappe.throw(_("Action {0} does not support {1}.").format(action.get("label"), doctype), frappe.ValidationError)
	return action


def validate_registry_permission(action: dict, payload: dict) -> None:
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


def apply_modifications(payload: dict, modifications: str | dict | None = None, user: str | None = None) -> dict:
	modifications = parse_payload(modifications)
	allowed = {
		"user": "user",
		"assigned_user": "user",
		"assigned_to": "user",
		"priority": "priority",
		"due_date": "due_date",
		"date": "due_date",
		"subject": "title",
		"title": "title",
		"description": "description",
	}
	updated = dict(payload)
	for source, target in allowed.items():
		if source in modifications:
			updated[target] = modifications[source]
	if user:
		updated["user"] = user
	return updated


def create_execution_plan(action_id: str, action_payload=None, modifications=None, user: str | None = None) -> dict:
	require_authenticated()
	payload = apply_modifications(parse_payload(action_payload), modifications, user=user)
	action = validate_action(action_id, payload)
	payload = standardize_payload(action_id, payload, action)
	validate_registry_permission(action, payload)
	doctype, document_name = related_document(payload)
	plan = {
		"success": True,
		"ok": True,
		"action_id": action_id,
		"action": action.get("label") or action_id,
		"description": payload.get("description"),
		"owner": payload.get("user") or payload.get("owner") or payload.get("owner_role"),
		"priority": payload.get("priority"),
		"related_document": " / ".join(x for x in [doctype, document_name] if x),
		"doctype": doctype,
		"document_name": document_name,
		"estimated_time": payload.get("estimated_time"),
		"business_impact": payload.get("business_impact"),
		"confidence": payload.get("confidence"),
		"expected_outcome": payload.get("expected_outcome"),
		"ai_explanation": payload.get("ai_explanation"),
		"business_reasoning": payload.get("business_reasoning"),
		"estimated_impact": payload.get("estimated_impact"),
		"approval_status": STATUS_PENDING,
		"approval_rule": "safe",
		"approval_rule_label": APPROVAL_RULES["safe"]["label"],
		"payload": payload,
		"action_meta": action,
	}
	log_approval("plan", action_id, payload, plan, decision=STATUS_PENDING)
	return plan


def log_approval(event: str, action_id: str, payload: dict, result: dict | None = None,
	decision: str | None = None, execution_time: float = 0, error: str | None = None) -> None:
	doctype, document_name = related_document(payload)
	entry = {
		"timestamp": frappe.utils.now(),
		"user": frappe.session.user,
		"recommendation": payload.get("title") or payload.get("action"),
		"approval_decision": decision,
		"event": event,
		"action": action_id,
		"related_doctype": doctype,
		"related_document": document_name,
		"execution_result": result.get("message") if result else None,
		"success": result.get("success") if result else None,
		"execution_time": round(execution_time, 4),
		"error": error,
	}
	try:
		frappe.logger("ai_assistant.approval_center").info(entry)
	except Exception:
		pass


def reject_action(action_id: str, action_payload=None, reason: str | None = None) -> dict:
	require_authenticated()
	payload = parse_payload(action_payload)
	result = response(action_id, reason or _("AI action rejected."), success=True,
		extra={"approval_status": STATUS_REJECTED, "decision": "reject"})
	log_approval("reject", action_id, payload, result, decision=STATUS_REJECTED)
	return result


def modify_action(action_id: str, action_payload=None, modifications=None, user: str | None = None) -> dict:
	plan = create_execution_plan(action_id, action_payload, modifications=modifications, user=user)
	plan["approval_status"] = STATUS_MODIFIED
	plan["message"] = _("AI action modified. Review the updated execution plan before approving.")
	log_approval("modify", action_id, plan.get("payload") or {}, plan, decision=STATUS_MODIFIED)
	return plan


def execute_approved_action(action_id: str, action_payload=None, modifications=None, user: str | None = None) -> dict:
	require_authenticated()
	start = perf_counter()
	try:
		plan = create_execution_plan(action_id, action_payload, modifications=modifications, user=user)
		payload = plan["payload"]
		action = plan["action_meta"]
		handler = HANDLERS.get(action.get("handler"))
		if not handler:
			frappe.throw(_("No handler configured for action {0}.").format(action_id), frappe.ValidationError)
		log_approval("approve", action_id, payload, plan, decision=STATUS_APPROVED)
		result = handler(payload, action, user=user)
		execution_time = perf_counter() - start
		result.update({
			"approval_status": STATUS_EXECUTED,
			"approval_decision": STATUS_APPROVED,
			"execution_plan": plan,
			"execution_summary": {
				"success": result.get("success"),
				"created_document": result.get("created_document"),
				"assigned_user": payload.get("user"),
				"execution_time": round(execution_time, 4),
				"open_document_route": result.get("document_route") or result.get("route"),
			},
			"execution_time": round(execution_time, 4),
		})
		if result.get("success"):
			result["approval_status"] = STATUS_COMPLETED
		log_approval("execute", action_id, payload, result, decision=STATUS_EXECUTED, execution_time=execution_time)
		return result
	except Exception as exc:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "AI Approval Center Error")
		execution_time = perf_counter() - start
		payload = parse_payload(action_payload)
		message = getattr(exc, "message", None) or str(exc) or _("Approval Center request failed.")
		result = response(action_id, text(message, 500), success=False, execution_time=execution_time,
			extra={"approval_status": STATUS_PENDING})
		log_approval("error", action_id, payload, result, decision="Error", execution_time=execution_time, error=message)
		return result
