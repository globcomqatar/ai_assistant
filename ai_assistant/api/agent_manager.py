"""
agent_manager.py — Centralized AI Agent management service.

Loads agent definitions from the AI Agent DocType, merges with RBAC,
and provides the router with agent-specific prompts / tools / KPIs.
Cache TTL: 5 min site-wide per agent.
"""
from __future__ import annotations
import frappe
from frappe import _

_CACHE_PREFIX = "ai_agent:"
_CACHE_TTL    = 300


# ── Internal helpers ──────────────────────────────────────────────────────────

def _doc_to_dict(doc) -> dict:
    return {
        "agent_code":    doc.agent_code,
        "agent_name":    doc.agent_name,
        "description":   doc.description   or "",
        "icon":          doc.icon          or "🤖",
        "color":         doc.color         or "#2563EB",
        "system_prompt": doc.system_prompt or "",
        "model_override":doc.model_override or "",
        "temperature":   float(doc.temperature or 0.7),
        "max_tokens":    int(doc.max_tokens or 0),
        "tools":         [r.tool_name for r in (doc.tools or []) if r.enabled],
        "kpis":          [
            {"name": r.kpi_name, "description": r.description or "",
             "weight": float(r.weight or 1.0)}
            for r in (doc.kpis or []) if r.enabled
        ],
        "allowed_roles": [r.role for r in (doc.allowed_roles or [])],
        "default_agent": bool(doc.default_agent),
        "display_order": int(doc.display_order or 99),
    }


# ── Public API ────────────────────────────────────────────────────────────────

def load_agent(agent_code: str) -> dict:
    """Return full agent config dict (Redis-cached 5 min)."""
    key = f"{_CACHE_PREFIX}{agent_code}"
    cached = frappe.cache().get_value(key)
    if cached:
        return cached
    if not frappe.db.exists("AI Agent", agent_code):
        frappe.throw(_("AI Agent '{0}' not found.").format(agent_code))
    doc = frappe.get_doc("AI Agent", agent_code)
    if not doc.enabled:
        frappe.throw(_("AI Agent '{0}' is disabled.").format(agent_code))
    data = _doc_to_dict(doc)
    frappe.cache().set_value(key, data, expires_in_sec=_CACHE_TTL)
    return data


def get_agent_prompt(agent_code: str) -> str:
    if not agent_code or agent_code == "general":
        return ""
    try:
        return load_agent(agent_code)["system_prompt"]
    except Exception:
        return ""


def get_agent_tools(agent_code: str) -> list[str]:
    """Returns list of tool names; empty list means 'use all RBAC-allowed tools'."""
    if not agent_code or agent_code == "general":
        return []
    try:
        return load_agent(agent_code)["tools"]
    except Exception:
        return []


def get_agent_kpis(agent_code: str) -> list[dict]:
    if not agent_code or agent_code == "general":
        return []
    try:
        return load_agent(agent_code)["kpis"]
    except Exception:
        return []


def validate_agent_access(user: str, agent_code: str) -> bool:
    """True if user can use this agent. System Manager always passes."""
    if not agent_code or agent_code == "general":
        return True
    try:
        agent = load_agent(agent_code)
    except Exception:
        return False
    allowed_roles = agent.get("allowed_roles", [])
    if not allowed_roles:
        return True
    user_roles = set(frappe.get_roles(user))
    return "System Manager" in user_roles or bool(user_roles & set(allowed_roles))


# ── Agent Governance (Patches 1–4) ───────────────────────────────────────────

def _is_system_manager(user: str) -> bool:
    return "System Manager" in frappe.get_roles(user)


def resolve_active_agent(user: str, requested_agent: str | None = None) -> str:
    """
    PATCH 1: Strict agent resolution.
    Non-System Manager users are always forced to 'general'.
    System Manager can use any valid agent.
    """
    if not _is_system_manager(user):
        return "general"
    if not requested_agent:
        return "general"
    return requested_agent


