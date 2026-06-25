"""
chat.py — whitelisted Frappe API endpoints for the AI chat UI.
"""

from __future__ import annotations

import json
import frappe
from frappe import _

from ai_assistant.api.router import route
from ai_assistant.api.executor import execute_actions
from ai_assistant.api.security import is_system_manager, require_management_access


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
    # Composite cross-module tools
    "get_so_invoice_gap",
    "get_sales_pipeline_status",
    "get_customer_360",
    "get_po_receipt_gap",
    "get_monthly_pl_bridge",
    "get_sales_order_dashboard",
})


# Advisory schema returned by the analytics interpreter. The four legacy list
# keys remain supported so older report payloads still render safely.
_LEGACY_INTERP_KEYS: frozenset[str] = frozenset({"findings", "risks", "recommendations", "required_actions"})
_ADVISORY_INTERP_KEYS: frozenset[str] = frozenset({
    "executive_summary",
    "findings",
    "root_causes",
    "risks",
    "opportunities",
    "recommendations",
    "required_actions",
    "expected_business_impact",
})
_SEVERITIES: frozenset[str] = frozenset({"low", "medium", "high", "critical"})
_PRIORITIES: frozenset[str] = frozenset({"low", "medium", "high", "urgent"})


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


def normalize_score(value) -> int:
    """Normalize model scores from 0-1, 1-10, or 0-100 into a 0-100 integer."""
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0
    if 0 < score <= 1:
        score *= 100
    elif 1 <= score <= 10:
        score *= 10
    return max(0, min(100, int(round(score))))


