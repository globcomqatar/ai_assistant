"""
setup.py — Post-install / post-migrate hooks for AI Assistant.
Creates the AI Assistant Dashboard and Number Cards if they don't exist.
"""

from __future__ import annotations
import frappe


def create_dashboard():
    """Create the AI Assistant Dashboard with Number Cards. Called after migrate."""
    _fix_workspace_title()
    _ensure_number_cards()
    _ensure_dashboard_charts()
    _ensure_dashboard()
    create_default_tool_permissions()


def _fix_workspace_title():
    """Patch: workspace JSON imported without title causes all sidebar items to go blank.
    frappe.router.slug(null) throws TypeError; make_sidebar() crashes before removing
    the skeleton, so every workspace in the sidebar stays gray forever.
    """
    if not frappe.db.exists("Workspace", "AI Assistant"):
        return
    current = frappe.db.get_value("Workspace", "AI Assistant", "title")
    if not current:
        frappe.db.set_value(
            "Workspace", "AI Assistant", "title", "AI Assistant", update_modified=False
        )
        frappe.db.commit()


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
            frappe.db.set_value("Number Card", name, "type", "Custom", update_modified=False)
            continue
        doc = frappe.new_doc("Number Card")
        doc.name      = name
        doc.label     = label
        doc.type      = "Custom"
        doc.method    = method
        doc.color     = color
        doc.is_public = 1
        doc.module    = "AI Assistant"
        doc.flags.ignore_permissions = True
        doc.flags.ignore_mandatory   = True
        doc.insert()
    frappe.db.commit()


def _ensure_dashboard_charts():
    """Idempotent: create Dashboard Chart documents for AI usage analytics."""
    charts = [
        {
            "name": "AI - Daily Usage Trend",
            "chart_name": "AI - Daily Usage Trend",
            "chart_type": "Count",
            "document_type": "AI Usage Log",
            "based_on": "creation",
            "time_interval": "Daily",
            "timespan": "Last Month",
            "color": "#7C3AED",
            "is_public": 1,
            "module": "AI Assistant",
            "type": "Line",
            "filters_json": "[]",
        },
        {
            "name": "AI - Usage by Status",
            "chart_name": "AI - Usage by Status",
            "chart_type": "Count",
            "document_type": "AI Usage Log",
            "based_on": "creation",
            "group_by_type": "Count",
            "group_by_based_on": "status",
            "time_interval": "Monthly",
            "timespan": "Last Year",
            "color": "#10B981",
            "is_public": 1,
            "module": "AI Assistant",
            "type": "Bar",
            "filters_json": "[]",
        },
    ]
    for data in charts:
        if frappe.db.exists("Dashboard Chart", data["name"]):
            continue
        doc = frappe.new_doc("Dashboard Chart")
        for k, v in data.items():
            setattr(doc, k, v)
        doc.flags.ignore_permissions = True
        doc.flags.ignore_mandatory   = True
        try:
            doc.insert()
        except Exception:
            pass
    frappe.db.commit()


def _ensure_dashboard():
    """Idempotent: create the AI Assistant Dashboard if not present."""
    exists = frappe.db.exists("Dashboard", "AI Assistant Dashboard")
    if exists:
        doc = frappe.get_doc("Dashboard", "AI Assistant Dashboard")
    else:
        doc = frappe.new_doc("Dashboard")
        doc.name           = "AI Assistant Dashboard"
        doc.dashboard_name = "AI Assistant Dashboard"
        doc.module         = "AI Assistant"

    existing_cards  = [c.card  for c in doc.cards]
    existing_charts = [c.chart for c in doc.charts]

    for card_name in [
        "AI - Sales This Month",
        "AI - Pending Quotations",
        "AI - Overdue Invoices",
        "AI - Low Stock Items",
        "AI - New Customers",
        "AI - Open Job Cards",
    ]:
        if card_name not in existing_cards:
            doc.append("cards", {"card": card_name})

    for chart_name in ["AI - Daily Usage Trend", "AI - Usage by Status"]:
        if chart_name not in existing_charts:
            doc.append("charts", {"chart": chart_name, "width": "Full"})

    doc.flags.ignore_permissions = True
    doc.flags.ignore_mandatory   = True
    if exists:
        doc.save()
    else:
        doc.insert()
    frappe.db.commit()


# ─── Default Tool Permissions ─────────────────────────────────────────────────

