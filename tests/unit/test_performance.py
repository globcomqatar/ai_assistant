"""Unit tests for core/performance.py — no Frappe dependency."""
import sys
import time
import types
import unittest


def _install_minimal_stubs():
    """Install the minimum stubs so performance.py can import."""
    import sys, types

    frappe = types.ModuleType("frappe")
    frappe.logger = lambda *a, **k: _NullLogger()
    frappe.conf = types.SimpleNamespace(developer_mode=0, ai_debug_mode=0)
    frappe.local = None
    sys.modules.setdefault("frappe", frappe)

    # config.settings needs no frappe
    sys.path.insert(0, ".")


class _NullLogger:
    def info(self, *a, **k): pass
    def debug(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass


class TestPerformanceTracker(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _install_minimal_stubs()
        from ai_assistant.core.performance import PerformanceTracker, Timing
        cls.PerformanceTracker = PerformanceTracker
        cls.Timing = Timing

    def test_stop_without_start_returns_zero(self):
        tracker = self.PerformanceTracker()
        self.assertEqual(tracker.stop("never_started"), 0.0)

    def test_start_stop_returns_positive_elapsed(self):
        tracker = self.PerformanceTracker()
        tracker.start("step")
        time.sleep(0.005)
        elapsed = tracker.stop("step")
        self.assertGreater(elapsed, 0)

    def test_total_sums_all_timings(self):
        tracker = self.PerformanceTracker()
        tracker.start("a")
        tracker.stop("a")
        tracker.start("b")
        tracker.stop("b")
        self.assertGreaterEqual(tracker.total(), 0)
        self.assertEqual(len(tracker.all_timings()), 2)

    def test_summary_has_expected_keys(self):
        tracker = self.PerformanceTracker()
        tracker.start("x")
        tracker.stop("x")
        summary = tracker.summary()
        self.assertIn("total_s", summary)
        self.assertIn("steps", summary)

    def test_timing_elapsed_ms(self):
        t = self.Timing(name="test", elapsed=1.5)
        self.assertAlmostEqual(t.elapsed_ms, 1500.0)


class TestTimedContextManager(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _install_minimal_stubs()

    def test_timed_runs_without_error(self):
        from ai_assistant.core.performance import timed
        with timed("test_op", log=False):
            time.sleep(0.002)


if __name__ == "__main__":
    unittest.main()
