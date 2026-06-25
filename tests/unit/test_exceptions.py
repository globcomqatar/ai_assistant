"""Unit tests for core/exceptions.py — no Frappe dependency."""
import sys
import unittest


class TestExceptionHierarchy(unittest.TestCase):

    def setUp(self):
        sys.path.insert(0, ".")
        from ai_assistant.core import exceptions as ex
        self.ex = ex

    def test_all_exceptions_inherit_base(self):
        subclasses = [
            self.ex.ProviderError,
            self.ex.BudgetExceededError,
            self.ex.PermissionDeniedError,
            self.ex.ValidationError,
            self.ex.ConfigurationError,
            self.ex.AgentNotFoundError,
            self.ex.RateLimitError,
            self.ex.ToolExecutionError,
            self.ex.WorkflowError,
        ]
        for cls in subclasses:
            self.assertTrue(
                issubclass(cls, self.ex.AIAssistantError),
                f"{cls.__name__} does not inherit AIAssistantError",
            )

    def test_base_error_has_user_message(self):
        exc = self.ex.AIAssistantError("dev message")
        self.assertIsNotNone(exc.user_message)
        self.assertIsNotNone(exc.recovery)

    def test_to_dict_never_exposes_internal_message(self):
        secret = "SECRET_TOKEN_abc123"
        exc = self.ex.ProviderError(secret)
        d = exc.to_dict()
        self.assertNotIn(secret, str(d))

    def test_to_dict_has_required_keys(self):
        exc = self.ex.ValidationError("bad input")
        d = exc.to_dict()
        self.assertIn("error_code", d)
        self.assertIn("message", d)
        self.assertIn("recovery", d)

    def test_provider_error_http_status(self):
        self.assertEqual(self.ex.ProviderError.http_status_code, 502)

    def test_permission_denied_http_status(self):
        self.assertEqual(self.ex.PermissionDeniedError.http_status_code, 403)

    def test_budget_exceeded_http_status(self):
        self.assertEqual(self.ex.BudgetExceededError.http_status_code, 429)

    def test_rate_limit_http_status(self):
        self.assertEqual(self.ex.RateLimitError.http_status_code, 429)

    def test_validation_error_http_status(self):
        self.assertEqual(self.ex.ValidationError.http_status_code, 400)

    def test_custom_code_override(self):
        exc = self.ex.AIAssistantError("msg", code="CUSTOM_CODE")
        self.assertEqual(exc.error_code, "CUSTOM_CODE")

    def test_agent_not_found_includes_code_in_message(self):
        exc = self.ex.AgentNotFoundError("sales_agent")
        self.assertIn("sales_agent", str(exc))


if __name__ == "__main__":
    unittest.main()
