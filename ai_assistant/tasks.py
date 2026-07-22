"""Scheduled background tasks for AI Assistant."""

import frappe


def reset_monthly_usage():
	"""Called monthly by the scheduler — clears old usage logs beyond retention."""
	frappe.logger("ai_assistant").info("AI Assistant monthly usage reset triggered.")
	# Actual log clearing is handled by default_log_clearing_doctypes in hooks.py (90 days).
	# This hook can send summary emails or perform additional cleanup in the future.
