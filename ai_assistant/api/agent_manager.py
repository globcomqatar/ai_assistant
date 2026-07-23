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


def _safe_general_code() -> str:
    """Return the correct agent_code for the 'general' fallback.

    This must ALWAYS resolve to the literal 'general' agent — never to
    whichever agent happens to have default_agent=1. That flag selects the
    System Manager's preferred specialist default (e.g. 'supervisor', per
    _ensure_single_default_agent()'s preference order) and is unrelated to
    the non-System-Manager safety net. Conflating the two previously made
    every non-SM chat request resolve to 'supervisor' and then get rejected
    by validate_agent_switch, breaking the assistant for every regular user.

    Falls back to the hardcoded string so the system never breaks even if
    the AI Agent table is empty or misconfigured."""
    code = frappe.db.get_value("AI Agent", {"name": "general", "enabled": 1}, "agent_code")
    if code:
        return code
    return "general"


def resolve_active_agent(user: str, requested_agent: str | None = None) -> str:
    """
    PATCH 1: Resolve which agent a request should run under.

    No requested agent -> the literal 'general' agent, NEVER
    get_default_agent_code() (whichever agent has default_agent=1, e.g.
    'supervisor'). That flag is the System Manager's preferred specialist
    default and is unrelated to this fallback; conflating the two previously
    made every request with no requested_agent resolve to 'supervisor' and
    then get rejected by validate_agent_switch, breaking chat for every
    non-System-Manager user (see _safe_general_code()).

    A requested agent is passed through as-is, for every user — access is
    enforced by validate_agent_switch() right after this, based on each
    AI Agent's own allowed_roles (e.g. Sales User -> 'sales' agent), not by
    blanket-blocking every non-System-Manager from switching at all.
    """
    requested_agent = (requested_agent or "").strip()
    if not requested_agent:
        return _safe_general_code()
    return requested_agent


def validate_agent_switch(user: str, agent: str) -> None:
    """
    PATCH 2: Raise PermissionError if `user`'s roles don't grant access to
    `agent`, per validate_agent_access() (System Manager and 'general' always
    pass; anyone else needs a role overlap with that AI Agent's allowed_roles).
    Called server-side on every request — the real access boundary, so a
    Sales User can reach the Sales Agent but not the Accounts or Operations
    Agent, regardless of what the client sends.
    """
    if not validate_agent_access(user, agent):
        frappe.throw(
            _("You do not have permission to use the '{0}' agent.").format(agent),
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
    PATCH 4: Defense-in-depth re-check. By the time chat.py calls this,
    session_agent already passed validate_agent_switch — but roles (or the
    AI Agent's allowed_roles) can change between requests, so re-validate
    here too and fall back to 'general' rather than trust a stale value.
    """
    if validate_agent_access(user, session_agent):
        return session_agent
    return _safe_general_code()


@frappe.whitelist()
def get_available_agents(user: str | None = None) -> list[dict]:
    """
    Return agents available to the current (or given) user, ordered by
    display_order, filtered through the same validate_agent_access() check
    used to enforce switching. System Manager passes for every enabled
    agent; everyone else only sees 'general' plus agents whose allowed_roles
    overlap their own roles — e.g. a Sales User sees General + Sales Agent,
    not Accounts/Operations/Supervisor.
    """
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
