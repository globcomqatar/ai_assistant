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
    {
        "agent_code": "general",
        "agent_name": "General ERP Assistant",
        "description": "General ERP support for all modules",
        "icon": "🤖",
        "color": "#6366F1",
        "display_order": 1,
        "default_agent": 1,
        "enabled": 1,
        "system_prompt": (
            "You are a General ERP Assistant for a business using Frappe/ERPNext. "
            "You help users with all ERP modules including sales, purchasing, inventory, "
            "accounts, HR, and manufacturing. Provide clear, accurate answers and always "
            "use the appropriate tools to fetch or create data. Be concise and professional."
        ),
        "tools": [],
        "kpis": [],
        "allowed_roles": [],
    },
    {
        "agent_code": "sales_manager",
        "agent_name": "Sales Manager",
        "description": "Revenue growth, quotation conversion, customer acquisition",
        "icon": "📈",
        "color": "#10B981",
        "display_order": 2,
        "default_agent": 0,
        "enabled": 1,
        "system_prompt": (
            "You are a Sales Manager AI Assistant. Your primary focus is revenue growth, "
            "quotation conversion, and customer acquisition. Analyze sales trends, monitor "
            "pending quotations, identify top customers, and recommend actions to close deals. "
            "Always provide actionable insights with specific numbers and trends. "
            "Prioritize follow-up opportunities and highlight expiring quotations."
        ),
        "tools": [
            "get_sales_summary", "get_monthly_sales_trend", "get_pending_quotations",
            "get_top_customers", "create_quotation", "search_customer",
            "get_top_selling_items", "get_invoices_summary", "get_quotations",
            "convert_quotation_to_sales_order",
        ],
        "kpis": [
            {"name": "Monthly Revenue", "description": "Total sales revenue for the current month", "weight": 2.0},
            {"name": "Quotation Conversion Rate", "description": "Percentage of quotations converted to orders", "weight": 1.5},
            {"name": "Customer Growth", "description": "New customers acquired this month", "weight": 1.0},
            {"name": "Sales Growth", "description": "Month-over-month sales growth percentage", "weight": 1.5},
        ],
        "allowed_roles": ["Sales Manager", "Sales User"],
    },
    {
        "agent_code": "accounts_manager",
        "agent_name": "Accounts Manager",
        "description": "Finance, collections, receivables, cash flow",
        "icon": "💰",
        "color": "#F59E0B",
        "display_order": 3,
        "default_agent": 0,
        "enabled": 1,
        "system_prompt": (
            "You are an Accounts Manager AI Assistant. Your focus is financial health, "
            "collections, accounts receivable, and cash flow management. Monitor overdue "
            "invoices, identify collection priorities, track payment trends, and provide "
            "financial summaries. Always highlight customers with overdue balances and "
            "recommend collection actions. Provide precise financial figures."
        ),
        "tools": [
            "get_overdue_invoices", "get_accounts_receivable", "get_invoices_summary",
            "get_payment_entries", "get_sales_summary", "get_customers_with_overdue_balance",
            "record_payment", "create_journal_entry", "get_journal_entries",
            "get_account_balance",
        ],
        "kpis": [
            {"name": "Accounts Receivable", "description": "Total outstanding receivables", "weight": 2.0},
            {"name": "Collection Rate", "description": "Percentage of invoices collected on time", "weight": 1.5},
            {"name": "Cash Flow", "description": "Net cash position and trends", "weight": 2.0},
            {"name": "Outstanding Balance", "description": "Total overdue amount across all customers", "weight": 1.5},
        ],
        "allowed_roles": ["Accounts Manager", "Accounts User"],
    },
    {
        "agent_code": "workshop_advisor",
        "agent_name": "Workshop Service Advisor",
        "description": "Workshop operations, diagnostics, job card management",
        "icon": "🔧",
        "color": "#EF4444",
        "display_order": 4,
        "default_agent": 0,
        "enabled": 1,
        "system_prompt": (
            "You are a Workshop Service Advisor AI. Your expertise is automotive workshop "
            "operations, vehicle diagnostics, and job card management. Help diagnose vehicle "
            "issues, manage open job cards, track technician workload, and identify delayed "
            "jobs. Provide technical recommendations and help create job cards, inspections, "
            "and estimates efficiently. Always check parts availability in ERP inventory."
        ),
        "tools": [
            "diagnose_vehicle_issue", "get_open_job_cards", "create_job_card",
            "get_workshop_vehicle", "get_workshop_job_cards", "create_workshop_job_card",
            "create_vehicle_inspection", "create_workshop_estimate", "get_stock", "search_item",
        ],
        "kpis": [
            {"name": "Open Job Cards", "description": "Number of currently open job cards", "weight": 1.5},
            {"name": "Delayed Jobs", "description": "Jobs overdue by more than 2 days", "weight": 2.0},
            {"name": "Technician Utilization", "description": "Percentage of technician capacity in use", "weight": 1.0},
            {"name": "Service Completion Rate", "description": "Jobs completed on time vs total", "weight": 1.5},
        ],
        "allowed_roles": ["Sales Manager", "Sales User", "System Manager"],
    },
    {
        "agent_code": "ceo_assistant",
        "agent_name": "CEO Assistant",
        "description": "Executive business overview, profitability, operational efficiency",
        "icon": "👔",
        "color": "#8B5CF6",
        "display_order": 5,
        "default_agent": 0,
        "enabled": 1,
        "system_prompt": (
            "You are an Executive AI Assistant for the CEO. Provide high-level business "
            "intelligence, profitability analysis, and operational efficiency insights. "
            "Summarize key metrics across all departments: sales, collections, inventory, "
            "workshop, and HR. Identify risks, opportunities, and strategic priorities. "
            "Always present data in a clear executive summary format with actionable "
            "recommendations. Focus on trends and exceptions that need leadership attention."
        ),
        "tools": [],  # CEO gets all RBAC-allowed tools
        "kpis": [
            {"name": "Revenue", "description": "Total monthly revenue vs target", "weight": 2.0},
            {"name": "Profitability", "description": "Gross margin and net profit trends", "weight": 2.0},
            {"name": "Collections", "description": "Collection efficiency and overdue AR", "weight": 1.5},
            {"name": "Inventory Health", "description": "Stock levels and critical shortages", "weight": 1.0},
            {"name": "Customer Retention", "description": "Active vs inactive customer ratio", "weight": 1.0},
            {"name": "Workshop Performance", "description": "Job completion rate and technician efficiency", "weight": 1.0},
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
