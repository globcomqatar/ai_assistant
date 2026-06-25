"""Security helpers for AI Assistant API endpoints and tools."""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _


MANAGEMENT_ROLES: frozenset[str] = frozenset({
	"System Manager",
	"Accounts Manager",
	"Sales Manager",
	"Stock Manager",
	"CEO",
	"Management",
	"Management User",
})

HIGH_RISK_WRITE_TOOLS: frozenset[str] = frozenset({
	"create_sales_invoice",
	"record_payment",
	"create_journal_entry",
	"generate_payment_from_invoice",
	"create_purchase_invoice",
	"create_stock_entry",
	"create_employee",
	"create_leave_application",
	"create_expense_claim",
})


def user_roles(user: str | None = None) -> set[str]:
	return set(frappe.get_roles(user or frappe.session.user))


def is_system_manager(user: str | None = None) -> bool:
	return "System Manager" in user_roles(user)


def has_any_role(allowed_roles: set[str] | frozenset[str], user: str | None = None) -> bool:
	return bool(user_roles(user) & set(allowed_roles))


def require_any_role(allowed_roles: set[str] | frozenset[str], message: str | None = None) -> None:
	if has_any_role(allowed_roles):
		return
	frappe.throw(
		message or _("You do not have permission to access this AI Assistant resource."),
		frappe.PermissionError,
	)


def require_management_access() -> None:
	require_any_role(
		MANAGEMENT_ROLES,
		_("Management intelligence is restricted to management roles."),
	)


def require_doctype_permission(doctype: str, ptype: str = "read", doc: Any | None = None) -> None:
	if not frappe.has_permission(doctype, ptype=ptype, doc=doc):
		frappe.throw(
			_("You do not have {0} permission for {1}.").format(ptype, doctype),
			frappe.PermissionError,
		)


def insert_with_permission(doc) -> None:
	require_doctype_permission(doc.doctype, "create", doc)
	doc.check_permission("create")
	doc.insert()


def save_with_permission(doc) -> None:
	require_doctype_permission(doc.doctype, "write", doc)
	doc.check_permission("write")
	doc.save()


def is_confirmed_action(action: dict) -> bool:
	params = action.get("parameters") or {}
	return bool(
		action.get("confirmed")
		or action.get("confirm")
		or params.get("confirmed")
		or params.get("confirm")
		or params.get("_confirmed")
	)


def sanitize_parameters(parameters: dict | None) -> dict:
	if not isinstance(parameters, dict):
		return {}

	blocked_fragments = ("password", "secret", "token", "api_key", "apikey", "authorization")
	safe: dict[str, Any] = {}
	for key, value in parameters.items():
		if key in {"confirmed", "confirm", "_confirmed"}:
			continue
		if any(fragment in key.lower() for fragment in blocked_fragments):
			safe[key] = "***"
			continue
		try:
			json.dumps(value, default=str)
			safe[key] = value
		except TypeError:
			safe[key] = str(value)
	return safe


def confirmation_required_response(intent: str, parameters: dict | None) -> dict:
	safe_parameters = sanitize_parameters(parameters)
	return {
		"intent": intent,
		"status": "confirmation_required",
		"confirmation_required": True,
		"tool": intent,
		"summary": _("Please confirm before AI Assistant executes this high-risk action."),
		"sanitized_parameters": safe_parameters,
	}
