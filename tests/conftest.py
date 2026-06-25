"""
Shared test fixtures and Frappe mock infrastructure.

Tests that do NOT need a live Frappe site use the mock_frappe() helper
to stub the minimum required attributes. Tests that need the full Frappe
context (database, DocTypes) should be run with:

    bench --site mysite.localhost run-tests --app ai_assistant

Pure Python tests can be run with:

    python -m pytest tests/unit/
"""
from __future__ import annotations

import sys
import types
import unittest


def build_frappe_mock() -> types.ModuleType:
    """Return a minimal frappe stub for pure-Python unit tests."""
    frappe = types.ModuleType("frappe")
    frappe._ = lambda text, *a, **k: text
    frappe.log_error = lambda *a, **k: None
    frappe.whitelist = lambda *a, **k: (lambda fn: fn)
    frappe.throw = lambda msg, *a, **k: (_ for _ in ()).throw(Exception(msg))
    frappe.ValidationError = Exception
    frappe.PermissionError = PermissionError

    class _db:
        @staticmethod
        def sql(*a, **k):
            return [(0,)]
        @staticmethod
        def get_single_value(*a, **k):
            return None
        @staticmethod
        def exists(*a, **k):
            return True
        @staticmethod
        def commit():
            pass

    frappe.db = _db()
    frappe.session = types.SimpleNamespace(user="Administrator")
    frappe.local = None
    frappe.conf = types.SimpleNamespace(
        developer_mode=0,
        ai_debug_mode=0,
    )

    # Submodule stubs so `from frappe.utils import ...` works in pure-Python tests
    frappe_utils = types.ModuleType("frappe.utils")
    frappe_utils.now_datetime = lambda: None
    frappe_utils.add_days = lambda dt, n: dt
    frappe_utils.getdate = lambda dt=None: dt
    frappe_utils.nowdate = lambda: ""
    frappe_utils.format_date = lambda dt, fmt=None: str(dt)
    frappe.utils = frappe_utils
    sys.modules.setdefault("frappe.utils", frappe_utils)

    return frappe


def install_frappe_mock() -> types.ModuleType:
    """Install the frappe stub into sys.modules and return it."""
    mock = build_frappe_mock()
    sys.modules.setdefault("frappe", mock)
    return mock
