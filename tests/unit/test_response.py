"""Unit tests for core/response.py — no Frappe dependency."""
import sys
import time
import unittest


class TestAPIResponse(unittest.TestCase):

    def setUp(self):
        sys.path.insert(0, ".")
        from ai_assistant.core import response as r
        self.r = r

    def test_ok_sets_success_true(self):
        result = self.r.ok("Done.")
        self.assertTrue(result["success"])
        self.assertTrue(result["ok"])

    def test_error_sets_success_false(self):
        result = self.r.error("Something broke.")
        self.assertFalse(result["success"])
        self.assertFalse(result["ok"])

    def test_ok_includes_message(self):
        result = self.r.ok("Task complete.")
        self.assertEqual(result["message"], "Task complete.")

    def test_error_shows_user_message_not_internal(self):
        secret = "SELECT * FROM __Auth"
        result = self.r.error(secret, user_message="An error occurred.")
        self.assertEqual(result["message"], "An error occurred.")
        self.assertNotIn(secret, result["message"])

    def test_ok_merges_dict_data_at_top_level(self):
        result = self.r.ok("OK", {"key": "value"})
        self.assertEqual(result["key"], "value")

    def test_ok_wraps_non_dict_data(self):
        result = self.r.ok("OK", ["item1", "item2"])
        self.assertEqual(result["data"], ["item1", "item2"])

    def test_ok_no_warnings_by_default(self):
        result = self.r.ok("OK")
        self.assertNotIn("warnings", result)

    def test_ok_includes_warnings_when_provided(self):
        result = self.r.ok("OK", warnings=["Watch out"])
        self.assertIn("warnings", result)
        self.assertEqual(result["warnings"], ["Watch out"])

    def test_error_includes_recovery(self):
        result = self.r.error("Err", recovery="Try again.")
        self.assertEqual(result["recovery"], "Try again.")

    def test_request_timer_elapsed_is_positive(self):
        timer = self.r.RequestTimer()
        time.sleep(0.005)
        self.assertGreater(timer.elapsed(), 0)

    def test_request_timer_attach_sets_key(self):
        timer = self.r.RequestTimer()
        response = {"success": True}
        timer.attach(response)
        self.assertIn("execution_time", response)
        self.assertGreaterEqual(response["execution_time"], 0)

    def test_from_exception_with_ai_error(self):
        from ai_assistant.core.exceptions import ProviderError
        exc = ProviderError("internal detail", user_message="Service unavailable.")
        result = self.r.from_exception(exc)
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "Service unavailable.")
        self.assertNotIn("internal detail", result["message"])

    def test_from_exception_with_generic_error(self):
        exc = RuntimeError("raw system error")
        result = self.r.from_exception(exc)
        self.assertFalse(result["success"])
        self.assertNotIn("raw system error", result["message"])

    def test_response_has_request_id(self):
        result = self.r.ok("OK")
        self.assertIn("request_id", result)
        self.assertGreater(len(result["request_id"]), 0)


if __name__ == "__main__":
    unittest.main()
