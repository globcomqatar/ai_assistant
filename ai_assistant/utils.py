"""Shared utility helpers for AI Assistant."""

from __future__ import annotations
import frappe


def is_ai_enabled() -> bool:
	try:
		settings = frappe.get_single("AI Settings")
		return bool(settings.enabled)
	except Exception:
		return False


def get_user_monthly_cost(user: str) -> float:
	month_start = frappe.utils.get_first_day(frappe.utils.nowdate())
	result = frappe.db.sql(
		"SELECT COALESCE(SUM(cost), 0) FROM `tabAI Usage Log` WHERE user=%s AND timestamp>=%s AND status='Success'",
		(user, month_start),
	)
	return float(result[0][0]) if result else 0.0
