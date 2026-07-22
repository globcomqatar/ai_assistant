"""
executor.py — maps AI intent names to tool functions, executes them, logs usage.

Entry point:  execute_actions(actions, user, prompt, ai_raw_response)
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import now_datetime

from ai_assistant.api.tools import TOOL_REGISTRY
from ai_assistant.api.permission_manager import (
    get_user_roles,
    validate_tool_permission,
)


def _check_budget(user: str, settings) -> tuple[bool, str]:
    """Return (allowed, reason).  Checks monthly budget and per-request limits."""
    if not settings.max_monthly_budget:
        return True, ""

    month_start = frappe.utils.get_first_day(frappe.utils.nowdate())
    used = frappe.db.sql(
        """
        SELECT COALESCE(SUM(cost), 0)
        FROM `tabAI Usage Log`
        WHERE user = %s AND timestamp >= %s AND status = 'Success'
        """,
        (user, month_start),
    )[0][0] or 0.0

    budget = float(settings.max_monthly_budget)

    if used >= budget:
        return False, f"Monthly AI budget of ${budget:.2f} has been exhausted (used ${used:.2f})."

    if used >= budget * 0.8:
        frappe.publish_realtime(
            "ai_budget_warning",
            {"used": used, "budget": budget},
            user=user,
        )

    return True, ""


def _write_log(
    user: str,
    prompt: str,
    response: str,
    tool_used: str,
    tokens: int,
    cost: float,
    status: str,
    blocked_reason: str = "",
    requested_tool: str = "",
    permission_result: str = "N/A",
    user_roles: str = "",
    agent_code: str = "",
    agent_name: str = "",
) -> None:
    try:
        log = frappe.new_doc("AI Usage Log")
        log.user = user
        log.prompt = prompt[:2000]
        log.response = response[:2000]
        log.tool_used = tool_used
        log.tokens_used = tokens
        log.cost = cost
        log.timestamp = now_datetime()
        log.status = status
        log.blocked_reason = blocked_reason
        log.requested_tool = requested_tool
        log.permission_result = permission_result
        log.user_roles = user_roles
        log.agent_code = agent_code
        log.agent_name = agent_name
        log.flags.ignore_permissions = True
        log.insert()
        frappe.db.commit()
    except Exception as exc:
        frappe.log_error(title="AI Usage Log Write Failed", message=str(exc))


def execute_actions(
    actions: list[dict],
    user: str,
    prompt: str,
    ai_raw_response: str,
    agent_code: str = "general",
) -> list[dict]:
    """
    Execute a list of AI-resolved action dicts.

    Returns a list of result dicts (one per action).
    """
    settings = frappe.get_single("AI Settings")

    # Extract metadata injected by router
    meta = {}
    if actions and "_meta" in actions[-1]:
        meta = actions[-1].pop("_meta", {})

    tokens_total = meta.get("tokens", 0)
    cost_total = meta.get("cost", 0.0)

    # Capture user roles once for all log entries in this request
    roles_str = ", ".join(get_user_roles(user))

    # Resolve agent name for logging
    _agent_name = ""
    if agent_code and agent_code != "general":
        try:
            _agent_name = frappe.db.get_value("AI Agent", agent_code, "agent_name") or ""
        except Exception:
            pass

    # Budget check
    allowed, reason = _check_budget(user, settings)
    if not allowed:
        _write_log(user, prompt, ai_raw_response, "", tokens_total, cost_total,
                   "Blocked", reason, user_roles=roles_str,
                   agent_code=agent_code, agent_name=_agent_name)
        return [{"intent": "blocked", "message": reason}]

    if not settings.allow_tool_execution:
        _write_log(user, prompt, ai_raw_response, "", tokens_total, cost_total,
                   "Blocked", "Tool execution disabled in settings.", user_roles=roles_str,
                   agent_code=agent_code, agent_name=_agent_name)
        return [{"intent": "blocked", "message": _("Tool execution is currently disabled by the administrator.")}]

    results: list[dict] = []
    tools_used: list[str] = []
    any_denied = False

    for action in actions:
        intent = action.get("intent", "")
        parameters = action.get("parameters", {})

        # Plain text reply — no permission check needed
        if intent == "reply":
            results.append({"intent": "reply", "message": action.get("message", "")})
            continue

        # ── RBAC: server-side permission check ────────────────────────────────
        try:
            validate_tool_permission(user, intent)
        except frappe.PermissionError as exc:
            any_denied = True
            denied_msg = str(exc)
            results.append({
                "intent": intent,
                "status": "denied",
                "message": denied_msg,
            })
            _write_log(
                user=user,
                prompt=prompt,
                response=ai_raw_response,
                tool_used="",
                tokens=tokens_total,
                cost=cost_total,
                status="Denied",
                blocked_reason=denied_msg,
                requested_tool=intent,
                permission_result="Denied",
                user_roles=roles_str,
                agent_code=agent_code,
                agent_name=_agent_name,
            )
            continue
        # ─────────────────────────────────────────────────────────────────────

        fn = TOOL_REGISTRY.get(intent)
        if not fn:
            results.append({
                "intent": intent,
                "status": "error",
                "message": f"Unknown tool '{intent}'. No action taken.",
            })
            continue

        try:
            result = fn(**parameters)
            result["intent"] = intent
            results.append(result)
            tools_used.append(intent)
        except frappe.ValidationError as exc:
            results.append({"intent": intent, "status": "validation_error", "message": str(exc)})
        except Exception as exc:
            frappe.log_error(title=f"AI Tool Failed: {intent}"[:140], message=str(exc))
            results.append({"intent": intent, "status": "error", "message": f"Tool '{intent}' encountered an error."})

    # Log a summary entry for successful/failed tool calls (denied ones are already logged individually)
    if tools_used or any(r.get("intent") == "reply" for r in results):
        status = "Success"
    elif any_denied:
        status = "Denied"
    else:
        status = "Failed"

    if tools_used or not any_denied:
        _write_log(
            user=user,
            prompt=prompt,
            response=ai_raw_response,
            tool_used=", ".join(tools_used),
            tokens=tokens_total,
            cost=cost_total,
            status=status,
            requested_tool=", ".join(a.get("intent", "") for a in actions if a.get("intent") != "reply"),
            permission_result="Allowed" if tools_used else "N/A",
            user_roles=roles_str,
            agent_code=agent_code,
            agent_name=_agent_name,
        )

    return results
