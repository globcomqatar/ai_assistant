"""Shared test helpers for AI Assistant governance/RBAC tests."""
from __future__ import annotations

import frappe


def ensure_user(email: str, first_name: str, roles: list[str]) -> str:
    """Create (or reuse) a test user with the given roles. Returns the email."""
    if not frappe.db.exists("User", email):
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": first_name,
            "send_welcome_email": 0,
            "user_type": "System User",
        }).insert(ignore_permissions=True)
        user.add_roles(*roles)
    else:
        user = frappe.get_doc("User", email)
        existing = set(frappe.get_roles(email))
        missing = [r for r in roles if r not in existing]
        if missing:
            user.add_roles(*missing)
    return email
