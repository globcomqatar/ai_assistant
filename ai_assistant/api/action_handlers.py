"""Handlers and helpers for the AI Action Framework."""

from __future__ import annotations

from datetime import datetime
from time import perf_counter
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, now_datetime


NO_LINKED_DOCUMENT_MESSAGE = _("This recommendation is based on AI analysis and is not linked to a specific ERPNext document.")


def text(value: Any, limit: int = 500) -> str:
	return str(value or "").strip()[:limit]


def parse_payload(action_payload: str | dict | None) -> dict[str, Any]:
	if isinstance(action_payload, str):
		try:
			action_payload = frappe.parse_json(action_payload)
		except Exception:
			frappe.throw(_("Invalid action payload."), frappe.ValidationError)
	if not isinstance(action_payload, dict):
		return {}
	return action_payload


def priority(value: str | None) -> str:
	value = str(value or "").lower().strip()
	if value in {"urgent", "high"}:
		return "High"
	if value == "low":
		return "Low"
	return "Medium"


def related_document(payload: dict) -> tuple[str, str]:
	doctype = text(payload.get("doctype") or payload.get("related_doctype"), 140)
	name = text(payload.get("document_name") or payload.get("related_document") or payload.get("name"), 140)
	return doctype, name


def valid_related_document(payload: dict) -> tuple[str, str]:
	doctype, name = related_document(payload)
	if doctype and name and frappe.db.exists("DocType", doctype) and frappe.db.exists(doctype, name):
		return doctype, name
	return "", ""


def recommendation_title(payload: dict, fallback: str = "AI Recommendation") -> str:
	return text(payload.get("title") or payload.get("action") or payload.get("text") or fallback, 140)


def recommendation_description(payload: dict, follow_up: bool = False) -> str:
	lines = [
		text(payload.get("description") or payload.get("suggested_next_step"), 1000),
		"",
		_("AI Action Framework Context"),
		f"- {_('Title')}: {recommendation_title(payload)}",
		f"- {_('Priority')}: {text(payload.get('priority'), 80)}",
		f"- {_('Severity')}: {text(payload.get('severity'), 80)}",
		f"- {_('Confidence')}: {text(payload.get('confidence'), 80)}",
		f"- {_('Estimated Time')}: {text(payload.get('estimated_time'), 80)}",
		f"- {_('Business Impact')}: {text(payload.get('business_impact') or payload.get('impact'), 500)}",
		f"- {_('Owner Role')}: {text(payload.get('owner_role'), 140)}",
	]
	doctype, docname = related_document(payload)
	if doctype or docname:
		lines.append(f"- {_('Reference')}: {' / '.join(x for x in [doctype, docname] if x)}")
	if follow_up:
		lines.append(f"- {_('Type')}: {_('Follow-up Task')}")
	return "\n".join(line for line in lines if line is not None).strip()


def validate_permission(doctype: str, ptype: str, doc=None) -> None:
	if not frappe.has_permission(doctype, ptype=ptype, doc=doc):
		frappe.throw(_("You do not have permission to {0} {1}.").format(ptype, doctype), frappe.PermissionError)


def validate_user(user: str | None) -> str:
	user = text(user, 140)
	if not user:
		frappe.throw(_("Please select a user before assigning this action."), frappe.ValidationError)
	if not frappe.db.exists("User", user):
		frappe.throw(_("Selected user does not exist."), frappe.ValidationError)
	if frappe.db.get_value("User", user, "enabled") == 0:
		frappe.throw(_("Selected user is disabled."), frappe.ValidationError)
	return user


def response(action_id: str, message: str, *, success: bool = True, created_document: dict | None = None,
	document_route: list | None = None, warnings: list[str] | None = None, execution_time: float = 0,
	extra: dict | None = None) -> dict:
	result = {
		"success": success,
		"ok": success,
		"message": message,
		"action_id": action_id,
		"created_document": created_document,
		"document_route": document_route,
		"warnings": warnings or [],
		"execution_time": round(execution_time, 4),
	}
	if document_route:
		result["route"] = document_route
	if extra:
		result.update(extra)
	return result


