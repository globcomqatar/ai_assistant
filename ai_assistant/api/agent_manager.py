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


@frappe.whitelist()
def get_available_agents(user: str | None = None) -> list[dict]:
    """Return agents available to the current (or given) user, ordered by display_order."""
    user = user or frappe.session.user
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
