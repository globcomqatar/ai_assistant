"""Scheduled background tasks for AI Assistant."""

import frappe


def reset_monthly_usage():
	"""Called monthly by the scheduler — placeholder for future per-month cleanup.

	Log clearing is handled automatically by Frappe's log-clearing job using the
	default_log_clearing_doctypes entry in hooks.py (90-day retention for AI Usage Log).
	This function exists as a hook point for future work such as sending monthly
	usage summary emails or archiving aggregated statistics.
	"""
	frappe.logger("ai_assistant").info("AI Assistant monthly scheduler tick.")