def create_task(payload: dict, action: dict, **kwargs) -> dict:
	validate_permission("Task", "create")
	doc = frappe.get_doc({
		"doctype": "Task",
		"subject": recommendation_title(payload, _("AI Action"))[:140],
		"description": recommendation_description(payload),
		"priority": priority(payload.get("priority")),
	})
	doc.insert()
	frappe.db.commit()
	route = ["Form", "Task", doc.name]
	return response(action["action_id"], _("Task {0} created successfully.").format(doc.name),
		created_document={"doctype": "Task", "name": doc.name}, document_route=route,
		extra={"status": "created", "task": doc.name})


def follow_up(payload: dict, action: dict, **kwargs) -> dict:
	validate_permission("Task", "create")
	title = recommendation_title(payload, _("AI Action"))
	doc = frappe.get_doc({
		"doctype": "Task",
		"subject": f"{_('Follow-up')}: {title}"[:140],
		"description": recommendation_description(payload, follow_up=True),
		"priority": priority(payload.get("priority")),
	})
	doc.insert()
	frappe.db.commit()
	route = ["Form", "Task", doc.name]
	return response(action["action_id"], _("Task {0} created successfully.").format(doc.name),
		created_document={"doctype": "Task", "name": doc.name}, document_route=route,
		extra={"status": "created", "task": doc.name})


def assign_user(payload: dict, action: dict, user: str | None = None, **kwargs) -> dict:
	user = validate_user(user or payload.get("user") or payload.get("allocated_to") or payload.get("assigned_to"))
	validate_permission("ToDo", "create")
	doctype, name = valid_related_document(payload)
	doc = frappe.get_doc({
		"doctype": "ToDo",
		"allocated_to": user,
		"description": recommendation_description(payload),
		"priority": priority(payload.get("priority")),
		"status": "Open",
	})
	if doctype and name:
		doc.reference_type = doctype
		doc.reference_name = name
	doc.insert()
	frappe.db.commit()
	return response(action["action_id"], _("Action assigned to {0}.").format(user),
		created_document={"doctype": "ToDo", "name": doc.name},
		extra={"status": "assigned", "todo": doc.name})


def draft_email(payload: dict, action: dict, **kwargs) -> dict:
	title = recommendation_title(payload, _("Action Follow-up"))
	body_lines = [
		_("Hello,"),
		"",
		_("I am following up on this management action: {0}").format(title),
	]
	description = text(payload.get("description") or payload.get("suggested_next_step"), 1000)
	impact = text(payload.get("business_impact") or payload.get("impact") or payload.get("expected_impact"), 1000)
	doctype, docname = related_document(payload)
	if description:
		body_lines.extend(["", _("Suggested next step:"), description])
	if impact:
		body_lines.extend(["", _("Business context:"), impact])
	if doctype or docname:
		body_lines.extend(["", _("Reference:"), " / ".join(x for x in [doctype, docname] if x)])
	body_lines.extend(["", _("Regards,")])
	return response(action["action_id"], _("Draft email generated."),
		extra={"to": "", "subject": _("Follow-up: {0}").format(title), "body": "\n".join(body_lines)})


def open_document(payload: dict, action: dict, **kwargs) -> dict:
	doctype, name = related_document(payload)
	if not doctype or not name or not frappe.db.exists("DocType", doctype) or not frappe.db.exists(doctype, name):
		return response(action["action_id"], NO_LINKED_DOCUMENT_MESSAGE,
			warnings=[NO_LINKED_DOCUMENT_MESSAGE],
			extra={"can_open_document": False, "related_doctype": doctype, "related_document": name})
	doc = frappe.get_doc(doctype, name)
	if not frappe.has_permission(doctype, ptype="read", doc=doc):
		return response(action["action_id"], _("You do not have permission to read the related document."),
			warnings=[_("Permission denied.")],
			extra={"can_open_document": False, "related_doctype": doctype, "related_document": name})
	route = ["Form", doctype, name]
	return response(action["action_id"], _("Opening {0} {1}.").format(doctype, name),
		document_route=route, extra={"can_open_document": True, "related_doctype": doctype, "related_document": name})