# Maps each tool to the ERPNext roles that may use it.
# System Manager always gets all enabled tools regardless of this table.
# Roles listed here follow standard ERPNext v15 role names.
_DEFAULT_TOOL_ROLES: dict[str, list[str]] = {
    # ── Customers & CRM ──────────────────────────────────────────────────────
    "create_customer":              ["Sales User", "Sales Manager"],
    "search_customer":              ["Sales User", "Sales Manager", "Accounts User", "Accounts Manager"],
    "get_customer_history":         ["Sales User", "Sales Manager", "Accounts User", "Accounts Manager"],
    "create_lead":                  ["Sales User", "Sales Manager"],
    "get_open_leads":               ["Sales User", "Sales Manager"],
    "create_opportunity":           ["Sales User", "Sales Manager"],
    # ── Quotations ───────────────────────────────────────────────────────────
    "create_quotation":             ["Sales User", "Sales Manager"],
    "get_quotations":               ["Sales User", "Sales Manager"],
    "convert_quotation_to_sales_order": ["Sales Manager"],
    # ── Sales Orders ─────────────────────────────────────────────────────────
    "create_sales_order":           ["Sales Manager"],
    "get_sales_orders":             ["Sales User", "Sales Manager"],
    "convert_so_to_invoice":        ["Accounts Manager"],
    "convert_so_to_delivery_note":  ["Stock Manager"],
    "close_sales_order":            ["Sales Manager"],
    # ── Sales Invoices ───────────────────────────────────────────────────────
    "create_sales_invoice":         ["Accounts Manager"],
    "get_pending_invoices":         ["Accounts User", "Accounts Manager", "Sales Manager"],
    "create_sales_return":          ["Accounts Manager"],
    "get_invoices_summary":         ["Accounts User", "Accounts Manager", "Sales Manager"],
    # ── Delivery Notes ───────────────────────────────────────────────────────
    "create_delivery_note":         ["Stock Manager"],
    "get_delivery_notes":           ["Stock User", "Stock Manager", "Sales Manager"],
    # ── Payments ─────────────────────────────────────────────────────────────
    "record_payment":               ["Accounts Manager"],
    "generate_payment_from_invoice": ["Accounts Manager"],
    "get_payment_entries":          ["Accounts User", "Accounts Manager"],
    # ── Finance / Accounts ───────────────────────────────────────────────────
    "get_account_balance":          ["Accounts User", "Accounts Manager"],
    "create_journal_entry":         ["Accounts Manager"],
    "get_journal_entries":          ["Accounts User", "Accounts Manager"],
    "get_accounts_receivable":      ["Accounts User", "Accounts Manager", "Sales Manager"],
    "get_sales_summary":            ["Accounts Manager", "Sales Manager"],
    # ── Suppliers & Purchasing ───────────────────────────────────────────────
    "create_supplier":              ["Purchase Manager"],
    "search_supplier":              ["Purchase User", "Purchase Manager"],
    "create_purchase_order":        ["Purchase Manager"],
    "get_pending_purchase_orders":  ["Purchase User", "Purchase Manager"],
    "get_purchase_summary":         ["Purchase Manager", "Accounts Manager"],
    # ── Inventory ────────────────────────────────────────────────────────────
    "get_stock":                    ["Stock User", "Stock Manager", "Purchase Manager", "Sales Manager"],
    "search_item":                  ["Sales User", "Sales Manager", "Purchase User", "Purchase Manager", "Stock User", "Stock Manager"],
    "get_item_price":               ["Sales User", "Sales Manager"],
    "create_material_request":      ["Purchase Manager", "Stock Manager"],
    "get_stock_report":             ["Stock User", "Stock Manager"],
    # ── Support & Projects ───────────────────────────────────────────────────
    "create_issue":                 ["Support Team", "Sales User", "Sales Manager"],
    "get_open_issues":              ["Support Team", "Sales Manager"],
    "create_project":               ["Projects Manager"],
    "create_task":                  ["Employee", "Projects Manager"],
    "create_job_card":              ["Manufacturing Manager", "Projects Manager"],
    # ── Auto Workshop ────────────────────────────────────────────────────────
    "create_workshop_job_card":     ["Sales User", "Sales Manager"],
    "create_vehicle_inspection":    ["Sales User", "Sales Manager"],
    "create_workshop_estimate":     ["Sales User", "Sales Manager"],
    "get_workshop_vehicle":         ["Sales User", "Sales Manager"],
    "get_workshop_job_cards":       ["Sales User", "Sales Manager"],
    # ── Car Rental ───────────────────────────────────────────────────────────
    "get_available_vehicles":       ["Sales User", "Sales Manager"],
    "get_active_rental_contracts":  ["Sales User", "Sales Manager", "Accounts Manager"],
    # ── Business Intelligence ─────────────────────────────────────────────────
    "get_monthly_sales_trend":      ["Sales Manager", "Accounts Manager"],
    "get_top_customers":            ["Sales Manager", "Accounts Manager"],
    "get_top_selling_items":        ["Sales Manager", "Stock Manager"],
    "get_pending_quotations":       ["Sales User", "Sales Manager"],
    "get_overdue_invoices":         ["Accounts User", "Accounts Manager", "Sales Manager"],
    "get_stock_alerts":             ["Stock User", "Stock Manager"],
    "get_open_job_cards":           ["Sales Manager"],
    "analyze_business":             ["Sales Manager", "Accounts Manager"],
    "get_management_summary":       ["Sales Manager", "Accounts Manager"],
    # ── Customer Follow-Up ────────────────────────────────────────────────────
    "get_inactive_customers":       ["Sales Manager"],
    "get_unconverted_quotations":   ["Sales Manager"],
    "get_customers_with_overdue_balance": ["Accounts Manager", "Sales Manager"],
    "get_customers_without_recent_orders": ["Sales Manager"],
    "get_followup_opportunities":   ["Sales Manager"],
    # ── Vehicle Diagnostics ───────────────────────────────────────────────────
    "diagnose_vehicle_issue":       ["Sales User", "Sales Manager"],
    # ── HR & Employees ────────────────────────────────────────────────────────
    "create_employee":              ["HR Manager"],
    "get_employees":                ["HR User", "HR Manager"],
    "create_leave_application":     ["Employee", "HR User", "HR Manager"],
    "get_leave_balance":            ["Employee", "HR User", "HR Manager"],
    "get_attendance_summary":       ["HR User", "HR Manager"],
    # ── Payroll ───────────────────────────────────────────────────────────────
    "get_salary_slips":             ["HR Manager", "Accounts Manager"],
    "get_payroll_summary":          ["HR Manager", "Accounts Manager"],
    # ── Manufacturing ─────────────────────────────────────────────────────────
    "create_work_order":            ["Manufacturing Manager"],
    "get_work_orders":              ["Manufacturing User", "Manufacturing Manager"],
    "get_bom_list":                 ["Manufacturing User", "Manufacturing Manager", "Stock Manager"],
    # ── Purchase Invoice & Receipt ────────────────────────────────────────────
    "create_purchase_invoice":      ["Accounts Manager", "Purchase Manager"],
    "get_purchase_invoices":        ["Accounts User", "Accounts Manager", "Purchase Manager"],
    "create_purchase_receipt":      ["Purchase Manager", "Stock Manager"],
    # ── Stock Operations ──────────────────────────────────────────────────────
    "create_stock_entry":           ["Stock Manager"],
    # ── Item Management ───────────────────────────────────────────────────────
    "create_item":                  ["Stock Manager", "Purchase Manager"],
    "get_items":                    ["Sales User", "Sales Manager", "Stock User", "Stock Manager",
                                     "Purchase User", "Purchase Manager"],
    # ── Task Management ───────────────────────────────────────────────────────
    "get_tasks":                    ["Employee", "Projects Manager"],
    "update_task_status":           ["Employee", "Projects Manager"],
    # ── Expense Claims ────────────────────────────────────────────────────────
    "create_expense_claim":         ["Employee", "HR User", "HR Manager"],
    "get_expense_claims":           ["HR User", "HR Manager", "Accounts Manager"],
}


def create_default_tool_permissions() -> None:
    """
    Idempotent: create one AI Tool Permission record per tool with sensible
    role defaults.  Existing records are left unchanged so admins can customize.
    """
    try:
        from ai_assistant.api.tools import TOOLS_SCHEMA
        descriptions = {t["name"]: t.get("description", "") for t in TOOLS_SCHEMA}
    except Exception:
        descriptions = {}

    created = 0
    for tool_name, roles in _DEFAULT_TOOL_ROLES.items():
        if frappe.db.exists("AI Tool Permission", tool_name):
            continue

        doc = frappe.new_doc("AI Tool Permission")
        doc.tool_name = tool_name
        doc.enabled = 1
        doc.description = descriptions.get(tool_name, "")
        for role in roles:
            doc.append("allowed_roles", {"role": role})
        doc.flags.ignore_permissions = True
        doc.flags.ignore_mandatory = True
        doc.insert()
        created += 1

    if created:
        frappe.db.commit()
