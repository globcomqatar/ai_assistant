"""
Tests for role-based AI tool filtering (permission_manager.py).

Covers: secure-default-deny for tools with no AI Tool Permission record,
role union across multiple roles, System Manager unrestricted access,
and the representative per-department examples from the spec (Sales,
Accounts, Stock, Purchase, Manufacturing).
"""
from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from ai_assistant.api.executor import execute_actions
from ai_assistant.api.permission_manager import (
    get_allowed_tools,
    get_permitted_tools_schema,
    invalidate_cache,
    validate_tool_permission,
)
from ai_assistant.tests.helpers import ensure_user

SALES_USER = "ai-perm-sales@example.com"
ACCOUNTS_USER = "ai-perm-accounts@example.com"
STOCK_USER = "ai-perm-stock@example.com"
PURCHASE_USER = "ai-perm-purchase@example.com"
MANUFACTURING_USER = "ai-perm-mfg@example.com"
MULTI_ROLE_USER = "ai-perm-multi@example.com"
SM_USER = "ai-perm-sm@example.com"

_NO_PERMISSION_TOOL = "ai_test_tool_with_no_permission_record"


class TestToolPermissions(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ensure_user(SALES_USER, "AI Perm Sales", ["Sales User"])
        ensure_user(ACCOUNTS_USER, "AI Perm Accounts", ["Accounts User"])
        ensure_user(STOCK_USER, "AI Perm Stock", ["Stock User"])
        ensure_user(PURCHASE_USER, "AI Perm Purchase", ["Purchase User"])
        ensure_user(MANUFACTURING_USER, "AI Perm Mfg", ["Manufacturing User"])
        ensure_user(MULTI_ROLE_USER, "AI Perm Multi", ["Sales User", "Accounts User"])
        ensure_user(SM_USER, "AI Perm SM", ["System Manager"])
        invalidate_cache()

    def tearDown(self):
        frappe.set_user("Administrator")
        invalidate_cache()

    # ── Secure default deny ──────────────────────────────────────────────────

    def test_tool_with_no_permission_record_is_denied(self):
        self.assertNotIn(_NO_PERMISSION_TOOL, get_allowed_tools(SALES_USER))
        with self.assertRaises(frappe.PermissionError):
            validate_tool_permission(SALES_USER, _NO_PERMISSION_TOOL)

    def test_executor_denies_unauthorized_tool_via_direct_action(self):
        # Simulates a direct API request bypassing the LLM's own tool choice.
        results = execute_actions(
            actions=[{"intent": _NO_PERMISSION_TOOL, "parameters": {}}],
            user=SALES_USER,
            prompt="test",
            ai_raw_response="{}",
        )
        self.assertEqual(results[0]["status"], "denied")

    # ── Role union ────────────────────────────────────────────────────────────

    def test_multiple_roles_receive_union_of_authorized_tools(self):
        sales_only = get_allowed_tools(SALES_USER)
        accounts_only = get_allowed_tools(ACCOUNTS_USER)
        multi = get_allowed_tools(MULTI_ROLE_USER)
        self.assertTrue(sales_only <= multi)
        self.assertTrue(accounts_only <= multi)
        # Union, not hardcoded to a single department: multi-role user gets
        # at least everything either single-role user gets.
        self.assertEqual(multi, sales_only | accounts_only)

    # ── System Manager unrestricted ─────────────────────────────────────────

    def test_system_manager_gets_every_enabled_tool(self):
        all_enabled = set(
            frappe.get_all("AI Tool Permission", filters={"enabled": 1}, pluck="tool_name")
        )
        self.assertEqual(get_allowed_tools(SM_USER), all_enabled)

    # ── Per-department examples from the spec ──────────────────────────────

    def test_sales_user_gets_permitted_sales_tools(self):
        allowed = get_allowed_tools(SALES_USER)
        for tool in ("search_customer", "create_lead", "create_opportunity", "create_quotation", "get_sales_orders"):
            self.assertIn(tool, allowed, f"Sales User missing expected tool: {tool}")
        # Must not receive accounts write tools without an accounts role.
        for tool in ("create_journal_entry", "record_payment", "create_sales_invoice"):
            self.assertNotIn(tool, allowed, f"Sales User unexpectedly has: {tool}")

    def test_accounts_user_gets_permitted_accounts_tools_but_not_sensitive_writes(self):
        allowed = get_allowed_tools(ACCOUNTS_USER)
        for tool in ("get_pending_invoices", "get_accounts_receivable", "get_payment_entries",
                     "get_account_balance", "get_journal_entries"):
            self.assertIn(tool, allowed, f"Accounts User missing expected tool: {tool}")
        # Sensitive write tools require Accounts Manager, not Accounts User.
        for tool in ("create_journal_entry", "record_payment"):
            self.assertNotIn(tool, allowed, f"Accounts User must not receive: {tool}")

    def test_stock_user_gets_permitted_stock_tools(self):
        allowed = get_allowed_tools(STOCK_USER)
        for tool in ("get_stock", "get_stock_report", "get_delivery_notes", "get_stock_alerts"):
            self.assertIn(tool, allowed, f"Stock User missing expected tool: {tool}")

    def test_purchase_user_gets_permitted_purchase_tools(self):
        allowed = get_allowed_tools(PURCHASE_USER)
        for tool in ("search_supplier", "get_pending_purchase_orders"):
            self.assertIn(tool, allowed, f"Purchase User missing expected tool: {tool}")
        self.assertNotIn("create_purchase_order", allowed)  # Purchase Manager only

    def test_manufacturing_user_gets_permitted_manufacturing_tools(self):
        allowed = get_allowed_tools(MANUFACTURING_USER)
        for tool in ("get_work_orders", "get_bom_list"):
            self.assertIn(tool, allowed, f"Manufacturing User missing expected tool: {tool}")
        self.assertNotIn("create_work_order", allowed)  # Manufacturing Manager only

    # ── LLM-facing schema stays server-filtered ─────────────────────────────

    def test_permitted_tools_schema_excludes_unauthorized_tools_for_sales_user(self):
        schema_names = {t["name"] for t in get_permitted_tools_schema(SALES_USER)}
        self.assertIn("search_customer", schema_names)
        self.assertNotIn("create_journal_entry", schema_names)
