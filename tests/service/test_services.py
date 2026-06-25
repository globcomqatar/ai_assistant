"""
Service layer tests.

Tests in this file verify the service classes (ReportService, ActionService,
WorkflowService) behave correctly. Most require a live Frappe bench context.

Run with:
    bench --site mysite.localhost run-tests --app ai_assistant

The example tests below use mocks so they run standalone with pytest too.
"""
from __future__ import annotations

import sys
import types
import unittest


def _install_stubs():
    """Install minimum frappe stubs for standalone testing."""
    if "frappe" not in sys.modules:
        frappe = types.ModuleType("frappe")
        frappe._ = lambda t, *a, **k: t
        frappe.throw = lambda msg, *a: (_ for _ in ()).throw(Exception(msg))
        frappe.ValidationError = Exception
        frappe.PermissionError = PermissionError
        frappe.session = types.SimpleNamespace(user="Administrator")
        frappe.local = None
        frappe.conf = types.SimpleNamespace(developer_mode=0, ai_debug_mode=0)
        sys.modules["frappe"] = frappe

    # Ensure frappe.utils submodule is available (needed by action_handlers.py)
    if "frappe.utils" not in sys.modules:
        frappe_utils = types.ModuleType("frappe.utils")
        frappe_utils.now_datetime = lambda: None
        frappe_utils.add_days = lambda dt, n: dt
        frappe_utils.getdate = lambda dt=None: dt
        frappe_utils.nowdate = lambda: ""
        frappe_utils.format_date = lambda dt, fmt=None: str(dt)
        sys.modules["frappe.utils"] = frappe_utils
        sys.modules["frappe"].utils = frappe_utils


_install_stubs()
sys.path.insert(0, ".")


class TestActionServiceRegistry(unittest.TestCase):
    """Verify ActionService.get_action_registry() delegates correctly."""

    def test_returns_list(self):
        from ai_assistant.services.action_service import ActionService
        svc = ActionService()
        registry = svc.get_action_registry()
        self.assertIsInstance(registry, list)
        self.assertGreater(len(registry), 0)

    def test_returns_known_action(self):
        from ai_assistant.services.action_service import ActionService
        svc = ActionService()
        action = svc.get_action("create_task")
        self.assertIsNotNone(action)
        self.assertEqual(action["action_id"], "create_task")

    def test_unknown_action_returns_none(self):
        from ai_assistant.services.action_service import ActionService
        svc = ActionService()
        self.assertIsNone(svc.get_action("no_such_action"))


class TestWorkflowServiceRegistry(unittest.TestCase):
    """Verify WorkflowService.get_workflow_registry() delegates correctly."""

    def test_returns_list(self):
        from ai_assistant.services.workflow_service import WorkflowService
        svc = WorkflowService()
        registry = svc.get_workflow_registry()
        self.assertIsInstance(registry, list)
        self.assertGreater(len(registry), 0)

    def test_infer_workflow_collection(self):
        from ai_assistant.services.workflow_service import WorkflowService
        svc = WorkflowService()
        wf_id = svc.infer_workflow({"title": "Overdue invoice collection"})
        self.assertEqual(wf_id, "collection_recovery")

    def test_infer_workflow_fallback(self):
        from ai_assistant.services.workflow_service import WorkflowService
        svc = WorkflowService()
        wf_id = svc.infer_workflow({"title": "Something completely unrelated"})
        self.assertEqual(wf_id, "reminder_workflow")


class TestMetricsSingleton(unittest.TestCase):
    """Verify the metrics collector works without Frappe context."""

    def setUp(self):
        from ai_assistant.core.metrics import MetricsCollector
        self.collector = MetricsCollector()

    def test_initial_snapshot_zeros(self):
        snap = self.collector.snapshot()
        self.assertEqual(snap["requests"]["total"], 0)
        self.assertEqual(snap["requests"]["success"], 0)

    def test_record_request_increments_total(self):
        self.collector.record_request(success=True, tokens=100, cost=0.001, elapsed=0.5)
        snap = self.collector.snapshot()
        self.assertEqual(snap["requests"]["total"], 1)
        self.assertEqual(snap["requests"]["success"], 1)

    def test_record_error_counts(self):
        self.collector.record_error("ProviderError")
        self.collector.record_error("ProviderError")
        snap = self.collector.snapshot()
        self.assertEqual(snap["errors"].get("ProviderError"), 2)

    def test_reset_clears_all(self):
        self.collector.record_request(success=True)
        self.collector.reset()
        snap = self.collector.snapshot()
        self.assertEqual(snap["requests"]["total"], 0)


if __name__ == "__main__":
    unittest.main()
