"""
Unit tests for the AI Kernel package.

Covers:
  - AIContext dataclass and AIContextManager helpers
  - PromptManager template management and rendering
  - FeatureFlagManager flag reading and overrides
  - EngineRegistry registration and listing
  - KernelProviderManager capability detection and selection

Run with:
    python -m pytest tests/unit/test_kernel.py -v
"""
from __future__ import annotations

import sys
import types
import unittest


def _setup():
    """Install minimal frappe stub for pure Python tests."""
    if "frappe" not in sys.modules:
        frappe = types.ModuleType("frappe")
        frappe._ = lambda t, *a, **k: t
        frappe.log_error = lambda *a, **k: None
        frappe.whitelist = lambda *a, **k: (lambda fn: fn)
        frappe.session = types.SimpleNamespace(user="Administrator")
        frappe.local = None
        frappe.conf = types.SimpleNamespace(developer_mode=0, ai_debug_mode=0, ai_flags={})
        sys.modules["frappe"] = frappe

    if "frappe.utils" not in sys.modules:
        frappe_utils = types.ModuleType("frappe.utils")
        frappe_utils.now_datetime = lambda: None
        frappe_utils.add_days = lambda dt, n: dt
        frappe_utils.get_time_zone = lambda: "UTC"
        sys.modules["frappe.utils"] = frappe_utils
        sys.modules["frappe"].utils = frappe_utils

    sys.path.insert(0, ".")


_setup()


# ── AIContext and AIContextManager ────────────────────────────────────────────

class TestAIContext(unittest.TestCase):

    def setUp(self):
        from ai_assistant.kernel.context_manager import AIContextManager
        self.mgr = AIContextManager()

    def test_build_with_defaults(self):
        from ai_assistant.kernel.context_manager import AIContext
        ctx = self.mgr.build()
        self.assertIsInstance(ctx, AIContext)
        self.assertEqual(ctx.user, "")
        self.assertEqual(ctx.language, "en")
        self.assertEqual(ctx.timezone, "UTC")

    def test_build_with_values(self):
        ctx = self.mgr.build(user="ahmed@example.com", company="Test Corp", roles=["Sales User"])
        self.assertEqual(ctx.user, "ahmed@example.com")
        self.assertEqual(ctx.company, "Test Corp")
        self.assertIn("Sales User", ctx.roles)

    def test_from_request_parses_fields(self):
        request = {
            "user": "manager@example.com",
            "company": "ACME",
            "module": "Accounts",
            "doctype": "Sales Invoice",
            "document": "SINV-0001",
        }
        ctx = self.mgr.from_request(request)
        self.assertEqual(ctx.user, "manager@example.com")
        self.assertEqual(ctx.module, "Accounts")
        self.assertEqual(ctx.doctype, "Sales Invoice")
        self.assertEqual(ctx.document, "SINV-0001")

    def test_from_request_handles_missing_fields(self):
        ctx = self.mgr.from_request({})
        self.assertEqual(ctx.user, "")
        self.assertEqual(ctx.roles, [])
        self.assertEqual(ctx.filters, {})

    def test_with_conversation_appends(self):
        ctx = self.mgr.build(conversation=[{"role": "user", "content": "Hello"}])
        new_ctx = self.mgr.with_conversation(ctx, [{"role": "assistant", "content": "Hi"}])
        self.assertEqual(len(new_ctx.conversation), 2)
        self.assertEqual(len(ctx.conversation), 1)  # original unchanged

    def test_with_flags_merges(self):
        ctx = self.mgr.build(feature_flags={"prediction_engine": False})
        new_ctx = self.mgr.with_flags(ctx, {"prediction_engine": True, "morning_brief": True})
        self.assertTrue(new_ctx.feature_flags["prediction_engine"])
        self.assertTrue(new_ctx.feature_flags["morning_brief"])
        self.assertFalse(ctx.feature_flags["prediction_engine"])  # original unchanged

    def test_with_provider_sets_fields(self):
        ctx = self.mgr.build()
        new_ctx = self.mgr.with_provider(ctx, "anthropic", "claude-3-5-sonnet")
        self.assertEqual(new_ctx.provider, "anthropic")
        self.assertEqual(new_ctx.model, "claude-3-5-sonnet")

    def test_to_dict_has_expected_keys(self):
        ctx = self.mgr.build(user="test@example.com")
        d = ctx.to_dict()
        for key in ("user", "roles", "company", "language", "timezone", "module",
                    "doctype", "document", "filters", "provider", "model", "feature_flags"):
            self.assertIn(key, d)

    def test_to_dict_excludes_memory_hooks(self):
        ctx = self.mgr.build()
        d = ctx.to_dict()
        self.assertNotIn("memory_hooks", d)