def calendar_event(payload: dict, action: dict, **kwargs) -> dict:
	validate_permission("Event", "create")
	starts_on = payload.get("starts_on") or payload.get("event_date") or add_days(now_datetime(), 1)
	if isinstance(starts_on, datetime):
		starts_on = starts_on.strftime("%Y-%m-%d %H:%M:%S")
	doc = frappe.get_doc({
		"doctype": "Event",
		"subject": recommendation_title(payload, _("AI Recommendation"))[:140],
		"description": recommendation_description(payload),
		"starts_on": starts_on,
		"event_type": "Private",
	})
	doc.insert()
	frappe.db.commit()
	route = ["Form", "Event", doc.name]
	return response(action["action_id"], _("Calendar event {0} created.").format(doc.name),
		created_document={"doctype": "Event", "name": doc.name}, document_route=route)


def notify_user(payload: dict, action: dict, user: str | None = None, **kwargs) -> dict:
	user = validate_user(user or payload.get("user"))
	validate_permission("Notification Log", "create")
	doc = frappe.get_doc({
		"doctype": "Notification Log",
		"subject": recommendation_title(payload, _("AI Recommendation"))[:140],
		"email_content": recommendation_description(payload),
		"for_user": user,
		"type": "Alert",
	})
	doc.insert()
	frappe.db.commit()
	return response(action["action_id"], _("Notification created for {0}.").format(user),
		created_document={"doctype": "Notification Log", "name": doc.name})


def add_comment(payload: dict, action: dict, **kwargs) -> dict:
	validate_permission("Comment", "create")
	doctype, name = valid_related_document(payload)
	if not doctype or not name:
		return response(action["action_id"], NO_LINKED_DOCUMENT_MESSAGE, warnings=[NO_LINKED_DOCUMENT_MESSAGE])
	doc = frappe.get_doc({
		"doctype": "Comment",
		"comment_type": "Comment",
		"reference_doctype": doctype,
		"reference_name": name,
		"content": recommendation_description(payload),
	})
	doc.insert()
	frappe.db.commit()
	return response(action["action_id"], _("Comment added to {0} {1}.").format(doctype, name),
		created_document={"doctype": "Comment", "name": doc.name})


def reminder(payload: dict, action: dict, **kwargs) -> dict:
	validate_permission("ToDo", "create")
	doctype, name = valid_related_document(payload)
	doc = frappe.get_doc({
		"doctype": "ToDo",
		"allocated_to": frappe.session.user,
		"description": recommendation_description(payload),
		"priority": priority(payload.get("priority")),
		"status": "Open",
		"date": payload.get("reminder_date") or add_days(now_datetime(), 1).date(),
	})
	if doctype and name:
		doc.reference_type = doctype
		doc.reference_name = name
	doc.insert()
	frappe.db.commit()
	return response(action["action_id"], _("Reminder created."),
		created_document={"doctype": "ToDo", "name": doc.name},
		extra={"todo": doc.name})


def activity_timeline(payload: dict, action: dict, **kwargs) -> dict:
	validate_permission("Comment", "create")
	doctype, name = valid_related_document(payload)
	if not doctype or not name:
		return response(action["action_id"], NO_LINKED_DOCUMENT_MESSAGE, warnings=[NO_LINKED_DOCUMENT_MESSAGE])
	doc = frappe.get_doc({
		"doctype": "Comment",
		"comment_type": "Info",
		"reference_doctype": doctype,
		"reference_name": name,
		"content": recommendation_description(payload),
	})
	doc.insert()
	frappe.db.commit()
	return response(action["action_id"], _("Timeline entry added to {0} {1}.").format(doctype, name),
		created_document={"doctype": "Comment", "name": doc.name})


HANDLERS = {
	"create_task": create_task,
	"follow_up": follow_up,
	"assign_user": assign_user,
	"draft_email": draft_email,
	"open_document": open_document,
	"calendar_event": calendar_event,
	"notify_user": notify_user,
	"add_comment": add_comment,
	"reminder": reminder,
	"activity_timeline": activity_timeline,
}


def time_call(fn, *args, **kwargs) -> tuple[dict, float]:
	start = perf_counter()
	result = fn(*args, **kwargs)
	return result, perf_counter() - start
