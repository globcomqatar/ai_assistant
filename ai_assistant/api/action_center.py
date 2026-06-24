"""Safe Action Center endpoints for Management Intelligence required actions."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _


def _payload(action_payload: str | dict | None) -> dict[str, Any]:
	if isinstance(action_payload, str):
		try:
			action_payload = frappe.parse_json(action_payload)
		except Exception:
			frappe.throw(_("Invalid action payload."), frappe.ValidationError)
	if not isinstance(action_payload, dict):
		return {}
	return action_payload


def _text(value: Any, limit: int = 500) -> str:
	text = str(value or "").strip()
	return text[:limit]


def _safe_error(exc: Exception) -> dict:
	frappe.log_error(frappe.get_traceback(), "AI Action Center Error")
	message = getattr(exc, "message", None) or str(exc) or _("Action Center request failed.")
	return {"ok": False, "message": _text(message, 500)}


def _run_safe(fn):
	try:
		return fn()
	except Exception as exc:
		return _safe_error(exc)


def _require_authenticated() -> None:
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in to use the Action Center."), frappe.PermissionError)


def _audit(action_type: str, payload: dict, task_name: str | None = None) -> None:
	"""Write a minimal server-side audit trail without storing full prompts."""
	try:
		frappe.logger("ai_assistant.action_center").info({
			"user": frappe.session.user,
			"action_type": action_type,
			"related_doctype": _text(payload.get("related_doctype"), 140),
			"related_document": _text(payload.get("related_document"), 140),
			"task_name": task_name,
		})
	except Exception:
		pass


def _priority(value: str | None) -> str:
	priority = str(value or "").lower().strip()
	if priority in {"urgent", "high"}:
		return "High"
	if priority == "low":
		return "Low"
	return "Medium"


def _related_document(payload: dict) -> tuple[str, str]:
	doctype = _text(payload.get("related_doctype") or payload.get("doctype"), 140)
	name = _text(payload.get("related_document") or payload.get("document_name") or payload.get("name"), 140)
	return doctype, name


def _insight_reference_message() -> str:
	return _("This action is based on an AI insight and is not linked to a specific ERPNext document.")


def _task_description(payload: dict, follow_up: bool = False) -> str:
	lines = [
		_text(payload.get("suggested_next_step"), 1000),
		"",
		_("AI Action Center Context"),
		f"- {_('Action')}: {_text(payload.get('action') or payload.get('title') or payload.get('text'), 500)}",
		f"- {_('Priority')}: {_text(payload.get('priority'), 80)}",
		f"- {_('Owner Role')}: {_text(payload.get('owner_role'), 140)}",
	]
	doctype, docname = _related_document(payload)
	if doctype or docname:
		lines.append(f"- {_('Related Document')}: {' / '.join(x for x in [doctype, docname] if x)}")
	if follow_up:
		lines.append(f"- {_('Type')}: {_('Follow-up Task')}")
	return "\n".join(line for line in lines if line is not None).strip()


def _new_task(payload: dict, follow_up: bool = False) -> dict:
	_require_authenticated()
	if not frappe.has_permission("Task", "create"):
		frappe.throw(_("You do not have permission to create Task."), frappe.PermissionError)

	action = _text(payload.get("action") or payload.get("title") or payload.get("text"), 140)
	subject = f"{_('Follow-up')}: {action}" if follow_up else action
	if not subject:
		subject = _("AI Action Follow-up") if follow_up else _("AI Action")

	doc = frappe.get_doc({
		"doctype": "Task",
		"subject": subject[:140],
		"description": _task_description(payload, follow_up=follow_up),
		"priority": _priority(payload.get("priority")),
	})
	doc.insert()
	frappe.db.commit()
	_audit("create_follow_up" if follow_up else "create_task", payload, doc.name)
	return {
		"ok": True,
		"status": "created",
		"task": doc.name,
		"route": ["Form", "Task", doc.name],
		"message": _("Task {0} created successfully.").format(doc.name),
	}


def _document_route(payload: dict) -> dict:
	_require_authenticated()
	doctype, name = _related_document(payload)
	if not doctype or not name:
		return {
			"ok": True,
			"can_open_document": False,
			"message": _insight_reference_message(),
		}
	if not frappe.db.exists("DocType", doctype) or not frappe.db.exists(doctype, name):
		return {
			"ok": True,
			"can_open_document": False,
			"related_doctype": doctype,
			"related_document": name,
			"message": _insight_reference_message(),
		}
	doc = frappe.get_doc(doctype, name)
	if not frappe.has_permission(doctype, ptype="read", doc=doc):
		frappe.throw(_("You do not have permission to read the related document."), frappe.PermissionError)
	_audit("open_document", payload)
	return {
		"ok": True,
		"can_open_document": True,
		"related_doctype": doctype,
		"related_document": name,
		"route": ["Form", doctype, name],
	}


def _todo_description(payload: dict) -> str:
	lines = [
		_text(payload.get("suggested_next_step"), 1000) or _text(payload.get("action") or payload.get("title") or payload.get("text"), 500),
		"",
		_("AI Action Center Assignment"),
		f"- {_('Action')}: {_text(payload.get('action') or payload.get('title') or payload.get('text'), 500)}",
		f"- {_('Priority')}: {_text(payload.get('priority'), 80)}",
		f"- {_('Owner Role')}: {_text(payload.get('owner_role'), 140)}",
	]
	doctype, docname = _related_document(payload)
	if doctype or docname:
		lines.append(f"- {_('Reference')}: {' / '.join(x for x in [doctype, docname] if x)}")
	return "\n".join(line for line in lines if line is not None).strip()


def _new_assignment(payload: dict, user: str | None = None) -> dict:
	_require_authenticated()
	allocated_to = _text(user or payload.get("user") or payload.get("allocated_to") or payload.get("assigned_to"), 140)
	if not allocated_to:
		frappe.throw(_("Please select a user to assign this action."), frappe.ValidationError)
	if not frappe.db.exists("User", allocated_to):
		frappe.throw(_("Selected user does not exist."), frappe.ValidationError)
	if frappe.db.get_value("User", allocated_to, "enabled") == 0:
		frappe.throw(_("Selected user is disabled."), frappe.ValidationError)
	if not frappe.has_permission("ToDo", "create"):
		frappe.throw(_("You do not have permission to create assignments."), frappe.PermissionError)

	doctype, name = _related_document(payload)
	has_valid_reference = bool(doctype and name and frappe.db.exists("DocType", doctype) and frappe.db.exists(doctype, name))
	doc = frappe.get_doc({
		"doctype": "ToDo",
		"allocated_to": allocated_to,
		"description": _todo_description(payload),
		"priority": _priority(payload.get("priority")),
		"status": "Open",
	})
	if has_valid_reference:
		doc.reference_type = doctype
		doc.reference_name = name
	doc.insert()
	frappe.db.commit()
	_audit("assign_owner", payload, doc.name)
	return {
		"ok": True,
		"status": "assigned",
		"todo": doc.name,
		"message": _("Action assigned to {0}.").format(allocated_to),
	}


@frappe.whitelist()
def ping():
	return {"ok": True, "user": frappe.session.user}


@frappe.whitelist()
def create_action_task(action_payload=None):
	"""Create a permission-aware ERPNext Task from a required action."""
	return _run_safe(lambda: _new_task(_payload(action_payload), follow_up=False))


@frappe.whitelist()
def create_follow_up(action_payload=None):
	"""Create a follow-up Task. No CRM Activity creation in this phase."""
	return _run_safe(lambda: _new_task(_payload(action_payload), follow_up=True))


@frappe.whitelist()
def assign_action_owner(action_payload=None, user=None):
	"""Create a safe ToDo assignment for a selected user."""
	return _run_safe(lambda: _new_assignment(_payload(action_payload), user=user))


@frappe.whitelist()
def draft_action_email(action_payload=None):
	"""Generate an email draft only. This endpoint never sends email."""
	def _draft():
		_require_authenticated()
		payload = _payload(action_payload)
		action = _text(payload.get("action") or payload.get("title") or payload.get("text"), 140) or _("Action Follow-up")
		next_step = _text(payload.get("suggested_next_step"), 1000)
		impact = _text(payload.get("impact") or payload.get("business_impact") or payload.get("expected_impact"), 1000)
		doctype, docname = _related_document(payload)
		body_lines = [
			_("Hello,"),
			"",
			_("I am following up on this management action: {0}").format(action),
		]
		if next_step:
			body_lines.extend(["", _("Suggested next step:"), next_step])
		if impact:
			body_lines.extend(["", _("Business context:"), impact])
		if doctype or docname:
			body_lines.extend(["", _("Reference:"), " / ".join(x for x in [doctype, docname] if x)])
		body_lines.extend(["", _("Regards,")])
		_audit("draft_email", payload)
		return {
			"ok": True,
			"to": "",
			"subject": _("Follow-up: {0}").format(action),
			"body": "\n".join(body_lines),
		}

	return _run_safe(_draft)


@frappe.whitelist()
def validate_related_document(action_payload=None):
	"""Return a Form route only for valid ERPNext documents."""
	return _run_safe(lambda: _document_route(_payload(action_payload)))


@frappe.whitelist()
def get_action_center_options(action_payload=None):
	"""Backward-compatible alias for older frontend code."""
	return validate_related_document(action_payload)
