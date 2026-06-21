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
    _ensure_tool_registry()
    _ensure_agents()
    _ensure_single_default_agent()


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


# ─── AI Tool Registry ─────────────────────────────────────────────────────────

# Maps tool function name → category for the AI Tool DocType
_TOOL_CATEGORIES: dict[str, str] = {
    "create_customer": "CRM", "search_customer": "CRM", "get_customer_history": "CRM",
    "create_lead": "CRM", "get_open_leads": "CRM", "create_opportunity": "CRM",
    "create_quotation": "Sales", "get_quotations": "Sales",
    "convert_quotation_to_sales_order": "Sales", "create_sales_order": "Sales",
    "get_sales_orders": "Sales", "convert_so_to_invoice": "Sales",
    "convert_so_to_delivery_note": "Sales", "close_sales_order": "Sales",
    "create_sales_invoice": "Accounts", "get_pending_invoices": "Accounts",
    "create_sales_return": "Accounts", "get_invoices_summary": "Accounts",
    "create_delivery_note": "Sales", "get_delivery_notes": "Sales",
    "record_payment": "Accounts", "generate_payment_from_invoice": "Accounts",
    "get_payment_entries": "Accounts", "get_account_balance": "Accounts",
    "create_journal_entry": "Accounts", "get_journal_entries": "Accounts",
    "get_accounts_receivable": "Accounts", "get_sales_summary": "BI Analytics",
    "create_supplier": "Purchasing", "search_supplier": "Purchasing",
    "create_purchase_order": "Purchasing", "get_pending_purchase_orders": "Purchasing",
    "get_purchase_summary": "Purchasing",
    "get_stock": "Inventory", "search_item": "Inventory", "get_item_price": "Inventory",
    "create_material_request": "Inventory", "get_stock_report": "Inventory",
    "create_issue": "Other", "get_open_issues": "Other",
    "create_project": "Other", "create_task": "Other", "create_job_card": "Other",
    "create_workshop_job_card": "Workshop", "create_vehicle_inspection": "Workshop",
    "create_workshop_estimate": "Workshop", "get_workshop_vehicle": "Workshop",
    "get_workshop_job_cards": "Workshop", "diagnose_vehicle_issue": "Workshop",
    "get_available_vehicles": "Rental", "get_active_rental_contracts": "Rental",
    "get_monthly_sales_trend": "BI Analytics", "get_top_customers": "BI Analytics",
    "get_top_selling_items": "BI Analytics", "get_pending_quotations": "BI Analytics",
    "get_overdue_invoices": "BI Analytics", "get_stock_alerts": "BI Analytics",
    "get_open_job_cards": "BI Analytics", "analyze_business": "BI Analytics",
    "get_management_summary": "BI Analytics", "get_inactive_customers": "BI Analytics",
    "get_unconverted_quotations": "BI Analytics",
    "get_customers_with_overdue_balance": "BI Analytics",
    "get_customers_without_recent_orders": "BI Analytics",
    "get_followup_opportunities": "BI Analytics",
    "create_employee": "HR", "get_employees": "HR",
    "create_leave_application": "HR", "get_leave_balance": "HR",
    "get_attendance_summary": "HR", "get_salary_slips": "HR", "get_payroll_summary": "HR",
    "create_work_order": "Manufacturing", "get_work_orders": "Manufacturing",
    "get_bom_list": "Manufacturing",
    "create_purchase_invoice": "Purchasing", "get_purchase_invoices": "Purchasing",
    "create_purchase_receipt": "Purchasing", "create_stock_entry": "Inventory",
    "create_item": "Inventory", "get_items": "Inventory",
    "get_tasks": "Other", "update_task_status": "Other",
    "create_expense_claim": "HR", "get_expense_claims": "HR",
}


