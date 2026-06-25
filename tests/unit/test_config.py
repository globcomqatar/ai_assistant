"""Unit tests for config/settings.py — no Frappe dependency."""
import sys
import unittest


class TestConfigSettings(unittest.TestCase):
    """Verify that all required configuration constants are present and sane."""

    def setUp(self):
        # config/settings.py has no frappe imports — import directly
        sys.path.insert(0, ".")
        from ai_assistant.config import settings
        self.s = settings

    def test_cache_ttls_are_positive(self):
        self.assertGreater(self.s.AGENT_CACHE_TTL_SECONDS, 0)
        self.assertGreater(self.s.RBAC_CACHE_TTL_SECONDS, 0)
        self.assertGreater(self.s.RATE_LIMIT_COOLDOWN_SECONDS, 0)

    def test_budget_thresholds_are_valid(self):
        self.assertGreater(self.s.BUDGET_WARNING_THRESHOLD, 0)
        self.assertLessEqual(self.s.BUDGET_WARNING_THRESHOLD, 1.0)
        self.assertLessEqual(self.s.BUDGET_WARNING_THRESHOLD, self.s.BUDGET_BLOCK_THRESHOLD)

    def test_confidence_threshold_is_between_0_and_1(self):
        self.assertGreaterEqual(self.s.CONFIDENCE_THRESHOLD, 0.0)
        self.assertLessEqual(self.s.CONFIDENCE_THRESHOLD, 1.0)

    def test_high_risk_tools_is_frozenset(self):
        self.assertIsInstance(self.s.HIGH_RISK_WRITE_TOOLS, frozenset)
        self.assertGreater(len(self.s.HIGH_RISK_WRITE_TOOLS), 0)

    def test_management_roles_is_frozenset(self):
        self.assertIsInstance(self.s.MANAGEMENT_ROLES, frozenset)
        self.assertIn("System Manager", self.s.MANAGEMENT_ROLES)

    def test_slow_query_threshold_is_positive(self):
        self.assertGreater(self.s.SLOW_QUERY_THRESHOLD_MS, 0)

    def test_known_high_risk_tools_present(self):
        known = {"create_sales_invoice", "record_payment", "create_journal_entry"}
        self.assertTrue(known.issubset(self.s.HIGH_RISK_WRITE_TOOLS))


if __name__ == "__main__":
    unittest.main()
