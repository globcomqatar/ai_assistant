"""
dashboard.py — Whitelisted KPI methods for Number Card widgets
in the AI Assistant Workspace dashboard.

Each function returns a single number (int or float).
"""

from __future__ import annotations

import frappe
from frappe.utils import today, get_first_day, flt


@frappe.whitelist()
def get_kpi_sales_month() -> float:
    """Total sales (grand_total) for the current calendar month."""
    m_start = str(get_first_day(today()))
    rows = frappe.db.sql(
        "SELECT COALESCE(SUM(grand_total), 0) FROM `tabSales Invoice` "
        "WHERE docstatus=1 AND posting_date >= %s",
        (m_start,),
    )
    return float(rows[0][0]) if rows else 0.0


@frappe.whitelist()
def get_kpi_overdue_count() -> int:
    """Number of sales invoices past due date with outstanding balance."""
    return frappe.db.count("Sales Invoice", {
        "docstatus": 1,
        "outstanding_amount": [">", 0],
        "due_date": ["<", today()],
    })


@frappe.whitelist()
def get_kpi_low_stock() -> int:
    """Number of items at or below their safety stock level."""
    rows = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabBin` b
        INNER JOIN `tabItem` i ON i.name = b.item_code
        WHERE i.is_stock_item = 1
          AND i.safety_stock > 0
          AND b.actual_qty <= i.safety_stock
          AND i.disabled = 0
    """)
    return int(rows[0][0]) if rows else 0


@frappe.whitelist()
def get_kpi_open_jobs() -> int:
    """Number of open/in-progress Workshop Job Cards (or 0 if module absent)."""
    if frappe.db.exists("DocType", "Workshop Job Card"):
        try:
            return frappe.db.count("Workshop Job Card",
                                   {"status": ["in", ["Open", "In Progress"]]})
        except Exception:
            pass
    return 0


@frappe.whitelist()
def get_kpi_pending_quotations() -> int:
    """Number of open/draft quotations not yet converted."""
    return frappe.db.count("Quotation", {
        "docstatus": ["in", [0, 1]],
        "status": ["in", ["Open", "Draft"]],
    })


@frappe.whitelist()
def get_kpi_new_customers() -> int:
    """Number of new Customer records created this month."""
    m_start = str(get_first_day(today()))
    return frappe.db.count("Customer", {"creation": [">=", m_start]})