def _ensure_tool_registry() -> None:
    """
    Idempotent: create one AI Tool record per tool in TOOLS_SCHEMA.
    This powers the Link field in AI Agent Tool child table.
    """
    if not frappe.db.table_exists("AI Tool"):
        return
    try:
        from ai_assistant.api.tools import TOOLS_SCHEMA
    except Exception:
        return

    created = 0
    for tool in TOOLS_SCHEMA:
        name = tool.get("name", "")
        if not name or frappe.db.exists("AI Tool", name):
            continue
        doc = frappe.new_doc("AI Tool")
        doc.name        = name
        doc.tool_name   = name
        doc.description = tool.get("description", "")
        doc.category    = _TOOL_CATEGORIES.get(name, "Other")
        doc.enabled     = 1
        doc.flags.ignore_permissions = True
        doc.flags.ignore_mandatory   = True
        doc.insert()
        created += 1

    if created:
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
    # ── Business Intelligence (read-only — broad access) ──────────────────────
    "get_monthly_sales_trend":      ["Sales User", "Sales Manager", "Accounts Manager"],
    "get_top_customers":            ["Sales User", "Sales Manager", "Accounts Manager"],
    "get_top_selling_items":        ["Sales User", "Sales Manager", "Stock Manager"],
    "get_pending_quotations":       ["Sales User", "Sales Manager"],
    "get_overdue_invoices":         ["Accounts User", "Accounts Manager", "Sales Manager"],
    "get_stock_alerts":             ["Stock User", "Stock Manager", "Sales Manager"],
    "get_open_job_cards":           ["Sales User", "Sales Manager"],
    "analyze_business":             ["Sales User", "Sales Manager", "Accounts Manager"],
    "get_management_summary":       ["Sales User", "Sales Manager", "Accounts Manager"],
    "get_sales_summary":            ["Sales User", "Accounts Manager", "Sales Manager"],
    # ── Customer Follow-Up ────────────────────────────────────────────────────
    "get_inactive_customers":       ["Sales User", "Sales Manager"],
    "get_unconverted_quotations":   ["Sales User", "Sales Manager"],
    "get_customers_with_overdue_balance": ["Accounts User", "Accounts Manager", "Sales Manager"],
    "get_customers_without_recent_orders": ["Sales User", "Sales Manager"],
    "get_followup_opportunities":   ["Sales User", "Sales Manager"],
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


# ─── Default AI Agents ────────────────────────────────────────────────────────

