"""
setup.py — Post-install / post-migrate hooks for AI Assistant.
Creates the AI Assistant Dashboard and Number Cards if they don't exist.
"""

from __future__ import annotations
import frappe


def create_dashboard():
    """Create the AI Assistant Dashboard with Number Cards. Called after migrate."""
    _ensure_number_cards()
    _ensure_dashboard()


def _ensure_number_cards():
    """Idempotent: create Number Card documents if not present."""
    cards = [
        ("AI - Sales This Month",    "Sales This Month",    "ai_assistant.api.dashboard.get_kpi_sales_month",       "#7C3AED"),
        ("AI - Pending Quotations",  "Pending Quotations",  "ai_assistant.api.dashboard.get_kpi_pending_quotations", "#F59E0B"),
        ("AI - Overdue Invoices",    "Overdue Invoices",    "ai_assistant.api.dashboard.get_kpi_overdue_count",      "#EF4444"),
        ("AI - Low Stock Items",     "Low Stock Items",     "ai_assistant.api.dashboard.get_kpi_low_stock",          "#F97316"),
        ("AI - New Customers",       "New Customers",       "ai_assistant.api.dashboard.get_kpi_new_customers",      "#10B981"),
        ("AI - Open Job Cards",      "Open Job Cards",      "ai_assistant.api.dashboard.get_kpi_open_jobs",          "#3B82F6"),
    ]
    for name, label, method, color in cards:
        if frappe.db.exists("Number Card", name):
            continue
        doc = frappe.new_doc("Number Card")
        doc.name    = name
        doc.label   = label
        doc.method  = method
        doc.color   = color
        doc.is_public = 1
        doc.module  = "AI Assistant"
        doc.flags.ignore_permissions = True
        doc.flags.ignore_mandatory   = True
        doc.insert()
    frappe.db.commit()


def _ensure_dashboard():
    """Idempotent: create the AI Assistant Dashboard if not present."""
    if frappe.db.exists("Dashboard", "AI Assistant Dashboard"):
        return
    doc = frappe.new_doc("Dashboard")
    doc.name             = "AI Assistant Dashboard"
    doc.dashboard_name   = "AI Assistant Dashboard"
    doc.module           = "AI Assistant"
    doc.is_public        = 1
    for card_name in [
        "AI - Sales This Month",
        "AI - Pending Quotations",
        "AI - Overdue Invoices",
        "AI - Low Stock Items",
        "AI - New Customers",
        "AI - Open Job Cards",
    ]:
        doc.append("cards", {"card": card_name})
    doc.flags.ignore_permissions = True
    doc.flags.ignore_mandatory   = True
    doc.insert()
    frappe.db.commit()