# ── PromptManager ─────────────────────────────────────────────────────────────

class TestPromptManager(unittest.TestCase):

    def setUp(self):
        from ai_assistant.kernel.prompt_manager import PromptManager
        self.mgr = PromptManager()

    def test_default_engines_registered(self):
        engines = self.mgr.list_engines()
        for expected in ("executive_report", "sales_agent", "accounts_agent",
                         "prediction_engine", "morning_brief"):
            self.assertIn(expected, engines)

    def test_get_latest_version(self):
        template = self.mgr.get("sales_agent")
        self.assertIsNotNone(template)
        self.assertEqual(template.engine, "sales_agent")

    def test_get_unknown_engine_returns_none(self):
        self.assertIsNone(self.mgr.get("non_existent_engine"))

    def test_get_specific_version(self):
        template = self.mgr.get("executive_report", version="v1")
        self.assertIsNotNone(template)
        self.assertEqual(template.version, "v1")

    def test_get_missing_version_returns_none(self):
        self.assertIsNone(self.mgr.get("sales_agent", version="v99"))

    def test_register_custom_prompt(self):
        from ai_assistant.kernel.prompt_manager import PromptTemplate
        custom = PromptTemplate(
            name="my_engine",
            engine="my_engine",
            version="v1",
            content="Hello {{user}}, welcome to {{company}}.",
            variables=["user", "company"],
        )
        self.mgr.register(custom)
        template = self.mgr.get("my_engine")
        self.assertIsNotNone(template)
        self.assertEqual(template.name, "my_engine")

    def test_render_substitutes_variables(self):
        from ai_assistant.kernel.prompt_manager import PromptTemplate
        template = PromptTemplate(
            name="test", engine="test", version="v1",
            content="Dear {{user}}, your company is {{company}}.",
            variables=["user", "company"],
        )
        rendered = self.mgr.render(template, {"user": "Ahmed", "company": "GlobalCom"})
        self.assertIn("Ahmed", rendered)
        self.assertIn("GlobalCom", rendered)
        self.assertNotIn("{{user}}", rendered)

    def test_render_leaves_missing_variables(self):
        from ai_assistant.kernel.prompt_manager import PromptTemplate
        template = PromptTemplate(
            name="test", engine="test", version="v1",
            content="Hello {{user}} and {{missing}}.",
            variables=["user"],
        )
        rendered = self.mgr.render(template, {"user": "Ahmed"})
        self.assertIn("Ahmed", rendered)
        self.assertIn("{{missing}}", rendered)  # not substituted

    def test_default_prompts_are_placeholders(self):
        template = self.mgr.get("prediction_engine")
        self.assertTrue(template.is_placeholder)

    def test_list_versions_for_engine(self):
        versions = self.mgr.list_versions("sales_agent")
        self.assertIn("v1", versions)


# ── FeatureFlagManager ────────────────────────────────────────────────────────

class TestFeatureFlagManager(unittest.TestCase):

    def setUp(self):
        from ai_assistant.kernel.feature_flags import FeatureFlagManager
        self.mgr = FeatureFlagManager()

    def test_all_flags_default_to_false(self):
        for value in self.mgr.get_all().values():
            self.assertFalse(value)

    def test_override_enables_flag(self):
        from ai_assistant.kernel.feature_flags import FeatureFlag
        self.mgr.override(FeatureFlag.PREDICTION_ENGINE, True)
        self.assertTrue(self.mgr.is_enabled(FeatureFlag.PREDICTION_ENGINE))

    def test_override_with_string_key(self):
        self.mgr.override("morning_brief", True)
        self.assertTrue(self.mgr.is_enabled("morning_brief"))

    def test_clear_overrides_restores_default(self):
        from ai_assistant.kernel.feature_flags import FeatureFlag
        self.mgr.override(FeatureFlag.RISK_ENGINE, True)
        self.mgr.clear_overrides()
        self.assertFalse(self.mgr.is_enabled(FeatureFlag.RISK_ENGINE))

    def test_get_all_returns_all_flags(self):
        from ai_assistant.kernel.feature_flags import FeatureFlag
        result = self.mgr.get_all()
        for flag in FeatureFlag:
            self.assertIn(flag.value, result)


