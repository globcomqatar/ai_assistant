"""
Smoke tests — fast import and structure checks.

These tests run without a live Frappe instance and verify that the
critical modules can be imported and their exports have the expected shape.
They act as a first line of defense: if a smoke test fails, no deeper
test needs to run.

Run with:
    python -m pytest tests/regression/test_smoke.py -v
"""
from __future__ import annotations

import sys
import types
import unittest


def _setup():
    """Install minimal frappe stub and add project to path."""
    if "frappe" not in sys.modules:
        frappe = types.ModuleType("frappe")
        frappe._ = lambda t, *a, **k: t
        frappe.log_error = lambda *a, **k: None
        frappe.whitelist = lambda *a, **k: (lambda fn: fn)
        frappe.session = types.SimpleNamespace(user="Administrator")
        frappe.local = None
        frappe.conf = types.SimpleNamespace(developer_mode=0, ai_debug_mode=0)
        sys.modules["frappe"] = frappe
    sys.path.insert(0, ".")


_setup()


class TestCoreImports(unittest.TestCase):

    def test_exceptions_importable(self):
        from ai_assistant.core.exceptions import (
            AIAssistantError, ProviderError, BudgetExceededError,
            PermissionDeniedError, ValidationError, ConfigurationError,
        )

    def test_response_importable(self):
        from ai_assistant.core.response import ok, error, APIResponse, RequestTimer

    def test_metrics_importable(self):
        from ai_assistant.core.metrics import MetricsCollector, metrics

    def test_orchestrator_importable(self):
        from ai_assistant.core.orchestrator import (
            AIOrchestrator, OrchestratorRequest, OrchestratorResponse,
        )

    def test_debug_importable(self):
        from ai_assistant.core.debug import is_debug_mode, debug_log


class TestSecurityPackage(unittest.TestCase):

    def test_security_exports(self):
        from ai_assistant.security.security import (
            MANAGEMENT_ROLES, HIGH_RISK_WRITE_TOOLS,
            is_system_manager, insert_with_permission, is_confirmed_action,
        )
        self.assertIn("System Manager", MANAGEMENT_ROLES)
        self.assertIn("create_sales_invoice", HIGH_RISK_WRITE_TOOLS)

    def test_shim_resolves_to_same_objects(self):
        from ai_assistant.security.security import MANAGEMENT_ROLES as canonical
        from ai_assistant.api.security import MANAGEMENT_ROLES as shim
        self.assertIs(canonical, shim)


class TestRegistriesPackage(unittest.TestCase):

    def test_action_registry_has_entries(self):
        from ai_assistant.registries.action_registry import ACTION_REGISTRY
        self.assertGreater(len(ACTION_REGISTRY), 0)

    def test_workflow_registry_has_entries(self):
        from ai_assistant.registries.workflow_registry import WORKFLOW_REGISTRY
        self.assertGreater(len(WORKFLOW_REGISTRY), 0)

    def test_action_shim_resolves_to_same(self):
        from ai_assistant.registries.action_registry import ACTION_REGISTRY as canonical
        from ai_assistant.api.action_registry import ACTION_REGISTRY as shim
        self.assertIs(canonical, shim)

    def test_workflow_shim_resolves_to_same(self):
        from ai_assistant.registries.workflow_registry import WORKFLOW_REGISTRY as canonical
        from ai_assistant.api.workflow_registry import WORKFLOW_REGISTRY as shim
        self.assertIs(canonical, shim)


class TestConfigSettings(unittest.TestCase):

    def test_required_constants_present(self):
        from ai_assistant.config.settings import (
            AGENT_CACHE_TTL_SECONDS, RBAC_CACHE_TTL_SECONDS,
            BUDGET_WARNING_THRESHOLD, BUDGET_BLOCK_THRESHOLD,
            HIGH_RISK_WRITE_TOOLS, MANAGEMENT_ROLES,
            CONFIDENCE_THRESHOLD, SLOW_QUERY_THRESHOLD_MS,
        )
        self.assertIsInstance(HIGH_RISK_WRITE_TOOLS, frozenset)
        self.assertIsInstance(MANAGEMENT_ROLES, frozenset)


class TestUtilsPackage(unittest.TestCase):

    def test_utils_init_importable(self):
        # utils/ package resolves to utils/__init__.py
        import ai_assistant.utils as u
        self.assertTrue(hasattr(u, "is_ai_enabled"))
        self.assertTrue(hasattr(u, "get_user_monthly_cost"))

    def test_helpers_importable(self):
        from ai_assistant.utils.helpers import (
            clamp, safe_float, safe_int, truncate, format_currency,
        )


class TestServicesPackage(unittest.TestCase):

    def test_report_service_importable(self):
        from ai_assistant.services.report_service import ReportService, report_service
        self.assertIsInstance(report_service, ReportService)

    def test_action_service_importable(self):
        from ai_assistant.services.action_service import ActionService, action_service
        self.assertIsInstance(action_service, ActionService)

    def test_approval_service_importable(self):
        from ai_assistant.services.approval_service import ApprovalService, approval_service
        self.assertIsInstance(approval_service, ApprovalService)

    def test_workflow_service_importable(self):
        from ai_assistant.services.workflow_service import WorkflowService, workflow_service
        self.assertIsInstance(workflow_service, WorkflowService)


if __name__ == "__main__":
    unittest.main()
