"""Unit tests for utils/helpers.py — no Frappe dependency."""
import sys
import unittest


class TestUtilsHelpers(unittest.TestCase):

    def setUp(self):
        sys.path.insert(0, ".")
        from ai_assistant.utils import helpers
        self.h = helpers

    def test_clamp_mid_value(self):
        self.assertEqual(self.h.clamp(5, 0, 10), 5)

    def test_clamp_below_min(self):
        self.assertEqual(self.h.clamp(-1, 0, 10), 0)

    def test_clamp_above_max(self):
        self.assertEqual(self.h.clamp(20, 0, 10), 10)

    def test_safe_float_valid(self):
        self.assertAlmostEqual(self.h.safe_float("3.14"), 3.14)

    def test_safe_float_invalid(self):
        self.assertEqual(self.h.safe_float("abc"), 0.0)

    def test_safe_float_none(self):
        self.assertEqual(self.h.safe_float(None), 0.0)

    def test_safe_int_valid(self):
        self.assertEqual(self.h.safe_int("42"), 42)

    def test_safe_int_invalid(self):
        self.assertEqual(self.h.safe_int("xyz", default=99), 99)

    def test_truncate_short_string(self):
        self.assertEqual(self.h.truncate("hello", 100), "hello")

    def test_truncate_long_string(self):
        result = self.h.truncate("a" * 1000, 10)
        self.assertEqual(len(result), 10)

    def test_truncate_none(self):
        self.assertEqual(self.h.truncate(None), "")

    def test_format_currency_default(self):
        result = self.h.format_currency(1234.5)
        self.assertIn("1,234.50", result)
        self.assertIn("QAR", result)

    def test_format_currency_none(self):
        result = self.h.format_currency(None)
        self.assertIn("0.00", result)

    def test_pct_change_positive(self):
        self.assertAlmostEqual(self.h.pct_change(110, 100), 10.0)

    def test_pct_change_negative(self):
        self.assertAlmostEqual(self.h.pct_change(90, 100), -10.0)

    def test_pct_change_zero_previous(self):
        self.assertIsNone(self.h.pct_change(100, 0))

    def test_normalize_to_100_midpoint(self):
        self.assertEqual(self.h.normalize_to_100(0.5, 0.0, 1.0), 50)

    def test_normalize_to_100_clamps_above(self):
        self.assertEqual(self.h.normalize_to_100(2.0, 0.0, 1.0), 100)

    def test_normalize_to_100_same_low_high(self):
        self.assertEqual(self.h.normalize_to_100(0.5, 0.5, 0.5), 0)


if __name__ == "__main__":
    unittest.main()
