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


class TestKernelPackage(unittest.TestCase):
    """Wave 3 — AI Kernel single entry point."""

    def test_kernel_init_importable(self):
        from ai_assistant.kernel import (
            AIContext, AIContextManager, context_manager,
            PromptManager, PromptTemplate, prompt_manager,
            KernelProviderManager, ProviderCapability, ProviderConfig,
            EngineRegistry, EngineRegistration, engine_registry,
            FeatureFlagManager, FeatureFlag, feature_flags,
        )

    def test_context_manager_builds_context(self):
        from ai_assistant.kernel import context_manager, AIContext
        ctx = context_manager.build(user="test@example.com", company="ACME")
        self.assertIsInstance(ctx, AIContext)
        self.assertEqual(ctx.user, "test@example.com")

    def test_engine_registry_has_phase2_engines(self):
        from ai_assistant.kernel import engine_registry
        available = {r.engine_id for r in engine_registry.list_available()}
        for eid in ("report_engine", "action_engine", "workflow_engine"):
            self.assertIn(eid, available)

    def test_engine_registry_has_phase3_placeholders(self):
        from ai_assistant.kernel import engine_registry
        placeholders = {r.engine_id for r in engine_registry.list_placeholders()}
        for eid in ("prediction_engine", "risk_engine", "opportunity_engine"):
            self.assertIn(eid, placeholders)

    def test_feature_flags_all_off_by_default(self):
        from ai_assistant.kernel.feature_flags import FeatureFlagManager
        mgr = FeatureFlagManager()
        for value in mgr.get_all().values():
            self.assertFalse(value)

    def test_prompt_manager_has_default_prompts(self):
        from ai_assistant.kernel import prompt_manager
        self.assertIn("sales_agent", prompt_manager.list_engines())
        self.assertIn("prediction_engine", prompt_manager.list_engines())


class TestEnginesPackage(unittest.TestCase):
    """Wave 3 — engines/ package structure and placeholder behaviour."""

    def test_phase2_engines_importable(self):
        from ai_assistant.engines import (
            BaseEngine, ReportEngine, RecommendationEngine,
            ActionEngine, ApprovalEngine, WorkflowEngine,
        )

    def test_phase3_engines_importable(self):
        from ai_assistant.engines import (
            PredictionEngine, RiskEngine, OpportunityEngine,
            LearningEngine, MorningBriefEngine, InsightEngine,
        )

    def test_phase2_engines_not_placeholder(self):
        from ai_assistant.engines import (
            ReportEngine, ActionEngine, WorkflowEngine,
        )
        for cls in (ReportEngine, ActionEngine, WorkflowEngine):
            self.assertFalse(cls.is_placeholder, f"{cls.__name__} should not be a placeholder")

    def test_phase3_engines_are_placeholder(self):
        from ai_assistant.engines import (
            PredictionEngine, RiskEngine, OpportunityEngine, InsightEngine,
        )
        for cls in (PredictionEngine, RiskEngine, OpportunityEngine, InsightEngine):
            self.assertTrue(cls.is_placeholder, f"{cls.__name__} should be a placeholder")

    def test_phase3_execute_raises_not_implemented(self):
        from ai_assistant.engines import PredictionEngine
        engine = PredictionEngine()
        with self.assertRaises(NotImplementedError):
            engine.execute(None, {})

    def test_base_engine_describe(self):
        from ai_assistant.engines import ReportEngine
        engine = ReportEngine()
        info = engine.describe()
        self.assertIn("engine_id", info)
        self.assertIn("is_placeholder", info)
        self.assertTrue(info["available"])


class TestRegistriesExtended(unittest.TestCase):
    """Wave 3 — populated playbook and KPI registries."""

    def test_playbook_registry_has_named_entries(self):
        from ai_assistant.registries.playbook_registry import (
            PLAYBOOK_REGISTRY, get_playbook, get_playbook_registry,
        )
        self.assertGreater(len(PLAYBOOK_REGISTRY), 0)
        self.assertIsNotNone(get_playbook("collection_recovery"))
        self.assertIsNotNone(get_playbook("quotation_follow_up"))

    def test_kpi_registry_has_named_entries(self):
        from ai_assistant.registries.kpi_registry import (
            KPI_REGISTRY, get_kpi, get_kpi_registry,
        )
        self.assertGreater(len(KPI_REGISTRY), 0)
        self.assertIsNotNone(get_kpi("monthly_revenue"))
        self.assertIsNotNone(get_kpi("overdue_collections"))

    def test_playbook_entries_have_required_fields(self):
        from ai_assistant.registries.playbook_registry import PLAYBOOK_REGISTRY
        for pb in PLAYBOOK_REGISTRY:
            self.assertIn("playbook_id", pb)
            self.assertIn("name", pb)
            self.assertIn("trigger", pb)
            self.assertIn("confidence_threshold", pb)

    def test_kpi_entries_have_required_fields(self):
        from ai_assistant.registries.kpi_registry import KPI_REGISTRY
        for kpi in KPI_REGISTRY:
            self.assertIn("kpi_id", kpi)
            self.assertIn("name", kpi)
            self.assertIn("unit", kpi)
            self.assertIn("source_doctype", kpi)


if __name__ == "__main__":
    unittest.main()