def validate_agent_switch(user: str, agent: str) -> None:
    """
    PATCH 2: Raise PermissionError if a non-System Manager tries to switch
    away from the general agent. Called server-side on every request.
    """
    if not _is_system_manager(user) and agent != "general":
        frappe.throw(
            _("Agent switching is not allowed for this user."),
            frappe.PermissionError,
        )


def check_system_manager_access(user: str) -> None:
    """
    PATCH 3: Gate for AI Agent configuration endpoints.
    Raises PermissionError for any non-System Manager.
    """
    if not _is_system_manager(user):
        frappe.throw(
            _("Only System Manager can access AI Agent configuration."),
            frappe.PermissionError,
        )


def get_session_agent(user: str, session_agent: str) -> str:
    """
    PATCH 4: Session cannot override agent for non-System Manager.
    Always returns 'general' for regular users regardless of stored session value.
    """
    if not _is_system_manager(user):
        return "general"
    return session_agent


@frappe.whitelist()
def get_available_agents(user: str | None = None) -> list[dict]:
    """
    Return agents available to the current (or given) user, ordered by display_order.
    Non-System Manager users receive only the general agent — agent switching is locked.
    """
    user = user or frappe.session.user
    # PATCH 2 enforcement: non-SM only sees general agent
    if not _is_system_manager(user):
        row = frappe.db.get_value(
            "AI Agent", "general",
            ["agent_code", "agent_name", "description", "icon", "color", "default_agent"],
            as_dict=True,
        ) or {}
        return [{
            "agent_code":    row.get("agent_code", "general"),
            "agent_name":    row.get("agent_name", "General ERP Assistant"),
            "description":   row.get("description", ""),
            "icon":          row.get("icon", "🤖"),
            "color":         row.get("color", "#2563EB"),
            "default_agent": True,
        }]
    rows = frappe.get_all(
        "AI Agent",
        filters={"enabled": 1},
        fields=["agent_code","agent_name","description","icon","color",
                "display_order","default_agent"],
        order_by="display_order asc, agent_name asc",
    )
    result = []
    for r in rows:
        if validate_agent_access(user, r.agent_code):
            result.append({
                "agent_code":    r.agent_code,
                "agent_name":    r.agent_name,
                "description":   r.description or "",
                "icon":          r.icon or "🤖",
                "color":         r.color or "#2563EB",
                "default_agent": bool(r.default_agent),
            })
    return result


def get_default_agent_code() -> str:
    default = frappe.db.get_value("AI Agent",
        {"enabled": 1, "default_agent": 1}, "agent_code")
    return default or "general"


def invalidate_agent_cache(agent_code: str | None = None) -> None:
    if agent_code:
        frappe.cache().delete_value(f"{_CACHE_PREFIX}{agent_code}")
    else:
        frappe.cache().delete_keys(f"{_CACHE_PREFIX}*")


def build_agent_system_prompt(agent_code: str, user: str, base_prompt: str) -> str:
    """
    Merge agent system prompt with the base prompt.
    Agent prompt is prepended; base prompt follows as operational rules.
    """
    agent_prompt = get_agent_prompt(agent_code)
    if not agent_prompt:
        return base_prompt
    kpis = get_agent_kpis(agent_code)
    kpi_section = ""
    if kpis:
        kpi_lines = "\n".join(f"- {k['name']}" + (f": {k['description']}" if k['description'] else "")
                               for k in kpis)
        kpi_section = f"\n\nKey Performance Indicators you monitor:\n{kpi_lines}"
    return f"{agent_prompt}{kpi_section}\n\n---\n\n{base_prompt}"


def filter_tools_for_agent(agent_code: str, rbac_filtered_schema: list[dict]) -> list[dict]:
    """
    Intersect agent tools with RBAC-allowed tools.
    If agent has no tool list (empty = general), return all RBAC-allowed tools.
    """
    agent_tools = get_agent_tools(agent_code)
    if not agent_tools:
        return rbac_filtered_schema
    allowed_set = set(agent_tools)
    return [t for t in rbac_filtered_schema if t["name"] in allowed_set]
