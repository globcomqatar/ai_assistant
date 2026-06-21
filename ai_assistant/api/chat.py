"""
chat.py — whitelisted Frappe API endpoints for the AI chat UI.
"""

from __future__ import annotations

import json
import frappe
from frappe import _

from ai_assistant.api.router import route
from ai_assistant.api.executor import execute_actions


@frappe.whitelist()
def send_message(message: str, history: str = "[]", current_agent: str = "general") -> dict:
    """
    Process a user message through the AI pipeline.

    Args:
        message:       The user's plain-text message.
        history:       JSON string of previous messages.
        current_agent: Agent code to activate (default "general").
    """
    frappe.only_for("All")

    if not message or not message.strip():
        frappe.throw(_("Message cannot be empty."))
    if len(message) > 4000:
        frappe.throw(_("Message too long. Please keep it under 4 000 characters."))

    # Validate agent access
    agent_code = (current_agent or "general").strip()
    user = frappe.session.user
    if agent_code != "general":
        try:
            from ai_assistant.api.agent_manager import validate_agent_access
            if not validate_agent_access(user, agent_code):
                frappe.throw(_("You do not have access to the '{0}' agent.").format(agent_code))
        except frappe.PermissionError:
            raise
        except Exception:
            agent_code = "general"

    try:
        hist: list[dict] = json.loads(history)
        if not isinstance(hist, list):
            hist = []
    except (json.JSONDecodeError, TypeError):
        hist = []

    hist = hist[-20:]
    messages = [*hist, {"role": "user", "content": message}]

    # 1. Route to AI
    try:
        actions = route(messages=messages, user=user, agent_code=agent_code)
    except Exception as exc:
        err_str = str(exc)
        frappe.log_error(title="AI Routing Failed", message=err_str)
        short = err_str.replace("\n", " ")[:300]
        return {
            "results": [{"intent": "error", "message": f"AI error: {short}"}],
            "ai_raw": "",
            "usage": {},
        }

    ai_raw = json.dumps(actions)

    # 2. Execute tool calls
    results = execute_actions(
        actions=actions,
        user=user,
        prompt=message,
        ai_raw_response=ai_raw,
        agent_code=agent_code,
    )

    if not results:
        results = [{"intent": "reply",
                    "message": _("No response received from AI. Please try again.")}]

    usage: dict = {}
    for action in actions:
        if "_meta" in action:
            usage = action["_meta"]
            break

    return {"results": results, "ai_raw": ai_raw, "usage": usage}


@frappe.whitelist()
def get_agents() -> list[dict]:
    """Return available agents for the current user."""
    from ai_assistant.api.agent_manager import get_available_agents
    return get_available_agents(frappe.session.user)


@frappe.whitelist()
def test_connection() -> dict:
    frappe.only_for("System Manager")
    try:
        from ai_assistant.providers import get_provider
        provider = get_provider()
        resp = provider.chat(
            messages=[{"role": "user", "content": 'Reply with exactly this JSON and nothing else: {"intent":"reply","message":"Connection OK"}'}],
            system_prompt='You are a test assistant. Output only raw JSON, no markdown.',
        )
        return {
            "status": "ok",
            "provider": frappe.get_single("AI Settings").provider,
            "model": resp.model,
            "raw_response": resp.raw_text[:300],
            "tokens": resp.tokens_total,
            "cost_usd": resp.estimated_cost_usd,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@frappe.whitelist()
def get_usage_summary() -> dict:
    user = frappe.session.user
    month_start = frappe.utils.get_first_day(frappe.utils.nowdate())
    row = frappe.db.sql(
        """SELECT COUNT(*) as requests, COALESCE(SUM(tokens_used),0) as tokens,
                  COALESCE(SUM(cost),0) as cost
           FROM `tabAI Usage Log`
           WHERE user=%s AND timestamp>=%s AND status='Success'""",
        (user, month_start), as_dict=True,
    )
    settings = frappe.get_single("AI Settings")
    data = row[0] if row else {"requests": 0, "tokens": 0, "cost": 0}
    data["budget"] = float(settings.max_monthly_budget or 0)
    data["budget_used_pct"] = (
        round(float(data["cost"]) / float(data["budget"]) * 100, 1)
        if data["budget"] else 0
    )
    return data


@frappe.whitelist()
def get_daily_briefing() -> dict:
    frappe.only_for("All")
    try:
        from ai_assistant.api.bi_tools import get_management_summary
        return get_management_summary()
    except Exception as exc:
        frappe.log_error(title="Daily Briefing Failed", message=str(exc))
        return {"status": "error", "message": str(exc)}


@frappe.whitelist()
def get_settings_status() -> dict:
    settings = frappe.get_single("AI Settings")
    has_key = False
    try:
        has_key = bool(settings.get_active_api_key())
    except Exception:
        pass
    return {
        "enabled": bool(settings.enabled),
        "provider": settings.provider,
        "model": settings.get_active_model(),
        "allow_tool_execution": bool(settings.allow_tool_execution),
        "fallback_mode": settings.fallback_mode,
        "has_api_key": has_key,
    }