# ── EngineRegistry ────────────────────────────────────────────────────────────

class TestEngineRegistry(unittest.TestCase):

    def setUp(self):
        from ai_assistant.kernel.engine_registry import engine_registry
        self.registry = engine_registry

    def test_phase2_engines_registered(self):
        for eid in ("report_engine", "recommendation_engine", "action_engine",
                    "approval_engine", "workflow_engine"):
            self.assertTrue(self.registry.is_registered(eid), f"{eid} not registered")

    def test_phase3_engines_registered(self):
        for eid in ("prediction_engine", "risk_engine", "opportunity_engine",
                    "learning_engine", "morning_brief", "insight_engine"):
            self.assertTrue(self.registry.is_registered(eid), f"{eid} not registered")

    def test_phase2_engines_are_available(self):
        for reg in self.registry.list_available():
            self.assertFalse(reg.is_placeholder)
            self.assertTrue(reg.is_available)

    def test_phase3_engines_are_placeholders(self):
        for reg in self.registry.list_placeholders():
            self.assertTrue(reg.is_placeholder)
            self.assertFalse(reg.is_available)

    def test_list_available_excludes_placeholders(self):
        available_ids = {r.engine_id for r in self.registry.list_available()}
        placeholder_ids = {r.engine_id for r in self.registry.list_placeholders()}
        self.assertEqual(available_ids & placeholder_ids, set())

    def test_get_returns_registration(self):
        reg = self.registry.get("report_engine")
        self.assertIsNotNone(reg)
        self.assertEqual(reg.engine_id, "report_engine")

    def test_get_unknown_returns_none(self):
        self.assertIsNone(self.registry.get("no_such_engine"))

    def test_summary_counts_correct(self):
        summary = self.registry.summary()
        self.assertEqual(summary["available"], len(self.registry.list_available()))
        self.assertEqual(summary["placeholders"], len(self.registry.list_placeholders()))
        self.assertEqual(summary["total"], len(self.registry.list_all()))


# ── KernelProviderManager ─────────────────────────────────────────────────────

class TestKernelProviderManager(unittest.TestCase):

    def setUp(self):
        from ai_assistant.kernel.provider_manager import KernelProviderManager
        self.mgr = KernelProviderManager()

    def test_phase2_providers_available(self):
        for pid in ("openai", "openrouter", "anthropic", "google", "groq"):
            self.assertTrue(self.mgr.is_available(pid), f"{pid} should be available")

    def test_phase3_providers_not_available(self):
        for pid in ("azure_openai", "ollama", "local"):
            self.assertFalse(self.mgr.is_available(pid), f"{pid} should not be available")

    def test_get_capabilities_for_openai(self):
        from ai_assistant.kernel.provider_manager import ProviderCapability
        caps = self.mgr.get_capabilities("openai")
        self.assertIn(ProviderCapability.JSON_MODE, caps)
        self.assertIn(ProviderCapability.FUNCTION_CALLING, caps)

    def test_select_provider_for_json_mode(self):
        from ai_assistant.kernel.provider_manager import ProviderCapability
        provider_id = self.mgr.select_provider([ProviderCapability.JSON_MODE])
        self.assertIsNotNone(provider_id)

    def test_select_provider_for_unsupported_capability(self):
        from ai_assistant.kernel.provider_manager import ProviderCapability
        # FINE_TUNING is only on placeholder providers — no match
        result = self.mgr.select_provider([ProviderCapability.FINE_TUNING])
        self.assertIsNone(result)

    def test_list_available_excludes_placeholders(self):
        available = self.mgr.list_available()
        for config in available:
            self.assertFalse(config.is_placeholder)

    def test_list_placeholders(self):
        placeholders = self.mgr.list_placeholders()
        placeholder_ids = {p.provider_id for p in placeholders}
        self.assertIn("azure_openai", placeholder_ids)
        self.assertIn("ollama", placeholder_ids)
        self.assertIn("local", placeholder_ids)

    def test_fallback_provider_excludes_given(self):
        fallback = self.mgr.get_fallback_provider_id(exclude="openai")
        self.assertIsNotNone(fallback)
        self.assertNotEqual(fallback, "openai")


if __name__ == "__main__":
    unittest.main()