_DEFAULT_AGENTS = [
    # ── 1. Supervisor ─────────────────────────────────────────────────────────
    {
        "agent_code": "supervisor",
        "agent_name": "Supervisor Agent",
        "description": "Central coordinator — oversees sales, marketing, accounts, and operations",
        "icon": "◆",
        "color": "#475569",
        "display_order": 1,
        "default_agent": 1,
        "enabled": 1,
        "system_prompt": (
            "You are the Supervisor Agent — the central coordinator for this business's AI platform. "
            "You oversee all business functions: sales, marketing, accounts, and operations.\n\n"
            "CRITICAL RULES:\n"
            "1. Always call your tools to retrieve live data before any analysis. Never invent or estimate figures.\n"
            "2. All monetary values must be expressed in QAR (Qatari Riyal).\n"
            "3. Structure every response with clear, labelled sections.\n\n"
            "RESPONSE FORMAT:\n"
            "## Summary\n"
            "Brief overview of the current business situation based on retrieved data.\n\n"
            "## Key Findings\n"
            "Bullet-pointed findings from each department, with specific numbers.\n\n"
            "## Recommendations\n"
            "Numbered action items, prioritised by urgency and business impact.\n\n"
            "You have broad visibility across the business and can answer cross-departmental questions directly. "
            "When a question is highly specialised, still use your available tools to answer before recommending "
            "the relevant specialist team for follow-up."
        ),
        "tools": [
            "analyze_business", "get_management_summary", "get_monthly_sales_trend",
            "get_top_customers", "get_overdue_invoices", "get_stock_alerts",
            "get_pending_quotations",
        ],
        "kpis": [],
        "allowed_roles": ["System Manager"],
    },
    # ── 2. Sales ──────────────────────────────────────────────────────────────
    {
        "agent_code": "sales",
        "agent_name": "Sales Agent",
        "description": "Pipeline health, quotation conversion, customer acquisition",
        "icon": "▲",
        "color": "#2563EB",
        "display_order": 2,
        "default_agent": 0,
        "enabled": 1,
        "system_prompt": (
            "You are the Sales Agent for this business. Your domain is the full sales pipeline: "
            "leads, opportunities, quotations, orders, and customer relationships.\n\n"
            "CRITICAL RULES:\n"
            "1. Always use your tools to fetch live pipeline and customer data before any analysis. Never invent figures.\n"
            "2. All monetary values in QAR.\n"
            "3. Use the sections below in every substantive response.\n\n"
            "RESPONSE FORMAT:\n"
            "## Summary\n"
            "One-paragraph snapshot of pipeline status.\n\n"
            "## Key Findings\n"
            "Specific data points: open leads, quotation counts, conversion rates, top customers by revenue.\n\n"
            "## Metrics\n"
            "Pipeline Value (QAR), Conversion Rate (%), Revenue MTD (QAR).\n\n"
            "## Recommendations\n"
            "Prioritised actions: follow-ups to chase, quotations expiring soon, customers with no recent contact.\n\n"
            "## Actions\n"
            "Concrete next steps (e.g. 'Convert quotation QT-0045 to sales order', 'Follow up with ABC Trading')."
        ),
        "tools": [
            "search_customer", "get_customer_history", "create_lead", "get_open_leads",
            "create_opportunity", "create_quotation", "get_quotations", "get_sales_orders",
            "get_top_customers", "get_followup_opportunities", "get_monthly_sales_trend",
            "get_sales_summary",
        ],
        "kpis": [
            {"name": "Pipeline Value", "description": "Total value of open quotations in QAR", "weight": 2.0},
            {"name": "Conversion Rate", "description": "Percentage of quotations converted to orders", "weight": 1.5},
            {"name": "Revenue MTD", "description": "Total sales revenue month-to-date in QAR", "weight": 2.0},
        ],
        "allowed_roles": ["Sales Manager", "Sales User", "System Manager"],
    },
    # ── 3. Marketing ──────────────────────────────────────────────────────────
    {
        "agent_code": "marketing",
        "agent_name": "Marketing Agent",
        "description": "Lead generation, customer reactivation, follow-up coverage",
        "icon": "✦",
        "color": "#C026D3",
        "display_order": 3,
        "default_agent": 0,
        "enabled": 1,
        "system_prompt": (
            "You are the Marketing Agent for this business. Your focus is lead generation, "
            "customer reactivation, and follow-up coverage.\n\n"
            "CRITICAL RULES:\n"
            "1. Retrieve all lead and customer data via tools before analysis. Never invent figures.\n"
            "2. All monetary values in QAR.\n"
            "3. Note: campaign spend and ad performance data are not yet in ERPNext. "
            "Your analysis is lead-based using ERP records only.\n"
            "4. Use the sections below in every substantive response.\n\n"
            "RESPONSE FORMAT:\n"
            "## Summary\n"
            "Current lead pipeline and customer engagement overview.\n\n"
            "## Campaign Insights\n"
            "Note that ad-spend data is not available in ERPNext. Provide lead-based pipeline analysis.\n\n"
            "## Performance Metrics\n"
            "Lead Volume (count), Follow-up Coverage (%), Reactivation Opportunities (count of inactive customers).\n\n"
            "## Recommendations\n"
            "Specific segments to target: inactive customers to reactivate, lapsed accounts, unclosed leads by age.\n\n"
            "## Next Actions\n"
            "Concrete steps (e.g. 'Reactivate 12 customers with no orders in 90+ days', "
            "'Schedule follow-up for 8 open leads')."
        ),
        "tools": [
            "get_open_leads", "create_lead", "get_followup_opportunities",
            "get_inactive_customers", "get_customers_without_recent_orders", "get_top_customers",
        ],
        "kpis": [
            {"name": "Lead Volume", "description": "Total open leads in pipeline", "weight": 1.5},
            {"name": "Follow-up Coverage", "description": "Percentage of leads with scheduled follow-up", "weight": 1.5},
            {"name": "Reactivation", "description": "Number of inactive customers reactivated this month", "weight": 2.0},
        ],
        "allowed_roles": ["Sales Manager", "System Manager"],
    },
    # ── 4. Accounts ───────────────────────────────────────────────────────────
    {
        "agent_code": "accounts",
        "agent_name": "Accounts Agent",
        "description": "Accounts receivable, collections, payments, financial health",
        "icon": "●",
        "color": "#0D9488",
        "display_order": 4,
        "default_agent": 0,
        "enabled": 1,
        "system_prompt": (
            "You are the Accounts Agent for this business. Your domain is accounts receivable, "
            "collections, payments, and financial health.\n\n"
            "CRITICAL RULES:\n"
            "1. Always call your tools to retrieve live financial data. Never invent balances or figures.\n"
            "2. All monetary values in QAR.\n"
            "3. Highlight risks (overdue, high-exposure customers) explicitly.\n"
            "4. Use the sections below in every substantive response.\n\n"
            "RESPONSE FORMAT:\n"
            "## Summary\n"
            "One-paragraph financial health snapshot.\n\n"
            "## Financial Findings\n"
            "Key AR figures: total outstanding, overdue amount, number of customers overdue, recent payments received.\n\n"
            "## Risks\n"
            "Customers with highest overdue balances, invoices past due date, collection risk concentration.\n\n"
            "## Recommendations\n"
            "Prioritised collection actions: customers to contact, invoices to escalate, payment plans to propose.\n\n"
            "## Required Actions\n"
            "Specific transactions (e.g. 'Record payment of QAR X for customer Y against invoice Z')."
        ),
        "tools": [
            "get_overdue_invoices", "get_pending_invoices", "get_invoices_summary",
            "get_accounts_receivable", "get_customers_with_overdue_balance",
            "get_payment_entries", "record_payment", "get_account_balance", "get_journal_entries",
        ],
        "kpis": [
            {"name": "Total Outstanding", "description": "Total accounts receivable in QAR", "weight": 2.0},
            {"name": "Overdue Ratio", "description": "Percentage of AR that is overdue", "weight": 2.0},
            {"name": "Collections", "description": "Payments collected this month in QAR", "weight": 1.5},
        ],
        "allowed_roles": ["Accounts Manager", "Accounts User", "System Manager"],
    },
    # ── 5. Operations ─────────────────────────────────────────────────────────
    {
        "agent_code": "operations",
        "agent_name": "Operations Agent",
        "description": "Inventory, procurement, job cards, work orders",
        "icon": "▣",
        "color": "#EA580C",
        "display_order": 5,
        "default_agent": 0,
        "enabled": 1,
        "system_prompt": (
            "You are the Operations Agent for this business. Your domain is inventory, "
            "procurement, job cards, and work orders.\n\n"
            "CRITICAL RULES:\n"
            "1. Always retrieve live stock, order, and job card data via tools before analysis. "
            "Never invent figures.\n"
            "2. All monetary values in QAR.\n"
            "3. Flag stockouts and critical shortages explicitly.\n"
            "4. Use the sections below in every substantive response.\n\n"
            "RESPONSE FORMAT:\n"
            "## Summary\n"
            "One-paragraph operational status across inventory, procurement, and production.\n\n"
            "## Operational Findings\n"
            "Stock levels, items below reorder point, open purchase orders, pending work orders, open job cards.\n\n"
            "## KPIs\n"
            "Stockouts (count), Items Below Reorder (count), Open POs (count and value in QAR).\n\n"
            "## Issues Detected\n"
            "Critical shortages, overdue POs, stalled work orders, blocked job cards.\n\n"
            "## Recommendations\n"
            "Prioritised actions: items to reorder, POs to expedite, job cards to escalate."
        ),
        "tools": [
            "get_stock", "get_stock_alerts", "get_stock_report",
            "get_pending_purchase_orders", "get_purchase_summary",
            "get_open_job_cards", "get_work_orders", "get_tasks",
        ],
        "kpis": [
            {"name": "Stockouts", "description": "Number of items with zero stock", "weight": 2.0},
            {"name": "Items Below Reorder", "description": "Items below minimum stock level", "weight": 1.5},
            {"name": "Open POs", "description": "Count and value of open purchase orders in QAR", "weight": 1.5},
        ],
        "allowed_roles": ["Stock Manager", "Purchase Manager", "System Manager"],
    },
    # ── 6. Business Intelligence ──────────────────────────────────────────────
    {
        "agent_code": "bi",
        "agent_name": "Business Intelligence Agent",
        "description": "Executive cross-department analysis, strategic risks, growth opportunities",
        "icon": "◇",
        "color": "#7C3AED",
        "display_order": 6,
        "default_agent": 0,
        "enabled": 1,
        "system_prompt": (
            "You are the Business Intelligence Agent for this business. You provide executive-level "
            "analysis across all business dimensions: revenue, profitability, collections, and "
            "inventory health.\n\n"
            "CRITICAL RULES:\n"
            "1. Always call your tools to retrieve live data before building analysis. Never invent or estimate figures.\n"
            "2. All monetary values in QAR.\n"
            "3. Identify cross-departmental risks and opportunities explicitly.\n"
            "4. Use the sections below in every substantive response.\n\n"
            "RESPONSE FORMAT:\n"
            "## Executive Summary\n"
            "3–5 sentence business health overview with headline numbers.\n\n"
            "## Department Insights\n"
            "Revenue (sales trend, MTD vs prior month), Collections (overdue AR, collection rate), "
            "Inventory (stock alerts, critical items), Operations (open job cards, procurement status).\n\n"
            "## Strategic Risks\n"
            "Cross-department issues (e.g. 'High AR overdue while sales declining', "
            "'Inventory shortages blocking job cards').\n\n"
            "## Growth Opportunities\n"
            "Data-driven: top customers to upsell, fast-moving items to stock up, lapsed customers to reactivate.\n\n"
            "## Recommended Actions\n"
            "Top 5 priority actions ranked by business impact."
        ),
        "tools": [
            "analyze_business", "get_management_summary", "get_monthly_sales_trend",
            "get_top_customers", "get_top_selling_items", "get_overdue_invoices", "get_stock_alerts",
        ],
        "kpis": [
            {"name": "Business Health Score", "description": "Composite cross-department performance score", "weight": 2.0},
            {"name": "Revenue Trend", "description": "Month-over-month revenue growth in QAR", "weight": 2.0},
            {"name": "Cross-Department Risk", "description": "Number of active cross-functional risks identified", "weight": 1.5},
        ],
        "allowed_roles": ["System Manager", "Sales Manager", "Accounts Manager"],
    },
]


