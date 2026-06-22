"""
chat.py — whitelisted Frappe API endpoints for the AI chat UI.
"""

from __future__ import annotations

import json
import frappe
from frappe import _

from ai_assistant.api.router import route
from ai_assistant.api.executor import execute_actions


# Intent names of tools that return a `metrics` key and receive AI interpretation.
# Add a tool's intent here whenever you enrich it with metrics/chart — no other changes needed.
ANALYTICAL_TOOLS: frozenset[str] = frozenset({
    "get_overdue_invoices",
    "get_monthly_sales_trend",
    "analyze_business",
    "get_management_summary",
    "get_sales_summary",
    "get_sales_analysis",
    "get_payables_analysis",
})


# All four keys the interpreter must return — strict subset check (Fix 4)
_INTERP_KEYS: frozenset[str] = frozenset({"findings", "risks", "recommendations", "required_actions"})


def _log_interpret(
    user: str, intent: str, prompt: str, raw: str,
    tokens: int, cost: float, status: str,
) -> None:
    """Write one AI Usage Log row for an interpreter call. Fails silently."""
    try:
        from ai_assistant.api.executor import _write_log
        _write_log(
            user=user,
            prompt=prompt[:500],
            response=raw[:500],
            tool_used=f"_interpret:{intent}",
            tokens=tokens,
            cost=cost,
            status=status,
            permission_result="N/A",
        )
    except Exception as _exc:
        frappe.log_error(title="Interpreter log write failed", message=str(_exc))


def _interpret_analytics(tool_result: dict, user_message: str, user: str) -> dict | None:
    """
    Send computed metrics to the AI and get back four structured sections.

    Returns {"findings":[...], "risks":[...], "recommendations":[...],
             "required_actions":[...]} or None on any failure.
    Always safe to call — logs errors and returns None without raising.
    """
    if not tool_result.get("metrics"):
        return None
    try:
        from ai_assistant.providers import get_provider
        from ai_assistant.api.router import _extract_json

        _intent = tool_result.get("intent", "unknown")
        metrics = tool_result["metrics"]
        aging = tool_result.get("aging_buckets") or {}
        top_cx = tool_result.get("top_customers") or []

        # Build compact, number-rich context — raw invoice rows excluded
        ctx = ["### Metrics"]
        for k, v in metrics.items():
            ctx.append(f"- {k}: {v}")
        if aging:
            ctx.append("### Aging Buckets (QAR)")
            for bucket, amt in aging.items():
                ctx.append(f"- {bucket} days past due: {amt:,.0f}")
        if top_cx:
            ctx.append("### Top Customers by Outstanding")
            for cx in top_cx[:5]:
                ctx.append(f"- {cx['customer']}: QAR {cx['outstanding']:,.0f} ({cx['pct_of_total']}%)")

        system_prompt = (
            "You are a financial analyst for a Qatar-based ERP system. "
            "Interpret the supplied pre-computed metrics and respond with ONLY valid JSON — "
            "no markdown, no explanation, no extra text.\n\n"
            'Output: {"findings":["..."],"risks":["..."],'
            '"recommendations":["..."],"required_actions":["..."]}\n\n'
            "Rules: 2-4 items per array. Every figure you quote must come from the "
            "supplied numbers — never invent values. Currency is QAR. "
            "findings=factual observations; risks=business risks; "
            "recommendations=strategic improvements; required_actions=immediate operational steps."
        )
        user_content = f"User question: {user_message}\n\nComputed data:\n" + "\n".join(ctx)

        provider = get_provider()
        resp = provider.chat(
            messages=[{"role": "user", "content": user_content}],
            system_prompt=system_prompt,
        )

        _tokens = getattr(resp, "tokens_total", 0) or 0
        _cost   = getattr(resp, "estimated_cost_usd", 0.0) or 0.0

        # Parse JSON — log and return None on decode failure
        try:
            clean = _extract_json(resp.raw_text.strip())
            parsed = json.loads(clean)
        except (json.JSONDecodeError, ValueError) as _je:
            frappe.log_error(title="Analytics interpreter failed", message=f"JSONDecodeError: {_je}")
            _log_interpret(user, _intent, user_content, resp.raw_text, _tokens, _cost, "Error")
            return None

        # Fix 4: strict key presence check
        missing = _INTERP_KEYS - parsed.keys()
        if missing:
            frappe.log_error(
                title="Interpreter response missing keys",
                message=f"Missing: {missing}. Raw (first 300): {resp.raw_text[:300]}",
            )
            _log_interpret(user, _intent, user_content, resp.raw_text, _tokens, _cost, "Error")
            return None

        # Fix 4: strict type check — all four values must be lists
        wrong_type = [k for k in _INTERP_KEYS if not isinstance(parsed.get(k), list)]
        if wrong_type:
            frappe.log_error(
                title="Interpreter response wrong types",
                message=f"Keys not lists: {wrong_type}. Raw (first 300): {resp.raw_text[:300]}",
            )
            _log_interpret(user, _intent, user_content, resp.raw_text, _tokens, _cost, "Error")
            return None

        # Strip empty / whitespace-only items from each list
        result = {k: [str(i) for i in parsed[k] if str(i).strip()] for k in _INTERP_KEYS}

        # If every list is empty after stripping, skip the analysis section entirely
        if not any(result.values()):
            _log_interpret(user, _intent, user_content, resp.raw_text, _tokens, _cost, "Success")
            return None

        _log_interpret(user, _intent, user_content, resp.raw_text, _tokens, _cost, "Success")
        return result

    except Exception as exc:
        frappe.log_error(title="Analytics interpreter failed", message=f"{type(exc).__name__}: {exc}")
        return None


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

    user = frappe.session.user

    # PATCH 5: Strict governance pipeline
    # Step 1 + 2: Resolve agent — non-SM is always forced to "general"
    from ai_assistant.api.agent_manager import (
        resolve_active_agent,
        validate_agent_switch,
        get_session_agent,
    )
    agent_code = resolve_active_agent(user, (current_agent or "general").strip())

    # Step 3: Validate switch — blocks any non-SM attempt to use a non-general agent
    validate_agent_switch(user, agent_code)

    # Step 4: Session safety — strips any session-level override for non-SM
    agent_code = get_session_agent(user, agent_code)

    # Step 5: Auto-routing — System Manager + Auto mode only.
    # Non-SM users are already locked to "general" by Steps 1–4; this block
    # never fires for them.
    routing_info: dict | None = None
    from ai_assistant.api.agent_manager import _is_system_manager
    if _is_system_manager(user):
        try:
            from ai_assistant.api import supervisor as _supervisor
            if _supervisor.is_auto_routing_enabled():
                routing_result = _supervisor.route_to_agent(message, user)
                agent_code = routing_result["agent_code"]
                routing_info = routing_result
        except Exception as _exc:
            frappe.log_error(title="Auto-routing Step 5 failed", message=str(_exc))

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

    # Step 6: For each successful analytical result, add AI-interpreted sections.
    # One extra model call per analytical report; fails silently — never breaks data/chart.
    for _result in results:
        if (
            _result.get("intent") in ANALYTICAL_TOOLS
            and _result.get("status", "ok") == "ok"
            and _result.get("metrics")          # only enriched tools have this key
        ):
            _result["analysis"] = _interpret_analytics(_result, message, user)

    if not results:
        results = [{"intent": "reply",
                    "message": _("No response received from AI. Please try again.")}]

    usage: dict = {}
    for action in actions:
        if "_meta" in action:
            usage = action["_meta"]
            break

    return {"results": results, "ai_raw": ai_raw, "usage": usage, "routing": routing_info}


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
