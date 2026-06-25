"""
supervisor.py — Auto-routing classifier for the Multi-Agent Framework.

When AI Settings.agent_routing_mode == "Auto", send_message calls
route_to_agent() to classify the user's message and pick the best
specialist agent.  Only activates for System Manager users — the
governance rules for all other users are entirely unchanged.
"""
from __future__ import annotations

import json
import time
import frappe


def is_auto_routing_enabled() -> bool:
    """Return True only when AI Settings.agent_routing_mode is 'Auto'."""
    mode = frappe.db.get_single_value("AI Settings", "agent_routing_mode") or "Manual"
    return mode == "Auto"


def route_to_agent(message: str, user: str) -> dict:
    """
    Classify *message* and return the best agent to handle it.

    Returns a dict: {"agent_code", "agent_name", "reason", "auto": True}
    Falls back to the default agent on any error — never raises.

    Routing logic:
    1. Fetch agents available to *user*, exclude "supervisor" and "general"
       (they are coordinators, not targets for routing).
    2. If ≤ 1 candidate exists, return the default immediately.
    3. Build a catalog and ask the AI provider for {"agent_code","reason"}.
    4. Validate the returned code against the candidate set.
    5. On any failure, fall back silently via frappe.log_error.
    """
    from ai_assistant.api.agent_manager import _get_available_agents_for_user, get_default_agent_code
    from ai_assistant.providers import get_provider
    from ai_assistant.api.router import _extract_json

    default_code = get_default_agent_code()
    default_name = (
        frappe.db.get_value("AI Agent", default_code, "agent_name") or default_code
    )
    _fallback: dict = {
        "agent_code": default_code,
        "agent_name": default_name,
        "reason": "Default agent selected.",
        "auto": True,
    }

    try:
        all_agents = _get_available_agents_for_user(user)
        candidates = [
            a for a in all_agents
            if a["agent_code"] not in ("supervisor", "general")
        ]

        if len(candidates) <= 1:
            return _fallback

        catalog_lines = "\n".join(
            f'- {a["agent_code"]}: {a["agent_name"]} — {a.get("description", "")}'
            for a in candidates
        )

        system_prompt = (
            "You are a routing classifier for an ERP AI assistant. "
            "Given a user message and a list of specialist agents, respond with ONLY "
            "valid JSON — no markdown, no explanation, no extra text.\n\n"
            'Output format: {"agent_code": "<code>", "reason": "<one sentence>"}\n\n'
            "Choose the single agent best suited to handle the user's request. "
            "If the message is ambiguous or cross-departmental, pick the most relevant agent.\n\n"
            f"Available agents:\n{catalog_lines}"
        )

        _t0 = time.perf_counter()
        provider = get_provider()
        # Tighter timeout for routing — must be fast so it never stalls the user
        if hasattr(provider, "_timeout"):
            provider._timeout = (5, 15)

        resp = provider.chat(
            messages=[{"role": "user", "content": message}],
            system_prompt=system_prompt,
        )
        _latency_ms = round((time.perf_counter() - _t0) * 1000)

        raw = resp.raw_text.strip()
        clean = _extract_json(raw)
        parsed = json.loads(clean)

        agent_code = str(parsed.get("agent_code", "")).strip()
        reason = str(parsed.get("reason", ""))

        valid_codes = {a["agent_code"] for a in candidates}
        if agent_code not in valid_codes:
            frappe.log_error(
                title="Supervisor: invalid agent_code from classifier",
                message=f"Got {agent_code!r}, valid: {valid_codes}, raw: {raw[:300]}",
            )
            return _fallback

        agent_name = next(
            (a["agent_name"] for a in candidates if a["agent_code"] == agent_code),
            agent_code,
        )

        _log: dict = {
            "user":            frappe.session.user,
            "message_preview": message[:120],
            "routed_to":       agent_code,
            "reason":          reason[:120],
            "latency_ms":      _latency_ms,
            "candidate_count": len(candidates),
            "method":          "llm",
        }
        if _latency_ms > 3000:
            _log["warning"] = "slow_routing"
            frappe.publish_realtime(
                "ai_supervisor_slow",
                {"latency_ms": _latency_ms, "user": frappe.session.user},
            )
        frappe.logger("ai_assistant").info(json.dumps(_log))

        return {
            "agent_code": agent_code,
            "agent_name": agent_name,
            "reason": reason,
            "auto": True,
        }

    except Exception as exc:
        _latency_ms = round((time.perf_counter() - _t0) * 1000) if "_t0" in dir() else -1
        frappe.log_error(
            title="[Supervisor] route_to_agent",
            message=json.dumps({
                "error":           str(exc),
                "latency_ms":      _latency_ms,
                "message_preview": message[:120],
            }),
        )
        return _fallback