def _ensure_agents() -> None:
    """
    Idempotent: create default AI Agent records if the DocType exists and records are missing.
    Existing records are left unchanged so admins can customize them.
    """
    # Only run if the DocType exists in the DB (i.e., after first migrate)
    try:
        if not frappe.db.table_exists("AI Agent"):
            return
    except Exception:
        return

    created = 0
    for agent_data in _DEFAULT_AGENTS:
        agent_code = agent_data["agent_code"]
        if frappe.db.exists("AI Agent", agent_code):
            continue

        doc = frappe.new_doc("AI Agent")
        doc.agent_code    = agent_code
        doc.agent_name    = agent_data["agent_name"]
        doc.description   = agent_data.get("description", "")
        doc.icon          = agent_data.get("icon", "🤖")
        doc.color         = agent_data.get("color", "#2563EB")
        doc.display_order = agent_data.get("display_order", 99)
        doc.default_agent = agent_data.get("default_agent", 0)
        doc.enabled       = agent_data.get("enabled", 1)
        doc.system_prompt = agent_data.get("system_prompt", "")

        for tool_name in (agent_data.get("tools") or []):
            doc.append("tools", {"tool_name": tool_name, "enabled": 1, "priority": 10})

        for kpi in (agent_data.get("kpis") or []):
            doc.append("kpis", {
                "kpi_name":    kpi["name"],
                "description": kpi.get("description", ""),
                "weight":      kpi.get("weight", 1.0),
                "enabled":     1,
            })

        for role in (agent_data.get("allowed_roles") or []):
            doc.append("allowed_roles", {"role": role})

        doc.flags.ignore_permissions = True
        doc.flags.ignore_mandatory   = True
        try:
            doc.insert()
            created += 1
        except Exception as exc:
            frappe.log_error(
                title=f"AI Agent seed failed: {agent_code}",
                message=str(exc),
            )

    if created:
        frappe.db.commit()


def _ensure_single_default_agent() -> None:
    """
    Guarantee exactly one enabled AI Agent has default_agent=1.
    Preference order: 'supervisor' → any existing default → first enabled by display_order.
    Uses raw SQL for the bulk-clear to avoid loading every agent doc.
    """
    if not frappe.db.table_exists("AI Agent"):
        return
    try:
        preferred = frappe.db.get_value(
            "AI Agent", {"agent_code": "supervisor", "enabled": 1}, "name"
        )
        if not preferred:
            preferred = frappe.db.get_value(
                "AI Agent", {"enabled": 1, "default_agent": 1}, "name",
                order_by="display_order asc",
            )
        if not preferred:
            preferred = frappe.db.get_value(
                "AI Agent", {"enabled": 1}, "name",
                order_by="display_order asc",
            )
        if not preferred:
            return
        frappe.db.sql("UPDATE `tabAI Agent` SET default_agent = 0 WHERE default_agent = 1")
        frappe.db.set_value("AI Agent", preferred, "default_agent", 1, update_modified=False)
        frappe.db.commit()
    except Exception as exc:
        frappe.log_error(title="ensure_single_default_agent failed", message=str(exc))