def _as_list(value) -> list:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _clean_text(value, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _normalize_risks(value) -> list[dict]:
    risks = []
    for item in _as_list(value):
        if isinstance(item, dict):
            severity = str(item.get("severity") or "medium").lower().strip()
            risks.append({
                "title": _clean_text(item.get("title") or item.get("risk") or item.get("message"), "Business risk"),
                "severity": severity if severity in _SEVERITIES else "medium",
                "risk_score": normalize_score(item.get("risk_score") or item.get("score")),
                "business_impact": _clean_text(item.get("business_impact") or item.get("impact"), "insufficient data"),
            })
        else:
            risks.append({
                "title": _clean_text(item, "Business risk"),
                "severity": "medium",
                "risk_score": 50,
                "business_impact": "insufficient data",
            })
    return risks


def _normalize_opportunities(value) -> list[dict]:
    opportunities = []
    for item in _as_list(value):
        if isinstance(item, dict):
            opportunities.append({
                "title": _clean_text(item.get("title") or item.get("opportunity") or item.get("message"), "Business opportunity"),
                "opportunity_score": normalize_score(item.get("opportunity_score") or item.get("score")),
                "expected_impact": _clean_text(item.get("expected_impact") or item.get("impact"), "insufficient data"),
            })
        else:
            opportunities.append({
                "title": _clean_text(item, "Business opportunity"),
                "opportunity_score": 50,
                "expected_impact": "insufficient data",
            })
    return opportunities


def _normalize_actions(value) -> list[dict]:
    actions = []
    for item in _as_list(value):
        if isinstance(item, dict):
            priority = str(item.get("priority") or "medium").lower().strip()
            actions.append({
                "action": _clean_text(item.get("action") or item.get("title") or item.get("message"), "Review report"),
                "priority": priority if priority in _PRIORITIES else "medium",
                "owner_role": _clean_text(item.get("owner_role"), "Management"),
                "related_doctype": _clean_text(item.get("related_doctype")),
                "related_document": _clean_text(item.get("related_document")),
                "suggested_next_step": _clean_text(item.get("suggested_next_step") or item.get("next_step"), "insufficient data"),
            })
        else:
            actions.append({
                "action": _clean_text(item, "Review report"),
                "priority": "medium",
                "owner_role": "Management",
                "related_doctype": "",
                "related_document": "",
                "suggested_next_step": "insufficient data",
            })
    return actions


def _normalize_advisory(parsed: dict) -> dict:
    """Normalize new advisory JSON and legacy four-list JSON into one safe shape."""
    if not isinstance(parsed, dict):
        parsed = {}
    return {
        "executive_summary": _clean_text(parsed.get("executive_summary")),
        "findings": [_clean_text(i) for i in _as_list(parsed.get("findings")) if _clean_text(i)],
        "root_causes": [_clean_text(i) for i in _as_list(parsed.get("root_causes")) if _clean_text(i)],
        "risks": _normalize_risks(parsed.get("risks")),
        "opportunities": _normalize_opportunities(parsed.get("opportunities")),
        "recommendations": [_clean_text(i) for i in _as_list(parsed.get("recommendations")) if _clean_text(i)],
        "required_actions": _normalize_actions(parsed.get("required_actions")),
        "expected_business_impact": _clean_text(parsed.get("expected_business_impact")),
    }


def _deterministic_advisory(tool_result: dict) -> dict:
    """Add deterministic advisory signals before the LLM interpretation."""
    metrics = tool_result.get("metrics") or {}
    intent = tool_result.get("intent", "unknown")
    base_curr = metrics.get("base_currency", "QAR")
    findings: list[str] = []
    root_causes: list[str] = []
    risks: list[dict] = []
    opportunities: list[dict] = []
    actions: list[dict] = []

    def add_risk(title: str, severity: str, score: int, impact: str) -> None:
        risks.append({"title": title, "severity": severity, "risk_score": score, "business_impact": impact})

    def add_action(action: str, priority: str, owner: str, doctype: str = "", doc: str = "", next_step: str = "") -> None:
        actions.append({
            "action": action,
            "priority": priority,
            "owner_role": owner,
            "related_doctype": doctype,
            "related_document": doc,
            "suggested_next_step": next_step or "Review the related report and assign an owner.",
        })

    revenue_change = metrics.get("revenue_mom_pct", metrics.get("mom_change_pct", metrics.get("revenue_vs_prev_pct")))
    if isinstance(revenue_change, (int, float)) and revenue_change < 0:
        findings.append(f"Revenue is down {abs(round(revenue_change, 1))}% versus the comparison period.")
        root_causes.append("Revenue decline may be linked to lower conversion, reduced order volume, pricing pressure, or customer inactivity; confirm with customer/item detail.")
        add_risk("Revenue decline", "high" if revenue_change <= -15 else "medium", 80 if revenue_change <= -15 else 60,
                 "If not corrected, the current sales run rate may reduce cash inflow and margin coverage.")
        add_action("Review declining customers/items and recover open opportunities", "urgent" if revenue_change <= -15 else "high", "Sales Manager",
                   next_step="Compare top customers and items against the previous period and assign follow-up calls.")

    overdue_amount = metrics.get("overdue_amount", metrics.get("total_overdue", 0)) or 0
    overdue_count = metrics.get("overdue_invoice_count", metrics.get("invoice_count", 0)) or 0
    over_90_pct = metrics.get("over_90_pct", 0) or 0
    if overdue_amount or overdue_count:
        add_risk("Collection risk", "critical" if over_90_pct >= 40 else "high", 90 if over_90_pct >= 40 else 75,
                 f"{base_curr} {float(overdue_amount):,.0f} is overdue across {int(overdue_count)} invoice(s); delayed collection can pressure cash flow.")
        add_action("Prioritize overdue collections", "urgent", "Accounts Manager", "Sales Invoice",
                   next_step="Contact the largest overdue customers first and agree dated payment commitments.")

    inactive_count = tool_result.get("inactive_count") or metrics.get("inactive_customers")
    if inactive_count:
        add_risk("Customer churn risk", "medium", 55,
                 f"{inactive_count} customer(s) appear inactive; delayed follow-up can reduce repeat revenue.")
        add_action("Launch customer reactivation follow-up", "high", "Sales Manager",
                   next_step="Segment inactive customers by lifetime value and contact high-value accounts first.")

    pending_q = metrics.get("pending_quotations", tool_result.get("total_pending", 0)) or 0
    expiring_q = tool_result.get("expiring_quotations", metrics.get("expiring_quotations", 0)) or 0
    if pending_q or expiring_q:
        opportunities.append({
            "title": "Quotation conversion opportunity",
            "opportunity_score": 75 if expiring_q else 60,
            "expected_impact": f"Converting pending quotations can improve near-term revenue; {pending_q} pending and {expiring_q} expiring soon.",
        })
        add_action("Follow up stale or expiring quotations", "high" if expiring_q else "medium", "Sales Manager", "Quotation",
                   next_step="Call owners of quotations older than 14 days or expiring within 7 days.")

    low_stock = metrics.get("critical_stock_items", metrics.get("low_stock_items", tool_result.get("low_stock_count", 0))) or 0
    if low_stock:
        add_risk("Inventory availability risk", "high" if low_stock > 3 else "medium", 70 if low_stock > 3 else 50,
                 f"{low_stock} item(s) are below safety stock or reorder thresholds; stockouts can delay delivery and revenue recognition.")
        add_action("Replenish critical stock items", "high", "Stock Manager", "Item",
                   next_step="Review reorder levels and create material requests for critical items.")

    gross_margin = metrics.get("gross_margin_pct")
    previous_margin = metrics.get("previous_gross_margin_pct")
    if isinstance(gross_margin, (int, float)) and isinstance(previous_margin, (int, float)) and gross_margin < previous_margin:
        root_causes.append("Gross margin deterioration may indicate pricing leakage, higher item cost, discounting, or unfavorable sales mix.")
        add_risk("Margin compression", "high", 70,
                 "Lower gross margin reduces profit even when revenue is stable; pricing and cost drivers need review.")
        add_action("Review pricing, discounts, and item costs", "high", "Accounts Manager",
                   next_step="Compare margin by item group and customer segment against the previous period.")

    return {
        "executive_summary": "",
        "findings": findings,
        "root_causes": root_causes,
        "risks": risks,
        "opportunities": opportunities,
        "recommendations": [],
        "required_actions": actions,
        "expected_business_impact": "",
        "_intent": intent,
    }


def _merge_advisory(rule_based: dict, ai_based: dict) -> dict:
    merged = _normalize_advisory(ai_based)
    for key in ("findings", "root_causes", "risks", "opportunities", "recommendations", "required_actions"):
        merged[key] = (rule_based.get(key) or []) + (merged.get(key) or [])
    if not merged.get("executive_summary"):
        merged["executive_summary"] = rule_based.get("executive_summary") or ""
    if not merged.get("expected_business_impact"):
        merged["expected_business_impact"] = rule_based.get("expected_business_impact") or ""
    return merged


def _interpret_analytics(tool_result: dict, user_message: str, user: str) -> dict | None:
    """
    Send computed metrics to the AI and get back business advisory sections.

    Returns the advisory schema, while keeping legacy findings/risks/
    recommendations/required_actions compatible for older renderers.
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
        rule_based = _deterministic_advisory(tool_result)

        # Build compact, number-rich context. Keep source report data bounded.
        ctx = ["### Metrics"]
        for k, v in metrics.items():
            ctx.append(f"- {k}: {v}")
        base_curr = metrics.get("base_currency", "QAR")
        multi_curr = metrics.get("multi_currency", False)
        if aging:
            ctx.append(f"### Aging Buckets ({base_curr})")
            for bucket, amt in aging.items():
                ctx.append(f"- {bucket} days past due: {amt:,.0f}")
        if top_cx:
            ctx.append("### Top Customers by Outstanding")
            for cx in top_cx[:5]:
                customer = cx.get("customer", "Unknown") if isinstance(cx, dict) else "Unknown"
                outstanding = frappe.utils.flt(cx.get("outstanding", cx.get("total", 0))) if isinstance(cx, dict) else 0
                pct = cx.get("pct_of_total", "") if isinstance(cx, dict) else ""
                ctx.append(f"- {customer}: {base_curr} {outstanding:,.0f}" + (f" ({pct}%)" if pct != "" else ""))
        for label, key in [
            ("Top Items", "top_items"),
            ("Alerts", "alerts"),
            ("Recommendations Already Computed", "recommendations"),
            ("Department Scores", "department_scores"),
            ("Priorities", "priorities"),
        ]:
            val = tool_result.get(key)
            if val:
                ctx.append(f"### {label}")
                ctx.append(json.dumps(val[:8] if isinstance(val, list) else val, default=str)[:2500])

        multi_curr_note = (
            " Transactions may involve multiple currencies — all amounts shown are base-currency equivalents."
            if multi_curr else ""
        )
        system_prompt = (
            "You are a senior business advisor for a Qatar-based ERPNext system. "
            "Interpret the supplied pre-computed report data and respond with ONLY valid JSON — "
            "no markdown, no explanation, no extra text.\n\n"
            'Output exactly this JSON shape: {"executive_summary":"","findings":[],"root_causes":[],'
            '"risks":[{"title":"","severity":"low|medium|high|critical","risk_score":0,'
            '"business_impact":""}],"opportunities":[{"title":"","opportunity_score":0,'
            '"expected_impact":""}],"recommendations":[],"required_actions":[{"action":"",'
            '"priority":"low|medium|high|urgent","owner_role":"","related_doctype":"",'
            '"related_document":"","suggested_next_step":""}],"expected_business_impact":""}\n\n'
            f"Rules: Every figure you quote must come from supplied numbers; never invent values. "
            f"If the data is insufficient, say \"insufficient data\". Base currency is {base_curr}.{multi_curr_note} "
            "Focus on root causes, risk scores, opportunity scores, business impact, and priority actions. "
            "For each risk/opportunity/action explain what happened, why it matters, what action is required, "
            "and expected impact if action is taken or ignored. Keep each array to 2-4 high-value items."
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

        # Accept both the new advisory shape and the legacy four-list shape.
        if not (_ADVISORY_INTERP_KEYS & parsed.keys()) and not (_LEGACY_INTERP_KEYS & parsed.keys()):
            frappe.log_error(title="Interpreter response invalid shape", message=resp.raw_text[:300])
            _log_interpret(user, _intent, user_content, resp.raw_text, _tokens, _cost, "Error")
            return _normalize_advisory(rule_based)

        result = _merge_advisory(rule_based, parsed)

        # If every list is empty after stripping, skip the analysis section entirely
        if not any(result.get(k) for k in (
            "executive_summary", "findings", "root_causes", "risks", "opportunities",
            "recommendations", "required_actions", "expected_business_impact",
        )):
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

    # Per-user rate limiting — prevent rapid-fire requests that exhaust workers or provider quotas.
    _cooldown_key = f"ai_cooldown:{user}"
    if frappe.cache().get_value(_cooldown_key):
        frappe.throw(_("Please wait a moment before sending another message."))
    frappe.cache().set_value(_cooldown_key, 1, expires_in_sec=2)

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
    return get_available_agents()


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
        frappe.log_error(title="AI Connection Test Failed", message=str(exc))
        return {"status": "error", "error": _("Connection test failed. Please check provider settings and logs.")}


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
    if not is_system_manager(user):
        return {
            "requests": int(data.get("requests") or 0),
            "tokens": int(data.get("tokens") or 0),
            "budget_used_pct": data["budget_used_pct"],
        }
    return data


@frappe.whitelist()
def get_daily_briefing() -> dict:
    require_management_access()
    try:
        from ai_assistant.api.permission_manager import validate_tool_permission
        validate_tool_permission(frappe.session.user, "get_management_summary")
        from ai_assistant.api.bi_tools import get_management_summary
        return get_management_summary()
    except frappe.PermissionError:
        raise
    except Exception as exc:
        frappe.log_error(title="Daily Briefing Failed", message=str(exc))
        return {"status": "error", "message": _("Daily briefing is currently unavailable. Please contact your administrator if this continues.")}


@frappe.whitelist()
def get_settings_status() -> dict:
    settings = frappe.get_single("AI Settings")
    has_key = False
    try:
        has_key = bool(settings.get_active_api_key())
    except Exception:
        pass
    voice_provider = settings.voice_provider or "Browser (Free)"
    has_voice_key = False
    try:
        has_voice_key = bool(settings.get_voice_api_key())
    except Exception:
        pass
    status = {
        "enabled": bool(settings.enabled),
        "allow_tool_execution": bool(settings.allow_tool_execution),
        "has_api_key": has_key,
        "enable_voice_input": bool(settings.enable_voice_input),
        "has_voice_key": has_voice_key,
    }
    if is_system_manager(frappe.session.user):
        status.update({
            "provider": settings.provider,
            "model": settings.get_active_model(),
            "fallback_mode": settings.fallback_mode,
            "voice_provider": voice_provider,
        })
    return status
