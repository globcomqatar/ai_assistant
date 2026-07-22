"""
Tests for the non-System-Manager governance pipeline:
resolve_active_agent / validate_agent_switch / get_session_agent /
get_available_agents, plus the send_message() integration of Supervisor
auto-routing gating.

System Manager behavior (full agent list, manual switching, Supervisor/Auto
routing) must remain completely unchanged — that is asserted here too.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from ai_assistant.api.agent_manager import (
    get_available_agents,
    get_session_agent,
    resolve_active_agent,
    validate_agent_switch,
)
from ai_assistant.providers.base import AIResponse
from ai_assistant.tests.helpers import ensure_user

NON_SM_USER = "ai-governance-nonsm@example.com"
SM_USER = "ai-governance-sm@example.com"


def _stub_provider(raw_text='{"intent":"reply","message":"stub"}'):
    provider = MagicMock()
    provider.chat.return_value = AIResponse(
        raw_text=raw_text,
        tokens_prompt=1,
        tokens_completion=1,
        tokens_total=2,
        estimated_cost_usd=0.0,
        model="stub-model",
    )
    return provider


class TestAgentGovernance(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ensure_user(NON_SM_USER, "AI Gov NonSM", ["Sales User"])
        ensure_user(SM_USER, "AI Gov SM", ["System Manager"])

    def tearDown(self):
        frappe.set_user("Administrator")

    # ── resolve_active_agent ────────────────────────────────────────────────

    def test_non_sm_always_resolves_to_general(self):
        self.assertEqual(resolve_active_agent(NON_SM_USER, "sales"), "general")
        self.assertEqual(resolve_active_agent(NON_SM_USER, "supervisor"), "general")
        self.assertEqual(resolve_active_agent(NON_SM_USER, None), "general")

    def test_non_sm_cannot_override_via_arbitrary_request_param(self):
        # Simulates a crafted direct API call: send_message(current_agent="sales_manager")
        self.assertEqual(resolve_active_agent(NON_SM_USER, "sales_manager"), "general")
        self.assertEqual(resolve_active_agent(NON_SM_USER, "anything-not-a-real-agent"), "general")

    def test_system_manager_can_request_specialist_agent(self):
        self.assertEqual(resolve_active_agent(SM_USER, "sales"), "sales")
        self.assertEqual(resolve_active_agent(SM_USER, None), resolve_active_agent(SM_USER, None))

    # ── validate_agent_switch ────────────────────────────────────────────────

    def test_validate_agent_switch_blocks_non_sm_from_specialist_agent(self):
        with self.assertRaises(frappe.PermissionError):
            validate_agent_switch(NON_SM_USER, "sales")

    def test_validate_agent_switch_allows_non_sm_on_general(self):
        validate_agent_switch(NON_SM_USER, "general")  # must not raise

    def test_validate_agent_switch_allows_sm_any_agent(self):
        validate_agent_switch(SM_USER, "sales")  # must not raise
        validate_agent_switch(SM_USER, "general")  # must not raise

    # ── get_session_agent ────────────────────────────────────────────────────

    def test_session_agent_forced_to_general_for_non_sm(self):
        # Simulates stale/tampered browser session state carrying a specialist agent.
        self.assertEqual(get_session_agent(NON_SM_USER, "accounts_manager"), "general")

    def test_session_agent_respected_for_sm(self):
        self.assertEqual(get_session_agent(SM_USER, "sales"), "sales")

    # ── get_available_agents ─────────────────────────────────────────────────

    def test_non_sm_sees_only_general_agent(self):
        agents = get_available_agents(NON_SM_USER)
        self.assertEqual(len(agents), 1)
        self.assertEqual(agents[0]["agent_code"], "general")

    def test_sm_sees_full_enabled_agent_list(self):
        agents = get_available_agents(SM_USER)
        codes = {a["agent_code"] for a in agents}
        self.assertIn("general", codes)
        self.assertGreater(len(agents), 1)  # specialist agents still present

    # ── send_message() integration: Supervisor gating ───────────────────────

    def test_send_message_skips_supervisor_for_non_sm_even_in_auto_mode(self):
        settings = frappe.get_single("AI Settings")
        original_mode = settings.agent_routing_mode
        settings.db_set("agent_routing_mode", "Auto")
        try:
            with patch("ai_assistant.api.supervisor.route_to_agent") as mock_route, \
                 patch("ai_assistant.providers.get_provider", return_value=_stub_provider()):
                frappe.set_user(NON_SM_USER)
                from ai_assistant.api.chat import send_message
                result = send_message(message="hello", current_agent="sales")
                mock_route.assert_not_called()
                self.assertIsNone(result.get("routing"))
        finally:
            settings.db_set("agent_routing_mode", original_mode)

    def test_send_message_uses_supervisor_for_sm_in_auto_mode(self):
        settings = frappe.get_single("AI Settings")
        original_mode = settings.agent_routing_mode
        settings.db_set("agent_routing_mode", "Auto")
        canned_routing = {
            "agent_code": "sales", "agent_name": "Sales Agent",
            "reason": "test", "auto": True,
        }
        try:
            with patch("ai_assistant.api.supervisor.route_to_agent", return_value=canned_routing) as mock_route, \
                 patch("ai_assistant.providers.get_provider", return_value=_stub_provider()):
                frappe.set_user(SM_USER)
                from ai_assistant.api.chat import send_message
                result = send_message(message="hello", current_agent="general")
                mock_route.assert_called_once()
                self.assertEqual(result.get("routing"), canned_routing)
        finally:
            settings.db_set("agent_routing_mode", original_mode)
