"""
permission_manager.py — Server-side RBAC layer for AI Tool execution.

Rules:
- System Manager always gets all enabled tools.
- Every other user gets only tools where their ERPNext roles overlap the
  tool's allowed_roles child table.
- If no AI Tool Permission record exists for a tool it is DENIED (secure default).
- All permission checks happen server-side; the AI never sees tools the user
  cannot use.
"""
from __future__ import annotations
import frappe
from frappe import _

_EXEMPT_INTENTS: frozenset[str] = frozenset({"reply", "blocked", "error"})
_CACHE_KEY = "ai_rbac_permission_map"
_CACHE_TTL = 300  # 5 minutes


# ─── Internal cache helpers ──────────────────────────────────────────────────

def _load_permission_map() -> dict[str, list[str]]:
    """
    Load {tool_name: [allowed_role, ...]} for all enabled tools.
    Cached site-wide; invalidated by AIToolPermission.on_update / after_delete.
    """
    cached = frappe.cache().get_value(_CACHE_KEY)
    if cached:
        return cached

    perms = frappe.get_all(
        "AI Tool Permission",
        filters={"enabled": 1},
        fields=["name", "tool_name"],
    )
    result: dict[str, list[str]] = {}
    for p in perms:
        roles = frappe.get_all(
            "AI Tool Permission Role",
            filters={"parent": p.name, "parenttype": "AI Tool Permission"},
            pluck="role",
        )
        result[p.tool_name] = roles

    frappe.cache().set_value(_CACHE_KEY, result, expires_in_sec=_CACHE_TTL)
    return result


def invalidate_cache() -> None:
    """Call whenever AI Tool Permission records are created, updated, or deleted."""
    frappe.cache().delete_value(_CACHE_KEY)


# ─── Public API ──────────────────────────────────────────────────────────────

def get_user_roles(user: str) -> list[str]:
    """Return ERPNext role names for the given user."""
    return frappe.get_roles(user)


def get_allowed_tools(user: str) -> set[str]:
    """
    Return the set of tool names this user is permitted to call.
    System Manager always receives every enabled tool.
    """
    user_roles = set(get_user_roles(user))
    perm_map = _load_permission_map()

    if "System Manager" in user_roles:
        return set(perm_map.keys())

    allowed: set[str] = set()
    for tool_name, allowed_roles in perm_map.items():
        if user_roles & set(allowed_roles):
            allowed.add(tool_name)
    return allowed


def validate_tool_permission(user: str, tool_name: str) -> None:
    """
    Raise frappe.PermissionError if user is not allowed to call tool_name.
    Exempt intents (reply, error, blocked) are always permitted.
    """
    if tool_name in _EXEMPT_INTENTS:
        return

    if tool_name not in get_allowed_tools(user):
        frappe.throw(
            _("You do not have permission to use the '{0}' tool.").format(tool_name),
            frappe.PermissionError,
        )


def get_permitted_tools_schema(user: str) -> list[dict]:
    """
    Return a TOOLS_SCHEMA filtered to only tools this user may use.
    Injected into the AI system prompt so the AI never proposes unauthorised tools.
    """
    from ai_assistant.api.tools import TOOLS_SCHEMA
    allowed = get_allowed_tools(user)
    return [t for t in TOOLS_SCHEMA if t["name"] in allowed]
