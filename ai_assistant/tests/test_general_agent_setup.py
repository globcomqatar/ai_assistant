"""
Tests for the General Agent enablement repair (setup.py) and the safe-failure
behavior when an agent is missing or disabled (agent_manager.load_agent).
"""
from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from ai_assistant.api.agent_manager import invalidate_agent_cache, load_agent
from ai_assistant.setup import _ensure_general_agent_enabled


class TestGeneralAgentSetupRepair(FrappeTestCase):
    def setUp(self):
        self._original_enabled = frappe.db.get_value("AI Agent", "general", "enabled")
        self._original_description = frappe.db.get_value("AI Agent", "general", "description")

    def tearDown(self):
        if self._original_enabled is not None:
            frappe.db.set_value("AI Agent", "general", "enabled", self._original_enabled, update_modified=False)
            frappe.db.set_value("AI Agent", "general", "description", self._original_description, update_modified=False)
            frappe.db.commit()
        invalidate_agent_cache("general")

    def test_general_agent_enabled_after_repair(self):
        frappe.db.set_value("AI Agent", "general", "enabled", 0, update_modified=False)
        frappe.db.commit()

        _ensure_general_agent_enabled()

        self.assertEqual(frappe.db.get_value("AI Agent", "general", "enabled"), 1)

    def test_repair_is_idempotent_and_creates_no_duplicates(self):
        frappe.db.set_value("AI Agent", "general", "enabled", 0, update_modified=False)
        frappe.db.commit()

        _ensure_general_agent_enabled()
        _ensure_general_agent_enabled()
        _ensure_general_agent_enabled()

        self.assertEqual(frappe.db.count("AI Agent", {"agent_code": "general"}), 1)
        self.assertEqual(frappe.db.get_value("AI Agent", "general", "enabled"), 1)

    def test_repair_is_noop_when_already_enabled(self):
        frappe.db.set_value("AI Agent", "general", "enabled", 1, update_modified=False)
        frappe.db.commit()

        _ensure_general_agent_enabled()  # must not raise or duplicate

        self.assertEqual(frappe.db.count("AI Agent", {"agent_code": "general"}), 1)

    def test_repair_preserves_administrator_customization(self):
        frappe.db.set_value("AI Agent", "general", "description", "Custom admin description", update_modified=False)
        frappe.db.set_value("AI Agent", "general", "enabled", 0, update_modified=False)
        frappe.db.commit()

        _ensure_general_agent_enabled()

        self.assertEqual(frappe.db.get_value("AI Agent", "general", "enabled"), 1)
        self.assertEqual(
            frappe.db.get_value("AI Agent", "general", "description"),
            "Custom admin description",
        )

    def test_repair_invalidates_agent_cache(self):
        frappe.cache().set_value("ai_agent:general", {"stale": True}, expires_in_sec=300)
        frappe.db.set_value("AI Agent", "general", "enabled", 0, update_modified=False)
        frappe.db.commit()

        _ensure_general_agent_enabled()

        self.assertIsNone(frappe.cache().get_value("ai_agent:general"))


class TestAgentSafeFailure(FrappeTestCase):
    """Missing or disabled agents must fail loudly, never silently."""

    def test_load_agent_raises_controlled_error_when_disabled(self):
        frappe.db.set_value("AI Agent", "general", "enabled", 0, update_modified=False)
        frappe.db.commit()
        invalidate_agent_cache("general")
        try:
            with self.assertRaises(frappe.ValidationError):
                load_agent("general")
        finally:
            frappe.db.set_value("AI Agent", "general", "enabled", 1, update_modified=False)
            frappe.db.commit()
            invalidate_agent_cache("general")

    def test_load_agent_raises_controlled_error_when_missing(self):
        with self.assertRaises(frappe.ValidationError):
            load_agent("this_agent_code_does_not_exist")
