"""
Business Intelligence tools for the AI Assistant.

Features implemented:
  Feature 1 — Business Analysis Engine
  Feature 2 — Management Daily Summary
  Feature 3 — Customer Follow-Up Assistant
  Feature 4 — Workshop Service Advisor / Vehicle Diagnostics

All tools return {"status": "ok"|"error", "message": str, ...data}.
SQL is used only where Frappe ORM cannot perform the required aggregation.
"""

from __future__ import annotations

import frappe
from frappe.utils import (
    today, add_days, flt, getdate, add_months,
    get_first_day, get_last_day, date_diff, nowdate,
)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _month_range(months_ago: int = 0):
    """Return (first_day, last_day) for the month N months ago."""
    base = getdate(add_months(today(), -months_ago))
    return str(get_first_day(base)), str(get_last_day(base))


def _sql_sum(table: str, field: str, where: str, params: tuple) -> float:
    rows = frappe.db.sql(
        f"SELECT COALESCE(SUM({field}), 0) AS v FROM {table} WHERE {where}",
        params, as_dict=True,
    )
    return float((rows[0] or {}).get("v", 0))


def _sql_count(table: str, where: str, params: tuple) -> int:
    rows = frappe.db.sql(
        f"SELECT COUNT(*) AS c FROM {table} WHERE {where}",
        params, as_dict=True,
    )
    return int((rows[0] or {}).get("c", 0))


_BASE_CURRENCY: str | None = None


def get_base_currency() -> str:
    global _BASE_CURRENCY
    if _BASE_CURRENCY is None:
        _BASE_CURRENCY = frappe.db.get_single_value("Global Defaults", "default_currency") or "QAR"
    return _BASE_CURRENCY


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  FEATURE 1 — BUSINESS ANALYSIS ENGINE                                       ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

def get_monthly_sales_trend(months: int = 6) -> dict:
    """Monthly sales totals + invoice counts for the past N months — enriched with metrics and chart."""
    months = max(1, min(months, 24))
    from datetime import datetime as _dt
    trend = []
    for i in range(months - 1, -1, -1):
        m_start, m_end = _month_range(i)
        rows = frappe.db.sql("""
            SELECT COALESCE(SUM(base_grand_total), 0) AS total,
                   COUNT(*) AS cnt
            FROM `tabSales Invoice`
            WHERE docstatus = 1
              AND posting_date BETWEEN %s AND %s
        """, (m_start, m_end), as_dict=True)
        row = rows[0] if rows else {}
        label = _dt.strptime(m_start, "%Y-%m-%d").strftime("%b %Y")
        trend.append({
            "month": label,
            "start": m_start,
            "end": m_end,
            "total_sales": float(row.get("total", 0)),
            "invoice_count": int(row.get("cnt", 0)),
        })

    current = trend[-1]["total_sales"] if trend else 0
    previous = trend[-2]["total_sales"] if len(trend) >= 2 else 0
    growth = round((current - previous) / previous * 100, 1) if previous else 0

    # ── Enrichment ──────────────────────────────────────────────────────
    revenue_ytd = sum(m["total_sales"] for m in trend)
    avg_monthly = round(revenue_ytd / len(trend), 2) if trend else 0
    best = max(trend, key=lambda m: m["total_sales"]) if trend else {}
    best_month_name = best.get("month", "—")

    m_start_curr, _ = _month_range(0)
    top_customers = frappe.db.sql("""
        SELECT customer, SUM(base_grand_total) AS revenue, COUNT(*) AS orders
        FROM `tabSales Invoice`
        WHERE docstatus = 1 AND posting_date >= %s
        GROUP BY customer ORDER BY revenue DESC LIMIT 5
    """, (m_start_curr,), as_dict=True)

    top_items = frappe.db.sql("""
        SELECT sii.item_code, sii.item_name, SUM(sii.base_amount) AS total_revenue, SUM(sii.qty) AS total_qty
        FROM `tabSales Invoice Item` sii
        INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
        WHERE si.docstatus = 1 AND si.posting_date >= %s
        GROUP BY sii.item_code, sii.item_name ORDER BY total_revenue DESC LIMIT 5
    """, (m_start_curr,), as_dict=True)

    base_currency = get_base_currency()
    metrics = {
        "revenue_current_month": round(current, 2),
        "revenue_prev_month":    round(previous, 2),
        "mom_change_pct":        growth,
        "revenue_ytd":           round(revenue_ytd, 2),
        "avg_monthly_revenue":   avg_monthly,
        "best_month_name":       best_month_name,
        "base_currency":         base_currency,
        "multi_currency":        True,
    }
    chart = {
        "type": "line",
        "title": f"Monthly Sales Trend (Last {months} Months)",
        "labels": [m["month"] for m in trend],
        "datasets": [{"name": f"Sales ({base_currency})", "values": [m["total_sales"] for m in trend]}],
    }

    return {
        "status": "ok",
        "months": months,
        "trend": trend,
        "current_month_sales": current,
        "previous_month_sales": previous,
        "growth_vs_last_month": growth,
        "top_customers": top_customers,
        "top_items":     top_items,
        "metrics":       metrics,
        "chart":         chart,
        "message": (
            f"Sales trend for {months} months. "
            f"Current month: {base_currency} {current:,.0f} (base currency). MoM: {growth:+.1f}%. "
            f"YTD: {base_currency} {revenue_ytd:,.0f}. Best month: {best_month_name}."
        ),
    }


def get_top_customers(period_days: int = 30, limit: int = 10) -> dict:
    """Top customers by base-currency sales value in the last N days."""
    from_date = add_days(today(), -period_days)
    try:
        rows = frappe.db.sql("""
            SELECT customer,
                   SUM(base_grand_total) AS total_sales,
                   COUNT(*)              AS invoice_count,
                   MAX(posting_date)     AS last_invoice_date
            FROM `tabSales Invoice`
            WHERE docstatus = 1 AND posting_date >= %s
            GROUP BY customer
            ORDER BY total_sales DESC
            LIMIT %s
        """, (from_date, limit), as_dict=True)
    except Exception as exc:
        import traceback as _tb
        frappe.log_error(title="get_top_customers SQL failed", message=_tb.format_exc())
        return {
            "status": "error",
            "message": f"Failed to query top customers: {exc}",
            "customers": [],
        }
    customers = [
        {
            "customer":          r.customer,
            "total_sales":       frappe.utils.flt(r.total_sales, 2),
            "invoice_count":     int(r.invoice_count or 0),
            "last_invoice_date": str(r.last_invoice_date or ""),
            "currency":          frappe.db.get_single_value("Global Defaults", "default_currency") or "QAR",
        }
        for r in rows
    ]
    return {
        "status":      "ok",
        "period_days": period_days,
        "from_date":   from_date,
        "count":       len(customers),
        "customers":   customers,
        "message":     f"Top {len(customers)} customers in the last {period_days} days.",
    }


def get_top_selling_items(period_days: int = 30, limit: int = 10) -> dict:
    """Top selling items by base-currency revenue in the last N days."""
    from_date = add_days(today(), -period_days)
    try:
        rows = frappe.db.sql("""
            SELECT sii.item_code,
                   sii.item_name,
                   SUM(sii.qty)         AS total_qty,
                   SUM(sii.base_amount) AS total_amount,
                   si.currency
            FROM `tabSales Invoice Item` sii
            INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
            WHERE si.docstatus = 1 AND si.posting_date >= %s
            GROUP BY sii.item_code, sii.item_name, si.currency
            ORDER BY total_amount DESC
            LIMIT %s
        """, (from_date, limit), as_dict=True)
    except Exception as exc:
        import traceback as _tb
        frappe.log_error(title="get_top_selling_items SQL failed", message=_tb.format_exc())
        return {
            "status": "error",
            "message": f"Failed to query top selling items: {exc}",
            "items": [],
        }
    items = [
        {
            "item_code":    r.item_code,
            "item_name":    r.item_name,
            "total_qty":    frappe.utils.flt(r.total_qty, 3),
            "total_amount": frappe.utils.flt(r.total_amount, 2),
            "currency":     r.currency or frappe.db.get_single_value("Global Defaults", "default_currency") or "QAR",
        }
        for r in rows
    ]
    return {
        "status":      "ok",
        "period_days": period_days,
        "from_date":   from_date,
        "count":       len(items),
        "items":       items,
        "message":     f"Top {len(items)} items by revenue in the last {period_days} days.",
    }


def get_pending_quotations(days_old: int = 0) -> dict:
    """Open quotations not yet converted; optionally filter by age."""
    filters: dict = {
        "docstatus": 1,
        "status": ["not in", ["Ordered", "Lost", "Cancelled"]],
    }
    if days_old:
        filters["transaction_date"] = ["<=", add_days(today(), -days_old)]

    rows = frappe.get_all(
        "Quotation",
        filters=filters,
        fields=["name", "party_name", "transaction_date", "valid_till",
                "grand_total", "status"],
        order_by="transaction_date asc",
        limit=50,
    )
    expiring = [r for r in rows
                if r.get("valid_till") and str(r["valid_till"]) <= add_days(today(), 7)]
    total_value = sum(flt(r.get("grand_total")) for r in rows)
    return {
        "status": "ok",
        "total_pending": len(rows),
        "expiring_soon_count": len(expiring),
        "total_value": total_value,
        "quotations": rows,
        "expiring_soon": expiring,
        "message": f"{len(rows)} pending quotations worth {total_value:,.0f}. {len(expiring)} expiring within 7 days.",
    }


def get_overdue_invoices() -> dict:
    """Unpaid invoices past due date — enriched with aging buckets, metrics, and chart data."""
    # Fetch up to 200 for accurate analytics; display is capped to 50 below
    rows = frappe.get_all(
        "Sales Invoice",
        filters={
            "docstatus": 1,
            "outstanding_amount": [">", 0],
            "due_date": ["<", today()],
        },
        fields=["name", "customer", "posting_date", "due_date",
                "grand_total", "outstanding_amount", "currency", "conversion_rate"],
        order_by="due_date asc",
        limit=200,
    )

    _today = getdate(today())
    for r in rows:
        r["days_overdue"] = date_diff(str(_today), str(r["due_date"])) if r.get("due_date") else 0
        r["base_outstanding"] = flt(r.get("outstanding_amount")) * flt(r.get("conversion_rate") or 1)

    total_overdue = sum(r["base_outstanding"] for r in rows)

    # Aging buckets — sum outstanding by days past due
    buckets = {"0-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0}
    for r in rows:
        d = r["days_overdue"]
        amt = r["base_outstanding"]
        if d <= 30:
            buckets["0-30"] += amt
        elif d <= 60:
            buckets["31-60"] += amt
        elif d <= 90:
            buckets["61-90"] += amt
        else:
            buckets["90+"] += amt

    # Top customers by outstanding (up to 8)
    customer_totals: dict[str, float] = {}
    for r in rows:
        c = r.get("customer") or "Unknown"
        customer_totals[c] = customer_totals.get(c, 0.0) + r["base_outstanding"]

    sorted_customers = sorted(customer_totals.items(), key=lambda x: x[1], reverse=True)[:8]
    top_customers = [
        {
            "customer": name,
            "outstanding": round(amt, 2),
            "pct_of_total": round(amt / total_overdue * 100, 1) if total_overdue else 0,
        }
        for name, amt in sorted_customers
    ]

    # Summary metrics
    over_90 = sum(r["base_outstanding"] for r in rows if r["days_overdue"] > 90)
    customers_affected = len(customer_totals)
    worst_pct = top_customers[0]["pct_of_total"] if top_customers else 0
    base_currency = get_base_currency()
    metrics = {
        "total_overdue": round(total_overdue, 2),
        "invoice_count": len(rows),
        "customers_affected": customers_affected,
        "over_90_days": round(over_90, 2),
        "over_90_pct": round(over_90 / total_overdue * 100, 1) if total_overdue else 0,
        "worst_customer_pct": worst_pct,
        "base_currency": base_currency,
        "multi_currency": True,
    }

    # Chart config for bar chart by aging bucket
    chart = {
        "type": "bar",
        "title": f"Overdue Invoices by Aging Bucket ({base_currency})",
        "labels": list(buckets.keys()),
        "datasets": [{"name": f"Outstanding ({base_currency})", "values": [round(v, 2) for v in buckets.values()]}],
    }

    worst_customer = top_customers[0]["customer"] if top_customers else "N/A"
    message = (
        f"{len(rows)} overdue invoices totaling {base_currency} {total_overdue:,.0f} (base currency) "
        f"across {customers_affected} customers. "
        f"{base_currency} {over_90:,.0f} ({metrics['over_90_pct']}%) is 90+ days past due. "
        f"Largest exposure: {worst_customer} ({worst_pct}% of total)."
    )

    return {
        # Original keys — preserved for backward compatibility
        "status": "ok",
        "overdue_count": len(rows),
        "total_overdue_amount": total_overdue,
        "invoices": rows[:50],          # capped at 50 for display
        "message": message,
        # Enrichment
        "aging_buckets": buckets,
        "top_customers": top_customers,
        "metrics": metrics,
        "chart": chart,
    }


def get_stock_alerts() -> dict:
    """Items below safety stock level and items with reserved but zero actual qty."""
    low = frappe.db.sql("""
        SELECT b.item_code, i.item_name, b.warehouse,
               b.actual_qty, i.safety_stock,
               ROUND(b.actual_qty / i.safety_stock * 100, 0) AS stock_pct
        FROM `tabBin` b
        INNER JOIN `tabItem` i ON i.name = b.item_code
        WHERE i.is_stock_item = 1
          AND i.safety_stock > 0
          AND b.actual_qty <= i.safety_stock
          AND i.disabled = 0
        ORDER BY stock_pct ASC
        LIMIT 20
    """, as_dict=True)

    out_of_stock = frappe.db.sql("""
        SELECT b.item_code, i.item_name, b.warehouse,
               b.actual_qty, b.reserved_qty
        FROM `tabBin` b
        INNER JOIN `tabItem` i ON i.name = b.item_code
        WHERE i.is_stock_item = 1
          AND b.actual_qty <= 0
          AND b.reserved_qty > 0
          AND i.disabled = 0
        ORDER BY b.reserved_qty DESC
        LIMIT 15
    """, as_dict=True)

    return {
        "status": "ok",
        "low_stock_count": len(low),
        "out_of_stock_count": len(out_of_stock),
        "critical_items": [dict(r) for r in low],
        "out_of_stock_items": [dict(r) for r in out_of_stock],
        "message": f"{len(low)} items below safety stock. {len(out_of_stock)} items out of stock with pending demand.",
    }


def get_open_job_cards(status: str = "", limit: int = 20) -> dict:
    """Open workshop job cards with delay detection."""
    if frappe.db.exists("DocType", "Workshop Job Card"):
        try:
            f: dict = {}
            if status:
                f["status"] = status
            else:
                f["status"] = ["in", ["Open", "In Progress"]]
            cards = frappe.get_all(
                "Workshop Job Card",
                filters=f,
                fields=["name", "vehicle", "customer", "complaint",
                        "status", "technician", "date", "creation"],
                limit=limit,
            )
            delayed = [c for c in cards
                       if c.get("date") and date_diff(today(), str(c["date"])) > 2]
            return {
                "status": "ok",
                "source": "Workshop Job Card",
                "total_open": len(cards),
                "delayed_count": len(delayed),
                "job_cards": cards,
                "delayed_jobs": delayed,
                "message": f"{len(cards)} open jobs. {len(delayed)} delayed beyond 2 days.",
            }
        except Exception as e:
            return {
                "status": "ok",
                "source": "Workshop Job Card",
                "total_open": 0,
                "delayed_count": 0,
                "job_cards": [],
                "delayed_jobs": [],
                "message": f"Workshop Job Card query error: {e}",
            }

    # Fallback to Maintenance Visit
    try:
        visits = frappe.get_all(
            "Maintenance Visit",
            filters={"completion_status": ["in",
                ["Partially Completed", "Not Started"]]},
            fields=["name", "customer", "maint_date", "purpose",
                    "completion_status"],
            order_by="maint_date asc",
            limit=limit,
        )
    except Exception:
        try:
            visits = frappe.get_all(
                "Maintenance Visit",
                fields=["name", "customer", "maint_date", "purpose"],
                order_by="maint_date asc",
                limit=limit,
            )
        except Exception:
            visits = []
    return {
        "status": "ok",
        "source": "Maintenance Visit",
        "total_open": len(visits),
        "delayed_count": 0,
        "job_cards": visits,
        "delayed_jobs": [],
        "message": (
            f"{len(visits)} open maintenance visits."
            if visits else
            "No open job cards or maintenance visits found."
        ),
    }


def _build_dept_scores(
    revenue_mom_pct: float,
    overdue_ar_pct: float,
    low_stock: int,
    open_pos: int,
    delayed_jobs: int,
) -> list:
    """Derive Green/Amber/Red health status for Sales, Accounts, Operations."""
    scores = []

    # Sales
    if revenue_mom_pct >= 5:
        scores.append({"department": "Sales", "status": "Good",
                        "note": f"Revenue up {revenue_mom_pct:+.1f}% MoM"})
    elif revenue_mom_pct >= -5:
        scores.append({"department": "Sales", "status": "Warning",
                        "note": f"Revenue flat ({revenue_mom_pct:+.1f}% MoM)"})
    else:
        scores.append({"department": "Sales", "status": "Critical",
                        "note": f"Revenue down {revenue_mom_pct:.1f}% MoM"})

    # Accounts
    if overdue_ar_pct < 15:
        scores.append({"department": "Accounts", "status": "Good",
                        "note": f"Overdue AR is {overdue_ar_pct:.1f}% of monthly sales"})
    elif overdue_ar_pct < 40:
        scores.append({"department": "Accounts", "status": "Warning",
                        "note": f"Overdue AR at {overdue_ar_pct:.1f}% of monthly sales"})
    else:
        scores.append({"department": "Accounts", "status": "Critical",
                        "note": f"Overdue AR is {overdue_ar_pct:.1f}% of monthly sales — high risk"})

    # Operations
    ops_issues = (1 if low_stock > 3 else 0) + (1 if open_pos > 5 else 0) + (1 if delayed_jobs > 0 else 0)
    if ops_issues == 0:
        scores.append({"department": "Operations", "status": "Good",
                        "note": "Stock, POs, and workshop within normal range"})
    elif ops_issues == 1:
        scores.append({"department": "Operations", "status": "Warning",
                        "note": f"Minor issues: low_stock={low_stock}, open_POs={open_pos}, delayed_jobs={delayed_jobs}"})
    else:
        scores.append({"department": "Operations", "status": "Critical",
                        "note": f"Multiple issues: low_stock={low_stock}, open_POs={open_pos}, delayed_jobs={delayed_jobs}"})

    return scores


def analyze_business() -> dict:
    """
    Comprehensive business intelligence snapshot.
    Aggregates sales, quotations, AR, stock and workshop data into a
    single report with AI-ready recommendations.
    """
    t = today()
    m_start, _ = _month_range(0)
    pm_start, pm_end = _month_range(1)

    # Sales
    sales_curr = _sql_sum("`tabSales Invoice`", "`base_grand_total`",
                          "docstatus=1 AND posting_date>=%s", (m_start,))
    sales_prev = _sql_sum("`tabSales Invoice`", "`base_grand_total`",
                          "docstatus=1 AND posting_date BETWEEN %s AND %s",
                          (pm_start, pm_end))
    sales_growth = round((sales_curr - sales_prev) / sales_prev * 100, 1) if sales_prev else 0

    # Collections today
    collected_today = _sql_sum("`tabPayment Entry`", "`paid_amount`",
                               "docstatus=1 AND payment_type='Receive' AND posting_date=%s", (t,))

    # Quotations
    pending_q = frappe.db.count("Quotation", {
        "docstatus": ["in", [0, 1]], "status": ["in", ["Open", "Draft"]]
    })
    expiring_q = frappe.db.count("Quotation", {
        "docstatus": ["in", [0, 1]], "status": ["in", ["Open", "Draft"]],
        "valid_till": ["between", [t, add_days(t, 7)]],
    })

    # Overdue AR
    overdue_rows = frappe.get_all(
        "Sales Invoice",
        filters={"docstatus": 1, "outstanding_amount": [">", 0], "due_date": ["<", t]},
        fields=["outstanding_amount", "conversion_rate"],
    )
    overdue_count = len(overdue_rows)
    overdue_amount = sum(flt(r.get("outstanding_amount")) * flt(r.get("conversion_rate") or 1) for r in overdue_rows)

    # Due this week
    due_week = frappe.db.count("Sales Invoice", {
        "docstatus": 1,
        "outstanding_amount": [">", 0],
        "due_date": ["between", [t, add_days(t, 7)]],
    })

    # Stock alerts
    stock_alert_rows = frappe.db.sql("""
        SELECT COUNT(*) AS c
        FROM `tabBin` b
        INNER JOIN `tabItem` i ON i.name = b.item_code
        WHERE i.is_stock_item=1 AND i.safety_stock>0
          AND b.actual_qty <= i.safety_stock AND i.disabled=0
    """, as_dict=True)
    critical_stock = int((stock_alert_rows[0] or {}).get("c", 0))

    # Workshop
    open_jobs = 0
    delayed_jobs = 0
    if frappe.db.exists("DocType", "Workshop Job Card"):
        try:
            open_jobs = frappe.db.count("Workshop Job Card",
                                        {"status": ["in", ["Open", "In Progress"]]})
            dj = frappe.db.sql("""
                SELECT COUNT(*) AS c FROM `tabWorkshop Job Card`
                WHERE status IN ('Open','In Progress')
                  AND DATEDIFF(CURDATE(), date) > 2
            """, as_dict=True)
            delayed_jobs = int((dj[0] or {}).get("c", 0))
        except Exception:
            pass

    # Top customers this month
    top_customers = frappe.db.sql("""
        SELECT customer, SUM(base_grand_total) AS total
        FROM `tabSales Invoice`
        WHERE docstatus=1 AND posting_date >= %s
        GROUP BY customer ORDER BY total DESC LIMIT 5
    """, (m_start,), as_dict=True)

    # New customers this month
    new_customers = frappe.db.count("Customer", {"creation": [">=", m_start]})

    # Open leads + open POs (for department scoring)
    open_leads = frappe.db.count("Lead", {"status": ["in", ["New", "Open", "Replied", "Contacted"]]})
    open_pos   = frappe.db.count("Purchase Order",
                                  {"docstatus": 1, "status": ["in", ["To Receive and Bill", "To Bill", "To Receive"]]})

    overdue_ar_pct = round(overdue_amount / sales_curr * 100, 1) if sales_curr else 0

    # ── Build prioritised recommendations ──────────────────────────────
    recs = []
    if sales_growth < -15:
        recs.append({
            "priority": "critical",
            "text": f"Sales are down {abs(sales_growth):.0f}% vs last month — review pricing, pipeline, and lost deals.",
        })
    elif sales_growth < -5:
        recs.append({
            "priority": "warning",
            "text": f"Sales declined {abs(sales_growth):.0f}% vs last month — increase follow-up on pending quotations.",
        })
    base_currency = get_base_currency()
    if overdue_count >= 5:
        recs.append({
            "priority": "critical",
            "text": f"{overdue_count} overdue invoices worth {base_currency} {overdue_amount:,.0f} — initiate collection immediately.",
        })
    elif overdue_count > 0:
        recs.append({
            "priority": "warning",
            "text": f"{overdue_count} overdue invoices totaling {base_currency} {overdue_amount:,.0f} — follow up with customers.",
        })
    if pending_q > 10:
        recs.append({
            "priority": "warning",
            "text": f"{pending_q} unconverted quotations — prioritise conversion calls.",
        })
    if expiring_q:
        recs.append({
            "priority": "warning",
            "text": f"{expiring_q} quotations expiring within 7 days — follow up urgently.",
        })
    if critical_stock > 3:
        recs.append({
            "priority": "warning",
            "text": f"{critical_stock} items critically low — raise material requests now.",
        })
    if delayed_jobs > 0:
        recs.append({
            "priority": "info",
            "text": f"{delayed_jobs} workshop jobs are delayed beyond 2 days — check technician assignments.",
        })
    if due_week:
        recs.append({
            "priority": "info",
            "text": f"{due_week} invoices due within 7 days — prepare collection reminders.",
        })
    if not recs:
        recs.append({
            "priority": "ok",
            "text": "Business is running well. Keep monitoring KPIs daily.",
        })

    # ── Enrichment ──────────────────────────────────────────────────────
    metrics = {
        "sales_this_month":      round(sales_curr, 2),
        "sales_last_month":      round(sales_prev, 2),
        "revenue_mom_pct":       sales_growth,
        "collected_today":       round(collected_today, 2),
        "overdue_ar_pct":        overdue_ar_pct,
        "overdue_amount":        round(overdue_amount, 2),
        "overdue_invoice_count": overdue_count,
        "pending_quotations":    pending_q,
        "critical_stock_items":  critical_stock,
        "open_job_cards":        open_jobs,
        "delayed_job_cards":     delayed_jobs,
        "base_currency":         base_currency,
        "multi_currency":        True,
    }
    chart = {
        "type": "bar",
        "title": f"Business Snapshot ({base_currency})",
        "labels": ["Sales This Month", "Sales Last Month", "Overdue AR", "Collected Today"],
        "datasets": [{"name": base_currency, "values": [
            round(sales_curr, 2), round(sales_prev, 2),
            round(overdue_amount, 2), round(collected_today, 2),
        ]}],
    }
    department_scores = _build_dept_scores(
        revenue_mom_pct=sales_growth,
        overdue_ar_pct=overdue_ar_pct,
        low_stock=critical_stock,
        open_pos=open_pos,
        delayed_jobs=delayed_jobs,
    )

    return {
        "status": "ok",
        "analysis_date": t,
        # KPIs
        "sales_this_month": sales_curr,
        "sales_last_month": sales_prev,
        "sales_growth": sales_growth,
        "collected_today": collected_today,
        # Pipeline
        "pending_quotations": pending_q,
        "expiring_quotations": expiring_q,
        # AR
        "overdue_invoice_count": overdue_count,
        "overdue_invoice_amount": overdue_amount,
        "invoices_due_this_week": due_week,
        # Operations
        "critical_stock_items": critical_stock,
        "open_job_cards": open_jobs,
        "delayed_job_cards": delayed_jobs,
        # Context
        "new_customers_this_month": new_customers,
        "top_customers": [dict(r) for r in top_customers],
        # Intelligence
        "recommendations": recs,
        # Enrichment
        "metrics":           metrics,
        "chart":             chart,
        "department_scores": department_scores,
        "message": (
            f"Business analysis for {t}. "
            f"Sales: {base_currency} {sales_curr:,.0f} ({sales_growth:+.1f}% vs last month). "
            f"Overdue: {overdue_count} invoices, {base_currency} {overdue_amount:,.0f}. "
            f"{len(recs)} recommendation(s)."
        ),
    }


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  FEATURE 2 — MANAGEMENT DAILY SUMMARY                                       ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

def get_management_summary() -> dict:
    """
    Full management daily briefing.
    Sections: Sales, Collections, Quotations, Invoices, Inventory, Workshop,
              New Customers, and Prioritised Action Items.
    """
    from datetime import datetime
    t = today()
    m_start, _ = _month_range(0)
    pm_start, pm_end = _month_range(1)
    week_start = str(getdate(t) - __import__("datetime").timedelta(days=getdate(t).weekday()))

    # ── Sales ─────────────────────────────────────────────────────────
    def _sales(f, t2):
        r = frappe.db.sql("""
            SELECT COALESCE(SUM(base_grand_total), 0) t, COUNT(*) c
            FROM `tabSales Invoice`
            WHERE docstatus=1 AND posting_date BETWEEN %s AND %s
        """, (f, t2), as_dict=True)
        row = r[0] if r else {}
        return float(row.get("t", 0)), int(row.get("c", 0))

    s_today, c_today = _sales(t, t)
    s_yesterday, c_yesterday = _sales(add_days(t, -1), add_days(t, -1))
    s_week, c_week = _sales(week_start, t)
    s_month, c_month = _sales(m_start, t)
    s_last, _ = _sales(pm_start, pm_end)
    growth = round((s_month - s_last) / s_last * 100, 1) if s_last else 0
    today_vs_yesterday_pct = round((s_today - s_yesterday) / s_yesterday * 100, 1) if s_yesterday else 0

    collected_today = _sql_sum("`tabPayment Entry`", "`paid_amount`",
                               "docstatus=1 AND payment_type='Receive' AND posting_date=%s", (t,))

    # ── Quotations ────────────────────────────────────────────────────
    pending_q = frappe.get_all("Quotation",
        filters={"docstatus": ["in", [0, 1]], "status": ["in", ["Open", "Draft"]]},
        fields=["name", "party_name", "valid_till", "grand_total"],
    )
    expiring_q = [q for q in pending_q
                  if q.get("valid_till") and str(q["valid_till"]) <= add_days(t, 7)]

    # ── Invoices ──────────────────────────────────────────────────────
    overdue_inv = frappe.get_all("Sales Invoice",
        filters={"docstatus": 1, "outstanding_amount": [">", 0], "due_date": ["<", t]},
        fields=["name", "customer", "outstanding_amount", "due_date", "conversion_rate"],
    )
    due_today_inv = frappe.get_all("Sales Invoice",
        filters={"docstatus": 1, "outstanding_amount": [">", 0], "due_date": t},
        fields=["name", "customer", "outstanding_amount", "conversion_rate"],
    )

    # ── Inventory ─────────────────────────────────────────────────────
    low_stock_r = frappe.db.sql("""
        SELECT COUNT(*) c FROM `tabBin` b
        INNER JOIN `tabItem` i ON i.name=b.item_code
        WHERE i.is_stock_item=1 AND i.safety_stock>0
          AND b.actual_qty<=i.safety_stock AND i.disabled=0
    """, as_dict=True)
    low_stock_count = int((low_stock_r[0] or {}).get("c", 0))

    fast_items = frappe.db.sql("""
        SELECT sii.item_code, sii.item_name, SUM(sii.qty) AS qty_sold
        FROM `tabSales Invoice Item` sii
        INNER JOIN `tabSales Invoice` si ON si.name=sii.parent
        WHERE si.docstatus=1 AND si.posting_date>=%s
        GROUP BY sii.item_code, sii.item_name
        ORDER BY qty_sold DESC LIMIT 5
    """, (m_start,), as_dict=True)

    # ── Workshop ──────────────────────────────────────────────────────
    open_jobs = delayed_jobs = 0
    if frappe.db.exists("DocType", "Workshop Job Card"):
        try:
            open_jobs = frappe.db.count("Workshop Job Card",
                                        {"status": ["in", ["Open", "In Progress"]]})
            dj = frappe.db.sql("""
                SELECT COUNT(*) c FROM `tabWorkshop Job Card`
                WHERE status IN ('Open','In Progress') AND DATEDIFF(CURDATE(), date) > 2
            """, as_dict=True)
            delayed_jobs = int((dj[0] or {}).get("c", 0))
        except Exception:
            pass

    # ── New Customers ─────────────────────────────────────────────────
    new_customers = frappe.db.count("Customer", {"creation": [">=", m_start]})

    # ── Action Priorities ─────────────────────────────────────────────
    priorities = []
    if overdue_inv:
        top3 = sorted(overdue_inv, key=lambda x: -flt(x.get("outstanding_amount")))[:3]
        for inv in top3:
            priorities.append({
                "type": "collect",
                "text": f"Collect {flt(inv['outstanding_amount']) * flt(inv.get('conversion_rate') or 1):,.0f} from {inv['customer']} ({inv['name']})",
                "doctype": "Sales Invoice", "doc": inv["name"],
            })
    for q in expiring_q[:3]:
        priorities.append({
            "type": "followup",
            "text": f"Follow up {q['name']} for {q['party_name']} — expires {q['valid_till']}",
            "doctype": "Quotation", "doc": q["name"],
        })
    if low_stock_count:
        priorities.append({
            "type": "stock",
            "text": f"Replenish {low_stock_count} low-stock items",
        })
    if delayed_jobs:
        priorities.append({
            "type": "workshop",
            "text": f"Review {delayed_jobs} delayed workshop jobs",
        })

    hour = datetime.now().hour
    greeting = "Good Morning" if hour < 12 else ("Good Afternoon" if hour < 17 else "Good Evening")

    overdue_count  = len(overdue_inv)
    overdue_amount = sum(flt(r.get("outstanding_amount")) * flt(r.get("conversion_rate") or 1) for r in overdue_inv)

    # ── Enrichment: flat metrics, chart, alerts ──────────────────────
    base_currency = get_base_currency()
    metrics = {
        "sales_today":           round(s_today, 2),
        "sales_yesterday":       round(s_yesterday, 2),
        "today_vs_yesterday_pct": today_vs_yesterday_pct,
        "sales_this_week":       round(s_week, 2),
        "sales_this_month":      round(s_month, 2),
        "revenue_mom_pct":       growth,
        "collected_today":       round(collected_today, 2),
        "overdue_invoice_count": overdue_count,
        "overdue_amount":        round(overdue_amount, 2),
        "pending_quotations":    len(pending_q),
        "low_stock_items":       low_stock_count,
        "open_jobs":             open_jobs,
        "delayed_jobs":          delayed_jobs,
        "base_currency":         base_currency,
        "multi_currency":        True,
    }
    chart = {
        "type": "bar",
        "title": f"Today vs Yesterday Sales ({base_currency})",
        "labels": ["Yesterday", "Today"],
        "datasets": [{"name": f"Sales ({base_currency})", "values": [round(s_yesterday, 2), round(s_today, 2)]}],
    }
    alerts = []
    if overdue_count >= 5:
        alerts.append({"level": "critical", "message": f"{overdue_count} overdue invoices totaling {base_currency} {overdue_amount:,.0f}"})
    elif overdue_count > 0:
        alerts.append({"level": "warning", "message": f"{overdue_count} overdue invoices — {base_currency} {overdue_amount:,.0f}"})
    if len(expiring_q) > 0:
        alerts.append({"level": "warning", "message": f"{len(expiring_q)} quotation(s) expiring within 7 days"})
    if low_stock_count > 3:
        alerts.append({"level": "warning", "message": f"{low_stock_count} items below safety stock"})
    if delayed_jobs > 0:
        alerts.append({"level": "info", "message": f"{delayed_jobs} workshop job(s) delayed beyond 2 days"})
    if today_vs_yesterday_pct < -20:
        alerts.append({"level": "warning", "message": f"Today's sales {today_vs_yesterday_pct:+.1f}% vs yesterday"})

    return {
        "status": "ok",
        "greeting": greeting,
        "date": t,
        "sales": {
            "today": s_today,
            "today_count": c_today,
            "this_week": s_week,
            "week_count": c_week,
            "this_month": s_month,
            "month_count": c_month,
            "last_month": s_last,
            "growth_pct": growth,
            "collected_today": collected_today,
        },
        "quotations": {
            "pending_count": len(pending_q),
            "pending_value": sum(flt(q.get("grand_total")) for q in pending_q),
            "expiring_soon": len(expiring_q),
        },
        "invoices": {
            "overdue_count": overdue_count,
            "overdue_amount": overdue_amount,
            "due_today_count": len(due_today_inv),
            "due_today_amount": sum(flt(r.get("outstanding_amount")) * flt(r.get("conversion_rate") or 1) for r in due_today_inv),
        },
        "inventory": {
            "low_stock_count": low_stock_count,
            "fast_moving_items": [dict(r) for r in fast_items],
        },
        "workshop": {
            "open_jobs": open_jobs,
            "delayed_jobs": delayed_jobs,
        },
        "customers": {
            "new_this_month": new_customers,
        },
        "priorities": priorities,
        # Enrichment
        "metrics": metrics,
        "chart":   chart,
        "alerts":  alerts,
        "message": (
            f"{greeting}! Today's sales: {base_currency} {s_today:,.0f} ({today_vs_yesterday_pct:+.1f}% vs yesterday). "
            f"Month: {base_currency} {s_month:,.0f} ({growth:+.1f}%). "
            f"Overdue: {overdue_count} invoices. "
            f"Pending quotations: {len(pending_q)}."
        ),
    }


def get_sales_analysis() -> dict:
    """
    Deep sales analysis for the current month:
    revenue by item group, by salesperson, quotation conversion rate,
    top customers, top items, new vs returning customers.

    Salesperson attribution — Case B (Sales Team child table):
    Sales Order has no direct sales_person Link field. Attribution uses
    the `tabSales Team` child table (Sales Order field: sales_team,
    child DocType: Sales Team, child field: sales_person → Link to Sales Person).
    The revenue query joins tabSales Team on tabSales Invoice (not tabSales Order)
    using allocated_percentage to weight each salesperson's share.
    Do NOT filter directly on a sales_person column on tabSales Invoice —
    that field does not exist there; always join through tabSales Team.
    """
    m_start, _ = _month_range(0)
    t = today()

    # Revenue by item group
    by_group = frappe.db.sql("""
        SELECT sii.item_group, SUM(sii.base_amount) AS revenue, COUNT(DISTINCT si.name) AS orders
        FROM `tabSales Invoice Item` sii
        INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
        WHERE si.docstatus = 1 AND si.posting_date >= %s
        GROUP BY sii.item_group ORDER BY revenue DESC LIMIT 8
    """, (m_start,), as_dict=True)

    # Revenue by salesperson
    by_salesperson = frappe.db.sql("""
        SELECT st.sales_person AS salesperson,
               SUM(si.base_grand_total * st.allocated_percentage / 100) AS revenue,
               COUNT(DISTINCT si.name) AS orders
        FROM `tabSales Team` st
        INNER JOIN `tabSales Invoice` si ON si.name = st.parent AND si.parenttype='Sales Invoice'
        WHERE si.docstatus = 1 AND si.posting_date >= %s
        GROUP BY st.sales_person ORDER BY revenue DESC LIMIT 8
    """, (m_start,), as_dict=True)

    # Quotation conversion rate
    total_quotations = frappe.db.count("Quotation", {
        "docstatus": ["in", [0, 1]], "transaction_date": [">=", m_start]
    })
    converted_quotations = frappe.db.count("Quotation", {
        "docstatus": 1, "status": "Ordered", "transaction_date": [">=", m_start]
    })
    conversion_rate_pct = round(converted_quotations / total_quotations * 100, 1) if total_quotations else 0

    # Top customers
    top_customers = frappe.db.sql("""
        SELECT customer, SUM(base_grand_total) AS revenue, COUNT(*) AS orders
        FROM `tabSales Invoice`
        WHERE docstatus = 1 AND posting_date >= %s
        GROUP BY customer ORDER BY revenue DESC LIMIT 8
    """, (m_start,), as_dict=True)

    # Total MTD revenue and orders
    totals_r = frappe.db.sql("""
        SELECT COALESCE(SUM(base_grand_total), 0) AS revenue, COUNT(*) AS orders,
               COALESCE(AVG(base_grand_total), 0) AS avg_deal
        FROM `tabSales Invoice` WHERE docstatus = 1 AND posting_date >= %s
    """, (m_start,), as_dict=True)
    totals = totals_r[0] if totals_r else {}
    total_revenue_mtd = float(totals.get("revenue", 0))
    total_orders_mtd  = int(totals.get("orders", 0))
    avg_deal_size     = round(float(totals.get("avg_deal", 0)), 2)

    # New vs returning customers this month
    new_cx = frappe.db.count("Customer", {"creation": [">=", m_start]})
    active_cx_r = frappe.db.sql(
        "SELECT COUNT(DISTINCT customer) AS c FROM `tabSales Invoice` WHERE docstatus=1 AND posting_date>=%s",
        (m_start,), as_dict=True,
    )
    active_cx = int((active_cx_r[0] or {}).get("c", 0))
    returning_cx = max(0, active_cx - new_cx)

    base_currency = get_base_currency()
    metrics = {
        "total_revenue_mtd":       round(total_revenue_mtd, 2),
        "total_orders_mtd":        total_orders_mtd,
        "avg_deal_size":           avg_deal_size,
        "conversion_rate_pct":     conversion_rate_pct,
        "total_quotations_mtd":    total_quotations,
        "converted_quotations_mtd": converted_quotations,
        "new_customers_mtd":       new_cx,
        "returning_customers_mtd": returning_cx,
        "base_currency":           base_currency,
        "multi_currency":          True,
    }
    chart = {
        "type": "bar",
        "title": "Revenue by Item Group (MTD)",
        "labels": [r.get("item_group") or "Other" for r in by_group],
        "datasets": [{"name": f"Revenue ({base_currency})", "values": [float(r.get("revenue") or 0) for r in by_group]}],
    }

    return {
        "status": "ok",
        "period_start": m_start,
        "by_item_group":   by_group,
        "by_salesperson":  by_salesperson,
        "top_customers":   top_customers,
        "metrics":         metrics,
        "chart":           chart,
        "message": (
            f"Sales analysis MTD ({m_start} → {t}): "
            f"{base_currency} {total_revenue_mtd:,.0f} from {total_orders_mtd} orders (base currency). "
            f"Conversion rate: {conversion_rate_pct}%. "
            f"New customers: {new_cx}."
        ),
    }


def get_payables_analysis() -> dict:
    """
    Outstanding purchase invoices with aging buckets, top suppliers by balance,
    upcoming-due forecast (next 7 days), and payables health metrics.
    """
    rows = frappe.get_all(
        "Purchase Invoice",
        filters={
            "docstatus": 1,
            "outstanding_amount": [">", 0],
        },
        fields=["name", "supplier", "posting_date", "due_date",
                "grand_total", "outstanding_amount", "conversion_rate"],
        order_by="due_date asc",
        limit=200,
    )

    _today = getdate(today())
    for r in rows:
        due = r.get("due_date")
        if due:
            r["days_overdue"] = max(0, date_diff(str(_today), str(due)))
        else:
            r["days_overdue"] = 0
        r["base_outstanding"] = flt(r.get("outstanding_amount")) * flt(r.get("conversion_rate") or 1)

    total_payable = sum(r["base_outstanding"] for r in rows)

    # Aging buckets
    buckets = {"0-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0}
    for r in rows:
        d = r["days_overdue"]
        amt = r["base_outstanding"]
        if d <= 30:
            buckets["0-30"] += amt
        elif d <= 60:
            buckets["31-60"] += amt
        elif d <= 90:
            buckets["61-90"] += amt
        else:
            buckets["90+"] += amt

    # Top suppliers by outstanding
    supplier_totals: dict[str, float] = {}
    for r in rows:
        s = r.get("supplier") or "Unknown"
        supplier_totals[s] = supplier_totals.get(s, 0.0) + r["base_outstanding"]

    sorted_suppliers = sorted(supplier_totals.items(), key=lambda x: x[1], reverse=True)[:8]
    top_suppliers = [
        {
            "supplier":         name,
            "outstanding":      round(amt, 2),
            "pct_of_total":     round(amt / total_payable * 100, 1) if total_payable else 0,
            "days_overdue_avg": 0,  # simplified
        }
        for name, amt in sorted_suppliers
    ]

    # Upcoming due in next 7 days
    due_7d = str(add_days(today(), 7))
    upcoming_due = [
        r for r in rows
        if r.get("due_date") and str(r["due_date"]) <= due_7d
    ][:20]

    # Metrics
    over_90 = sum(r["base_outstanding"] for r in rows if r["days_overdue"] > 90)
    suppliers_affected = len(supplier_totals)
    due_next_7d_amt = sum(r["base_outstanding"] for r in upcoming_due)

    base_currency = get_base_currency()
    metrics = {
        "total_payable":      round(total_payable, 2),
        "invoice_count":      len(rows),
        "suppliers_affected": suppliers_affected,
        "over_90_days":       round(over_90, 2),
        "over_90_pct":        round(over_90 / total_payable * 100, 1) if total_payable else 0,
        "due_next_7_days":    round(due_next_7d_amt, 2),
        "base_currency":      base_currency,
        "multi_currency":     True,
    }
    chart = {
        "type": "bar",
        "title": f"Payables by Aging Bucket ({base_currency})",
        "labels": list(buckets.keys()),
        "datasets": [{"name": f"Outstanding ({base_currency})", "values": [round(v, 2) for v in buckets.values()]}],
    }

    top_supplier_name = top_suppliers[0]["supplier"] if top_suppliers else "N/A"
    return {
        "status": "ok",
        "invoice_count":    len(rows),
        "total_payable":    total_payable,
        "invoices":         rows[:50],
        "aging_buckets":    buckets,
        "top_suppliers":    top_suppliers,
        "upcoming_due":     upcoming_due,
        "metrics":          metrics,
        "chart":            chart,
        "message": (
            f"{len(rows)} outstanding purchase invoices totaling {base_currency} {total_payable:,.0f} (base currency) "
            f"across {suppliers_affected} suppliers. "
            f"{base_currency} {due_next_7d_amt:,.0f} due in the next 7 days. "
            f"Largest exposure: {top_supplier_name}."
        ),
    }


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  FEATURE 3 — CUSTOMER FOLLOW-UP ASSISTANT                                   ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

def get_inactive_customers(days_inactive: int = 60) -> dict:
    """Customers who have had no Sales Invoice in the last N days."""
    cutoff = add_days(today(), -days_inactive)
    today_str = today()

    # Single query: fetch all customers with their last invoice date
    last_inv_rows = frappe.db.sql("""
        SELECT
            c.name,
            c.customer_name,
            c.mobile_no,
            c.customer_group,
            MAX(si.posting_date) AS last_invoice_date
        FROM `tabCustomer` c
        LEFT JOIN `tabSales Invoice` si
            ON si.customer = c.name AND si.docstatus = 1
        GROUP BY c.name, c.customer_name, c.mobile_no, c.customer_group
        HAVING last_invoice_date IS NULL OR last_invoice_date < %s
        ORDER BY last_invoice_date ASC
        LIMIT 300
    """, (cutoff,), as_dict=True)

    inactive = []
    for row in last_inv_rows:
        last = row.get("last_invoice_date")
        inactive.append({
            "name": row["name"],
            "customer_name": row["customer_name"],
            "mobile_no": row["mobile_no"],
            "customer_group": row["customer_group"],
            "last_purchase_date": str(last) if last else "Never",
            "days_inactive": date_diff(today_str, str(last)) if last else 9999,
        })

    inactive.sort(key=lambda x: -(x.get("days_inactive") or 0))
    inactive = inactive[:30]

    return {
        "status": "ok",
        "threshold_days": days_inactive,
        "inactive_count": len(inactive),
        "customers": inactive,
        "message": f"{len(inactive)} customers inactive for {days_inactive}+ days.",
    }


def get_unconverted_quotations(days_old: int = 14) -> dict:
    """Open quotations older than N days that have never become a Sales Order."""
    cutoff = add_days(today(), -days_old)
    rows = frappe.get_all(
        "Quotation",
        filters={
            "docstatus": ["in", [0, 1]],
            "status": ["in", ["Open", "Draft"]],
            "transaction_date": ["<=", cutoff],
        },
        fields=["name", "party_name", "transaction_date", "valid_till",
                "grand_total", "status"],
        order_by="grand_total desc",
        limit=30,
    )
    for r in rows:
        if r.get("transaction_date"):
            r["days_old"] = date_diff(today(), str(r["transaction_date"]))
    total_value = sum(flt(r.get("grand_total")) for r in rows)
    return {
        "status": "ok",
        "threshold_days": days_old,
        "count": len(rows),
        "total_value": total_value,
        "quotations": rows,
        "message": f"{len(rows)} unconverted quotations older than {days_old} days worth {total_value:,.0f}.",
    }


def get_customers_with_overdue_balance() -> dict:
    """Customers with outstanding invoices past due date, grouped and ranked."""
    rows = frappe.db.sql("""
        SELECT customer,
               COUNT(*)                AS invoice_count,
               SUM(outstanding_amount * COALESCE(conversion_rate, 1)) AS total_outstanding,
               MIN(due_date)           AS oldest_due_date,
               DATEDIFF(CURDATE(), MIN(due_date)) AS max_days_overdue
        FROM `tabSales Invoice`
        WHERE docstatus=1
          AND outstanding_amount > 0
          AND due_date < CURDATE()
        GROUP BY customer
        ORDER BY total_outstanding DESC
        LIMIT 20
    """, as_dict=True)
    total = sum(flt(r.get("total_outstanding")) for r in rows)
    base_currency = get_base_currency()
    return {
        "status": "ok",
        "customer_count": len(rows),
        "total_overdue": total,
        "base_currency": base_currency,
        "customers": [dict(r) for r in rows],
        "message": f"{len(rows)} customers with overdue balances totaling {base_currency} {total:,.0f} (base currency).",
    }


def get_customers_without_recent_orders(days: int = 90) -> dict:
    """High-value customers who have not purchased in the last N days."""
    cutoff = add_days(today(), -days)

    # Customers who purchased before the cutoff (lapsed)
    lapsed = frappe.db.sql("""
        SELECT si.customer,
               MAX(si.posting_date)      AS last_purchase,
               SUM(si.base_grand_total)  AS lifetime_value,
               COUNT(*)                  AS total_invoices
        FROM `tabSales Invoice` si
        WHERE si.docstatus=1 AND si.posting_date < %s
        GROUP BY si.customer
    """, (cutoff,), as_dict=True)

    # Customers who DID buy recently (exclude from lapsed)
    recent = frappe.db.sql("""
        SELECT DISTINCT customer FROM `tabSales Invoice`
        WHERE docstatus=1 AND posting_date >= %s
    """, (cutoff,), as_dict=True)
    recent_set = {r["customer"] for r in recent}

    result = []
    for r in lapsed:
        if r["customer"] in recent_set:
            continue
        r["days_since_purchase"] = date_diff(today(), str(r["last_purchase"]))
        result.append(dict(r))

    result.sort(key=lambda x: -flt(x.get("lifetime_value", 0)))
    result = result[:20]

    return {
        "status": "ok",
        "threshold_days": days,
        "count": len(result),
        "customers": result,
        "message": f"{len(result)} previously active customers haven't ordered in {days}+ days.",
    }


def get_followup_opportunities() -> dict:
    """
    Composite follow-up analysis. Returns prioritised action items
    across overdue payments, stale quotations, and lapsed customers.
    """
    opportunities = []

    # 1 — Overdue balances (HIGH)
    overdue = frappe.db.sql("""
        SELECT customer,
               SUM(outstanding_amount * COALESCE(conversion_rate, 1)) AS total_owed,
               COUNT(*)                AS inv_count,
               DATEDIFF(CURDATE(), MIN(due_date)) AS days_overdue
        FROM `tabSales Invoice`
        WHERE docstatus=1 AND outstanding_amount>0 AND due_date < CURDATE()
        GROUP BY customer ORDER BY total_owed DESC LIMIT 10
    """, as_dict=True)
    for r in overdue:
        opportunities.append({
            "type": "overdue_payment",
            "priority": "high",
            "customer": r["customer"],
            "reason": f"Overdue balance {flt(r['total_owed']):,.0f} ({r['inv_count']} invoices, {r.get('days_overdue',0)} days overdue)",
            "suggested_action": "Call customer and arrange payment",
            "potential_value": flt(r["total_owed"]),
            "quick_actions": ["record_payment", "create_issue"],
        })

    # 2 — Old high-value quotations (HIGH/MEDIUM)
    old_q = frappe.get_all("Quotation",
        filters={"docstatus": ["in", [0, 1]], "status": ["in", ["Open", "Draft"]],
                 "transaction_date": ["<=", add_days(today(), -7)]},
        fields=["name", "party_name", "grand_total", "transaction_date", "valid_till"],
        order_by="grand_total desc", limit=10,
    )
    for q in old_q:
        expiring = q.get("valid_till") and str(q["valid_till"]) <= add_days(today(), 3)
        opportunities.append({
            "type": "unconverted_quotation",
            "priority": "high" if expiring else "medium",
            "customer": q["party_name"],
            "reason": f"Quotation {q['name']} worth {flt(q['grand_total']):,.0f} pending since {q['transaction_date']}",
            "suggested_action": "Follow up and close as order",
            "quotation": q["name"],
            "potential_value": flt(q["grand_total"]),
            "expiring_soon": bool(expiring),
            "quick_actions": ["convert_quotation_to_sales_order", "create_task"],
        })

    # 3 — Lapsed high-value customers (MEDIUM)
    cutoff90 = add_days(today(), -90)
    recent_buyers = frappe.db.sql(
        "SELECT DISTINCT customer FROM `tabSales Invoice` WHERE docstatus=1 AND posting_date>=%s",
        (cutoff90,), as_dict=True,
    )
    recent_set = {r["customer"] for r in recent_buyers}
    lapsed = frappe.db.sql("""
        SELECT customer, MAX(posting_date) AS last_date, SUM(base_grand_total) AS ltv
        FROM `tabSales Invoice` WHERE docstatus=1 AND posting_date < %s
        GROUP BY customer ORDER BY ltv DESC LIMIT 5
    """, (cutoff90,), as_dict=True)
    for r in lapsed:
        if r["customer"] not in recent_set:
            opportunities.append({
                "type": "lapsed_customer",
                "priority": "medium",
                "customer": r["customer"],
                "reason": f"No order since {r['last_date']}. Lifetime value: {flt(r['ltv']):,.0f}",
                "suggested_action": "Re-engage with call or new quotation",
                "potential_value": 0,
                "quick_actions": ["create_quotation", "create_task"],
            })

    # Sort: high first, then by potential_value
    order = {"high": 0, "medium": 1, "low": 2}
    opportunities.sort(key=lambda o: (order.get(o.get("priority", "low"), 2),
                                       -o.get("potential_value", 0)))

    return {
        "status": "ok",
        "total_opportunities": len(opportunities),
        "high_priority": sum(1 for o in opportunities if o.get("priority") == "high"),
        "medium_priority": sum(1 for o in opportunities if o.get("priority") == "medium"),
        "total_potential_value": sum(o.get("potential_value", 0) for o in opportunities),
        "opportunities": opportunities,
        "message": (
            f"{len(opportunities)} follow-up opportunities. "
            f"{sum(1 for o in opportunities if o['priority']=='high')} high priority. "
            f"Potential value: {sum(o.get('potential_value',0) for o in opportunities):,.0f}."
        ),
    }


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  FEATURE 4 — WORKSHOP SERVICE ADVISOR / VEHICLE DIAGNOSTICS                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

_SYMPTOM_KB: dict[str, dict] = {
    # ── Engine ────────────────────────────────────────────────────────
    "check engine light": {
        "possible_causes": [
            "Oxygen sensor failure", "Catalytic converter degraded",
            "Mass airflow sensor dirty/faulty", "Spark plug or ignition coil failure",
            "Loose or damaged fuel cap", "EGR valve issue",
        ],
        "recommended_checks": [
            "OBD-II scan for fault codes",
            "Inspect oxygen sensors",
            "Check fuel cap seal",
            "Inspect spark plugs and ignition coils",
            "Test mass airflow sensor",
        ],
        "recommended_parts": [
            "OBD-II Scanner (diagnostic)",
            "Oxygen Sensor",
            "Spark Plugs Set",
            "Ignition Coil",
            "Fuel Cap",
            "MAF Sensor Cleaner",
        ],
        "estimated_labour_hours": 1.5,
    },
    "engine vibration": {
        "possible_causes": [
            "Worn or fouled spark plugs",
            "Faulty ignition coil",
            "Clogged fuel injectors",
            "Vacuum leak",
            "Damaged engine mount",
            "Loose or broken drive belt",
        ],
        "recommended_checks": [
            "Spark plug condition and gap check",
            "Ignition coil resistance test",
            "Fuel injector cleaning / test",
            "Vacuum hose inspection",
            "Engine mount visual inspection",
            "Belt tension and condition check",
        ],
        "recommended_parts": [
            "Spark Plugs Set",
            "Ignition Coil",
            "Fuel Injector Cleaner",
            "Engine Mount",
            "Drive Belt",
        ],
        "estimated_labour_hours": 2.5,
    },
    "poor fuel economy": {
        "possible_causes": [
            "Dirty or failing oxygen sensor",
            "Clogged air filter",
            "Worn spark plugs causing misfires",
            "Fuel injectors leaking or dirty",
            "Tyre under-inflation",
            "Thermostat stuck open",
        ],
        "recommended_checks": [
            "Read live O2 sensor data via OBD",
            "Inspect and replace air filter",
            "Check spark plug condition",
            "Fuel injector flow test",
            "Tyre pressure check (all 4 wheels)",
            "Coolant temperature monitoring",
        ],
        "recommended_parts": [
            "Oxygen Sensor",
            "Air Filter",
            "Spark Plugs Set",
            "Fuel System Cleaner",
            "Thermostat",
        ],
        "estimated_labour_hours": 2.0,
    },
    "engine overheating": {
        "possible_causes": [
            "Coolant leak (hose, gasket, or radiator)",
            "Thermostat stuck closed",
            "Failing water pump",
            "Blocked or damaged radiator",
            "Blown head gasket",
            "Faulty cooling fan",
        ],
        "recommended_checks": [
            "Check coolant level and inspect for leaks",
            "Pressure test cooling system",
            "Test thermostat operation",
            "Inspect water pump for leaks/noise",
            "Radiator flow test",
            "Head gasket compression test",
        ],
        "recommended_parts": [
            "Coolant / Antifreeze",
            "Thermostat",
            "Water Pump",
            "Radiator Hoses",
            "Radiator Cap",
            "Coolant Temperature Sensor",
        ],
        "estimated_labour_hours": 3.0,
    },
    "oil leak": {
        "possible_causes": [
            "Degraded valve cover gasket",
            "Crankshaft or camshaft seal failure",
            "Damaged oil pan or drain plug",
            "Failing oil pressure sensor",
        ],
        "recommended_checks": [
            "Identify leak source with UV dye or degreasing + visual",
            "Inspect valve cover gasket",
            "Check all seals and gaskets",
            "Inspect oil drain plug threads",
        ],
        "recommended_parts": [
            "Valve Cover Gasket",
            "Crankshaft Seal",
            "Oil Pan Gasket",
            "Oil Drain Plug",
            "Engine Oil",
        ],
        "estimated_labour_hours": 2.5,
    },
    # ── Brakes ────────────────────────────────────────────────────────
    "brakes squeaking": {
        "possible_causes": [
            "Worn brake pads (wear indicator contact)",
            "Glazed rotors",
            "Dust or debris between pad and rotor",
            "Low-quality brake pads",
        ],
        "recommended_checks": [
            "Measure brake pad thickness",
            "Inspect rotor surface for scoring/glazing",
            "Check caliper slide pins for corrosion",
        ],
        "recommended_parts": [
            "Brake Pads (front set)",
            "Brake Pads (rear set)",
            "Brake Rotors",
            "Brake Cleaner",
            "Caliper Slide Pin Grease",
        ],
        "estimated_labour_hours": 2.0,
    },
    "brakes grinding": {
        "possible_causes": [
            "Completely worn brake pads (metal on metal)",
            "Loose or missing rotor hardware",
            "Foreign object lodged in caliper",
        ],
        "recommended_checks": [
            "Immediate wheel removal for pad/rotor inspection",
            "Measure rotor thickness",
            "Inspect caliper pistons",
        ],
        "recommended_parts": [
            "Brake Pads Set",
            "Brake Rotors (likely damaged)",
            "Brake Fluid",
            "Caliper Rebuild Kit",
        ],
        "estimated_labour_hours": 2.5,
        "urgency": "immediate",
    },
    "brake pedal soft / spongy": {
        "possible_causes": [
            "Air in brake lines",
            "Brake fluid leak",
            "Failing brake master cylinder",
            "Deteriorated brake hoses",
        ],
        "recommended_checks": [
            "Inspect all brake lines and hoses for leaks",
            "Check brake fluid level and colour",
            "Bleed brake system",
            "Test master cylinder operation",
        ],
        "recommended_parts": [
            "Brake Fluid (DOT 4)",
            "Brake Hose Set",
            "Brake Master Cylinder",
        ],
        "estimated_labour_hours": 2.0,
        "urgency": "immediate",
    },
    # ── Suspension / Steering ─────────────────────────────────────────
    "vibration at speed": {
        "possible_causes": [
            "Wheel imbalance",
            "Bent or damaged rim",
            "Worn or loose wheel hub bearing",
            "Worn CV joint or driveshaft",
            "Suspension component wear (tie rod, ball joint)",
        ],
        "recommended_checks": [
            "Wheel balance and alignment check",
            "Visual inspection of rims for bending",
            "Hub bearing play test",
            "CV joint boot inspection",
            "Steering component inspection",
        ],
        "recommended_parts": [
            "Wheel Balancing (service)",
            "Wheel Bearing Hub Assembly",
            "CV Axle / Driveshaft",
            "Tie Rod End",
            "Ball Joint",
        ],
        "estimated_labour_hours": 2.0,
    },
    "steering pulling": {
        "possible_causes": [
            "Wheel alignment out of spec",
            "Uneven tyre pressure",
            "Worn tie rod ends",
            "Brake caliper sticking (one side dragging)",
            "Wheel bearing play",
        ],
        "recommended_checks": [
            "4-wheel alignment measurement",
            "Check tyre pressures (all wheels)",
            "Inspect tie rod ends for play",
            "Check brake caliper for binding",
            "Hub bearing check",
        ],
        "recommended_parts": [
            "Wheel Alignment (service)",
            "Tie Rod Ends",
            "Tyres (if uneven wear pattern)",
        ],
        "estimated_labour_hours": 1.5,
    },
    "clunking noise suspension": {
        "possible_causes": [
            "Worn shock absorbers or struts",
            "Loose sway bar link or end links",
            "Worn control arm bushings",
            "Damaged strut mount bearing",
            "Loose ball joint",
        ],
        "recommended_checks": [
            "Bounce test on each corner",
            "Inspect shock / strut for leaks",
            "Check sway bar links",
            "Inspect bushings with pry bar",
            "Ball joint play test",
        ],
        "recommended_parts": [
            "Shock Absorbers / Struts (pair)",
            "Sway Bar Links",
            "Control Arm Bushings",
            "Strut Mount Bearing",
            "Ball Joints",
        ],
        "estimated_labour_hours": 3.0,
    },
    # ── Electrical ────────────────────────────────────────────────────
    "battery warning light": {
        "possible_causes": [
            "Failing alternator",
            "Weak or dead battery",
            "Loose or corroded battery terminals",
            "Broken serpentine belt (drives alternator)",
        ],
        "recommended_checks": [
            "Battery load test",
            "Alternator output voltage test (should be 13.8–14.4V)",
            "Inspect serpentine belt tension and condition",
            "Clean and tighten battery terminals",
        ],
        "recommended_parts": [
            "Car Battery",
            "Alternator",
            "Serpentine Belt",
            "Battery Terminal Connectors",
        ],
        "estimated_labour_hours": 1.5,
    },
    "ac not cooling": {
        "possible_causes": [
            "Low refrigerant level (leak)",
            "Faulty AC compressor or clutch",
            "Blocked condenser",
            "Faulty expansion valve",
            "Blower motor failure",
        ],
        "recommended_checks": [
            "AC system pressure test",
            "Leak detection dye test",
            "Inspect condenser for blockage",
            "Test compressor clutch engagement",
            "Check cabin air filter",
        ],
        "recommended_parts": [
            "AC Refrigerant R134a",
            "AC Compressor",
            "Cabin Air Filter",
            "Expansion Valve",
            "AC Leak Sealant (temporary)",
        ],
        "estimated_labour_hours": 2.5,
    },
    # ── Transmission ──────────────────────────────────────────────────
    "transmission slipping": {
        "possible_causes": [
            "Low transmission fluid",
            "Worn clutch pack (automatic)",
            "Faulty solenoid",
            "Torque converter failure",
        ],
        "recommended_checks": [
            "Transmission fluid level and colour check",
            "Transmission fault code scan",
            "Fluid pressure test",
            "Road test under load",
        ],
        "recommended_parts": [
            "Automatic Transmission Fluid",
            "Transmission Filter Kit",
            "Solenoid Pack",
        ],
        "estimated_labour_hours": 3.5,
    },
}

# Aliases map — common user phrasing → KB key
_ALIASES: dict[str, str] = {
    "engine light": "check engine light",
    "cel": "check engine light",
    "mil": "check engine light",
    "shaking": "engine vibration",
    "vibration": "engine vibration",
    "rough idle": "engine vibration",
    "fuel consumption": "poor fuel economy",
    "high fuel consumption": "poor fuel economy",
    "fuel economy": "poor fuel economy",
    "bad mpg": "poor fuel economy",
    "overheating": "engine overheating",
    "temperature light": "engine overheating",
    "temp warning": "engine overheating",
    "oil leaking": "oil leak",
    "oil puddle": "oil leak",
    "squeaking brakes": "brakes squeaking",
    "brake squeal": "brakes squeaking",
    "grinding brakes": "brakes grinding",
    "brake grinding": "brakes grinding",
    "spongy brake": "brake pedal soft / spongy",
    "soft brake": "brake pedal soft / spongy",
    "brake soft": "brake pedal soft / spongy",
    "shakes at speed": "vibration at speed",
    "highway vibration": "vibration at speed",
    "pulls to one side": "steering pulling",
    "car pulling": "steering pulling",
    "clunking": "clunking noise suspension",
    "banging noise": "clunking noise suspension",
    "suspension noise": "clunking noise suspension",
    "battery light": "battery warning light",
    "no start": "battery warning light",
    "dead battery": "battery warning light",
    "air conditioning": "ac not cooling",
    "ac not working": "ac not cooling",
    "no cold air": "ac not cooling",
    "gear slipping": "transmission slipping",
    "slipping gears": "transmission slipping",
    "transmission": "transmission slipping",
}

# Generic recommendations by vehicle make (manufacturer-specific notes)
_MAKE_NOTES: dict[str, str] = {
    "toyota": "Toyota vehicles have strong reliability records; focus on genuine Toyota/OEM parts.",
    "honda": "Honda VTEC engines are sensitive to oil quality — use specified viscosity grade.",
    "nissan": "Nissan CVT transmissions require CVT-specific fluid; avoid generic ATF.",
    "hyundai": "Hyundai offers extended powertrain warranty — check warranty coverage before repair.",
    "kia": "Kia Theta II engine recall may apply — verify serial number.",
    "ford": "Ford EcoBoost engines can develop carbon buildup — walnut blasting recommended every 60k km.",
    "gm": "GM AFM lifter failures common on V8 models — check for GM TSB.",
    "chevrolet": "Same as GM: AFM deactivation issues on 5.3L/6.2L engines.",
    "bmw": "BMW requires OEM-spec engine oil (LL-01/LL-04); generic oil shortens engine life.",
    "mercedes": "Mercedes-Benz requires MB-approved fluids; use dealer-grade diagnostics (Xentry).",
    "audi": "Audi DSG/S-tronic fluid intervals are critical — check manufacturer schedule.",
    "volkswagen": "VW PD/TDI injectors are expensive; verify injector seals before diagnostics.",
    "mitsubishi": "Mitsubishi CVT (INVECS-III) requires CVT-J4 fluid specifically.",
    "mazda": "Mazda SkyActiv engines specify 0W-20 oil; heavier grades reduce efficiency.",
    "subaru": "Subaru boxer engines prone to head gasket issues (EJ series) — pressure test recommended.",
    "jeep": "Jeep 3.6L Pentastar engines: check valve train noise and oil consumption.",
}


def diagnose_vehicle_issue(
    vehicle_make: str = "",
    vehicle_model: str = "",
    symptoms: list | None = None,
    year: int = 0,
) -> dict:
    """
    AI-powered vehicle diagnostics.

    Matches reported symptoms against the knowledge base and returns:
    possible_causes, recommended_checks, recommended_parts, estimated_labour_hours,
    plus an optional workshop quotation suggestion.
    """
    if not symptoms:
        return {
            "status": "error",
            "message": "Please describe the symptom(s) you are experiencing.",
        }

    symptoms = [str(s).lower().strip() for s in symptoms]

    # Match symptoms to KB entries
    matched_keys: list[str] = []
    for symptom in symptoms:
        # Direct match
        if symptom in _SYMPTOM_KB:
            matched_keys.append(symptom)
            continue
        # Alias match
        if symptom in _ALIASES and _ALIASES[symptom] in _SYMPTOM_KB:
            matched_keys.append(_ALIASES[symptom])
            continue
        # Partial / substring match in KB keys
        for kb_key in _SYMPTOM_KB:
            if symptom in kb_key or kb_key in symptom:
                matched_keys.append(kb_key)
                break
        # Partial match in aliases
        else:
            for alias, kb_key in _ALIASES.items():
                if symptom in alias or alias in symptom:
                    if kb_key in _SYMPTOM_KB:
                        matched_keys.append(kb_key)
                        break

    matched_keys = list(dict.fromkeys(matched_keys))  # deduplicate preserving order

    if not matched_keys:
        return {
            "status": "ok",
            "vehicle": f"{year} {vehicle_make} {vehicle_model}".strip(),
            "symptoms_received": symptoms,
            "matched": False,
            "possible_causes": [
                "Unable to match symptoms to known patterns.",
                "Recommend OBD scan to retrieve fault codes.",
            ],
            "recommended_checks": [
                "Full OBD-II diagnostic scan",
                "Visual inspection by qualified technician",
            ],
            "recommended_parts": [],
            "estimated_labour_hours": 1.0,
            "make_note": _MAKE_NOTES.get(vehicle_make.lower(), ""),
            "message": f"Symptoms logged for {vehicle_make} {vehicle_model}. Recommend OBD scan as first step.",
        }

    # Aggregate from all matched entries
    all_causes: list[str] = []
    all_checks: list[str] = []
    all_parts: list[str] = []
    total_hours = 0.0
    urgency = ""

    for key in matched_keys:
        entry = _SYMPTOM_KB[key]
        all_causes.extend(entry.get("possible_causes", []))
        all_checks.extend(entry.get("recommended_checks", []))
        all_parts.extend(entry.get("recommended_parts", []))
        total_hours += entry.get("estimated_labour_hours", 1.0)
        if entry.get("urgency") == "immediate":
            urgency = "immediate"

    # Deduplicate while preserving order
    def _dedup(lst: list) -> list:
        seen: set = set()
        out = []
        for x in lst:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    possible_causes = _dedup(all_causes)[:8]
    recommended_checks = _dedup(all_checks)[:8]
    recommended_parts = _dedup(all_parts)[:10]

    # Check if any parts exist in ERPNext Item master
    erp_parts = []
    for part in recommended_parts:
        matches = frappe.get_all("Item",
            filters=[["item_name", "like", f"%{part.split('(')[0].strip()}%"],
                     ["disabled", "=", 0]],
            fields=["name", "item_name", "standard_rate"],
            limit=1)
        if matches:
            erp_parts.append(matches[0])

    make_lower = vehicle_make.lower()
    make_note = _MAKE_NOTES.get(make_lower, "")
    if not make_note:
        for mk, note in _MAKE_NOTES.items():
            if mk in make_lower or make_lower in mk:
                make_note = note
                break

    vehicle_str = " ".join(filter(None, [str(year) if year else "", vehicle_make, vehicle_model]))

    return {
        "status": "ok",
        "vehicle": vehicle_str.strip(),
        "symptoms_received": symptoms,
        "symptoms_matched": matched_keys,
        "matched": True,
        "urgency": urgency or "routine",
        "possible_causes": possible_causes,
        "recommended_checks": recommended_checks,
        "recommended_parts": recommended_parts,
        "erp_parts_available": erp_parts,
        "estimated_labour_hours": round(total_hours, 1),
        "make_note": make_note,
        "message": (
            f"Diagnosis for {vehicle_str}. "
            f"{len(possible_causes)} possible causes identified. "
            f"Estimated labour: {round(total_hours, 1)} hours. "
            + (f"⚠ URGENT — {urgency} attention needed." if urgency == "immediate" else "")
        ),
    }


# ══════════════════════════════════════════════════════════════════════════════
# COMPOSITE CROSS-MODULE TOOLS
# ══════════════════════════════════════════════════════════════════════════════


def get_so_invoice_gap(days: int = 30) -> dict:
    """Revenue leakage: Sales Orders fulfilled but not invoiced / not yet paid."""
    try:
        from frappe.utils import add_days, nowdate

        base_curr = get_base_currency()
        from_date = add_days(nowdate(), -int(days))

        so_list = frappe.get_all(
            "Sales Order",
            filters=[
                ["docstatus", "=", 1],
                ["status", "in", ["To Bill", "To Deliver and Bill", "Completed"]],
                ["transaction_date", ">=", from_date],
            ],
            fields=["name", "customer", "transaction_date", "base_grand_total",
                    "currency", "status"],
            order_by="transaction_date desc",
            limit=500,
        )

        data = []
        not_inv_count = 0;  not_inv_val = 0.0
        inv_unpaid_count = 0;  inv_unpaid_val = 0.0
        fully_paid_count = 0
        total_val = 0.0

        for so in so_list:
            total_val += flt(so.base_grand_total)
            inv_items = frappe.get_all(
                "Sales Invoice Item",
                filters=[["sales_order", "=", so.name], ["docstatus", "=", 1]],
                fields=["parent"],
                limit=1,
            )
            if not inv_items:
                inv_status = "Not Invoiced"
                not_inv_count += 1
                not_inv_val += flt(so.base_grand_total)
            else:
                outstanding = flt(frappe.db.get_value(
                    "Sales Invoice", inv_items[0].parent, "outstanding_amount") or 0)
                if outstanding <= 0:
                    inv_status = "Fully Paid"
                    fully_paid_count += 1
                else:
                    inv_status = "Invoiced Unpaid"
                    inv_unpaid_count += 1
                    inv_unpaid_val += flt(so.base_grand_total)

            if inv_status != "Fully Paid":
                row = {k: so[k] for k in so}
                row["base_grand_total"] = flt(so.base_grand_total)
                row["invoice_status"]   = inv_status
                data.append(row)

        value_at_risk     = not_inv_val + inv_unpaid_val
        collection_gap_pct = round(value_at_risk / total_val * 100, 1) if total_val else 0.0

        return {
            "status":   "ok",
            "intent":   "get_so_invoice_gap",
            "multi_currency": False,
            "metrics": {
                "base_currency":         base_curr,
                "period_days":           int(days),
                "total_orders":          len(so_list),
                "not_invoiced_count":    not_inv_count,
                "not_invoiced_value":    round(not_inv_val, 2),
                "invoiced_unpaid_count": inv_unpaid_count,
                "invoiced_unpaid_value": round(inv_unpaid_val, 2),
                "fully_paid_count":      fully_paid_count,
                "value_at_risk":         round(value_at_risk, 2),
                "collection_gap_pct":    collection_gap_pct,
            },
            "chart": {
                "type":   "bar",
                "title":  "Sales Order Billing Status",
                "labels": ["Not Invoiced", "Invoiced Unpaid", "Fully Paid"],
                "datasets": [{"name": "Orders",
                               "values": [not_inv_count, inv_unpaid_count, fully_paid_count]}],
            },
            "data": data,
            "message": (
                f"{not_inv_count + inv_unpaid_count} orders worth "
                f"{base_curr} {not_inv_val + inv_unpaid_val:,.0f} have not been fully invoiced or collected. "
                f"Revenue at risk: {base_curr} {value_at_risk:,.0f}."
            ),
        }
    except Exception as exc:
        frappe.log_error(title="get_so_invoice_gap failed", message=str(exc))
        return {"status": "error", "data": [],
                "message": "Could not load SO invoice gap report. Please try again."}


def get_sales_pipeline_status(days: int = 90) -> dict:
    """Full funnel: Quotation → Sales Order → Invoice → Payment with conversion rates."""
    try:
        from frappe.utils import add_days, nowdate, date_diff

        base_curr = get_base_currency()
        from_date = add_days(nowdate(), -int(days))

        quotes = frappe.get_all(
            "Quotation",
            filters=[["docstatus", "=", 1], ["transaction_date", ">=", from_date]],
            fields=["name", "party_name", "transaction_date", "base_grand_total",
                    "currency", "status"],
            limit=1000,
        )
        total_quotes      = len(quotes)
        pipeline_val_quotes = sum(flt(q.base_grand_total) for q in quotes)

        # quotes → SO
        converted_names   = set()
        pipeline_val_orders = 0.0
        days_q_so         = []
        for q in quotes:
            so_items = frappe.get_all(
                "Sales Order Item",
                filters=[["prevdoc_docname", "=", q.name], ["docstatus", "=", 1]],
                fields=["parent"],
                limit=1,
            )
            sos = []
            if so_items:
                so_data = frappe.db.get_value(
                    "Sales Order",
                    so_items[0].parent,
                    ["name", "transaction_date", "base_grand_total"],
                    as_dict=True,
                )
                if so_data:
                    sos = [so_data]
            if sos:
                converted_names.add(q.name)
                pipeline_val_orders += flt(sos[0].base_grand_total)
                delta = date_diff(str(sos[0].transaction_date), str(q.transaction_date))
                if delta >= 0:
                    days_q_so.append(delta)

        # SO → Invoice
        invoiced_names    = set()
        pipeline_val_inv  = 0.0
        days_so_inv       = []
        for q in quotes:
            if q.name not in converted_names:
                continue
            so_items = frappe.get_all(
                "Sales Order Item",
                filters=[["prevdoc_docname", "=", q.name], ["docstatus", "=", 1]],
                fields=["parent"],
                limit=1,
            )
            sos = []
            if so_items:
                so_data = frappe.db.get_value(
                    "Sales Order",
                    so_items[0].parent,
                    ["name", "transaction_date"],
                    as_dict=True,
                )
                if so_data:
                    sos = [so_data]
            if not sos:
                continue
            so = sos[0]
            inv_items = frappe.get_all(
                "Sales Invoice Item",
                filters=[["sales_order", "=", so.name], ["docstatus", "=", 1]],
                fields=["parent"],
                limit=1,
            )
            if inv_items:
                invoiced_names.add(q.name)
                inv = frappe.db.get_value(
                    "Sales Invoice", inv_items[0].parent,
                    ["posting_date", "base_grand_total"], as_dict=True)
                if inv:
                    pipeline_val_inv += flt(inv.base_grand_total)
                    delta = date_diff(str(inv.posting_date), str(so.transaction_date))
                    if delta >= 0:
                        days_so_inv.append(delta)

        # Invoice → Paid
        invoices_paid     = 0
        pipeline_val_coll = 0.0
        for q in quotes:
            if q.name not in invoiced_names:
                continue
            so_items = frappe.get_all(
                "Sales Order Item",
                filters=[["prevdoc_docname", "=", q.name], ["docstatus", "=", 1]],
                fields=["parent"],
                limit=1,
            )
            sos = []
            if so_items:
                so_data = frappe.db.get_value(
                    "Sales Order",
                    so_items[0].parent,
                    ["name", "transaction_date"],
                    as_dict=True,
                )
                if so_data:
                    sos = [so_data]
            if not sos:
                continue
            inv_items = frappe.get_all(
                "Sales Invoice Item",
                filters=[["sales_order", "=", sos[0].name], ["docstatus", "=", 1]],
                fields=["parent"],
                limit=1,
            )
            if not inv_items:
                continue
            outstanding = flt(frappe.db.get_value(
                "Sales Invoice", inv_items[0].parent, "outstanding_amount") or 0)
            if outstanding <= 0:
                invoices_paid += 1
                pipeline_val_coll += flt(frappe.db.get_value(
                    "Sales Invoice", inv_items[0].parent, "base_grand_total") or 0)

        converted_to_order = len(converted_names)
        orders_invoiced    = len(invoiced_names)
        q2o  = round(converted_to_order / total_quotes * 100, 1) if total_quotes else 0.0
        o2i  = round(orders_invoiced    / converted_to_order * 100, 1) if converted_to_order else 0.0
        i2p  = round(invoices_paid      / orders_invoiced * 100, 1) if orders_invoiced else 0.0
        q2c  = round(invoices_paid      / total_quotes * 100, 1) if total_quotes else 0.0
        avg_q2so = round(sum(days_q_so) / len(days_q_so), 1) if days_q_so else 0.0
        avg_so2inv = round(sum(days_so_inv) / len(days_so_inv), 1) if days_so_inv else 0.0

        today_str = nowdate()
        open_quotes = sorted(
            [
                dict(q,
                     base_grand_total=flt(q.base_grand_total),
                     days_open=date_diff(today_str, str(q.transaction_date)))
                for q in quotes
                if q.name not in converted_names
                   and (q.status or "") not in ("Cancelled", "Lost")
            ],
            key=lambda x: x["base_grand_total"], reverse=True,
        )[:10]

        return {
            "status":   "ok",
            "intent":   "get_sales_pipeline_status",
            "multi_currency": False,
            "metrics": {
                "base_currency":             base_curr,
                "period_days":               int(days),
                "total_quotes":              total_quotes,
                "converted_to_order":        converted_to_order,
                "quote_to_order_pct":        q2o,
                "orders_invoiced":           orders_invoiced,
                "order_to_invoice_pct":      o2i,
                "invoices_paid":             invoices_paid,
                "invoice_to_paid_pct":       i2p,
                "quote_to_cash_pct":         q2c,
                "avg_days_quote_to_order":   avg_q2so,
                "avg_days_order_to_invoice": avg_so2inv,
                "pipeline_value_quotes":     round(pipeline_val_quotes, 2),
                "pipeline_value_orders":     round(pipeline_val_orders, 2),
                "pipeline_value_invoiced":   round(pipeline_val_inv, 2),
                "pipeline_value_collected":  round(pipeline_val_coll, 2),
            },
            "chart": {
                "type":   "bar",
                "title":  "Sales Pipeline Funnel",
                "labels": ["Quotations", "Sales Orders", "Invoices", "Collected"],
                "datasets": [{"name": "Count",
                               "values": [total_quotes, converted_to_order,
                                          orders_invoiced, invoices_paid]}],
            },
            "data": open_quotes,
            "message": (
                f"{total_quotes} quotes created in {days} days. "
                f"Quote-to-cash conversion: {q2c}%. "
                f"Average quote-to-order: {avg_q2so} days."
            ),
        }
    except Exception as exc:
        frappe.log_error(title="get_sales_pipeline_status failed", message=str(exc))
        return {"status": "error", "data": [],
                "message": "Could not load sales pipeline report. Please try again."}


def get_customer_360(customer: str, days: int = 180) -> dict:
    """360° customer profile: revenue, open orders, unpaid invoices, top items, health."""
    try:
        from frappe.utils import add_days, nowdate, date_diff

        if not customer:
            return {"status": "error", "data": [],
                    "message": "Customer name is required."}

        base_curr = get_base_currency()
        from_date = add_days(nowdate(), -int(days))
        today     = nowdate()

        open_orders = frappe.get_all(
            "Sales Order",
            filters=[["customer", "=", customer], ["docstatus", "=", 1],
                     ["status", "not in", ["Completed", "Cancelled"]]],
            fields=["name", "transaction_date", "base_grand_total", "currency", "status"],
            order_by="transaction_date desc",
            limit=50,
        )
        open_orders_val = sum(flt(o.base_grand_total) for o in open_orders)

        unpaid_inv = frappe.get_all(
            "Sales Invoice",
            filters=[["customer", "=", customer], ["docstatus", "=", 1],
                     ["outstanding_amount", ">", 0]],
            fields=["name", "posting_date", "due_date", "base_grand_total",
                    "outstanding_amount", "currency", "conversion_rate"],
            order_by="due_date asc",
            limit=100,
        )
        total_outstanding = sum(
            flt(i.outstanding_amount) * flt(i.conversion_rate or 1) for i in unpaid_inv)
        overdue_amount = sum(
            flt(i.outstanding_amount) * flt(i.conversion_rate or 1)
            for i in unpaid_inv
            if i.due_date and str(i.due_date) < today)

        period_inv = frappe.get_all(
            "Sales Invoice",
            filters=[["customer", "=", customer], ["docstatus", "=", 1],
                     ["posting_date", ">=", from_date]],
            fields=["base_grand_total"],
        )
        total_revenue = sum(flt(i.base_grand_total) for i in period_inv)

        last_so = frappe.get_all(
            "Sales Order",
            filters=[["customer", "=", customer], ["docstatus", "=", 1]],
            fields=["transaction_date"],
            order_by="transaction_date desc",
            limit=1,
        )
        last_order_date = str(last_so[0].transaction_date) if last_so else None

        payments = frappe.get_all(
            "Payment Entry",
            filters=[["party_type", "=", "Customer"], ["party", "=", customer],
                     ["docstatus", "=", 1], ["posting_date", ">=", from_date]],
            fields=["posting_date"],
            order_by="posting_date desc",
            limit=1,
        )
        last_payment_date = str(payments[0].posting_date) if payments else None

        open_quotes = frappe.get_all(
            "Quotation",
            filters=[["party_name", "=", customer], ["docstatus", "=", 1],
                     ["status", "not in", ["Ordered", "Lost", "Cancelled"]]],
            fields=["name", "transaction_date", "base_grand_total", "currency"],
            limit=20,
        )
        open_quotes_val = sum(flt(q.base_grand_total) for q in open_quotes)

        top_items = frappe.db.sql("""
            SELECT sii.item_code, sii.item_name,
                   SUM(sii.qty)         AS total_qty,
                   SUM(sii.base_amount) AS total_amount
            FROM   `tabSales Invoice Item` sii
            JOIN   `tabSales Invoice`      si  ON si.name = sii.parent
            WHERE  si.customer    = %s
              AND  si.docstatus   = 1
              AND  si.posting_date >= %s
            GROUP  BY sii.item_code, sii.item_name
            ORDER  BY total_amount DESC
            LIMIT  5
        """, (customer, from_date), as_dict=True)

        if overdue_amount <= 0:
            health = "Good"
        elif total_outstanding and overdue_amount / total_outstanding < 0.30:
            health = "Warning"
        else:
            health = "Critical"

        return {
            "status":   "ok",
            "intent":   "get_customer_360",
            "multi_currency": False,
            "metrics": {
                "base_currency":     base_curr,
                "customer":          customer,
                "period_days":       int(days),
                "total_revenue":     round(total_revenue, 2),
                "total_outstanding": round(total_outstanding, 2),
                "overdue_amount":    round(overdue_amount, 2),
                "open_orders_count": len(open_orders),
                "open_orders_value": round(open_orders_val, 2),
                "open_quotes_count": len(open_quotes),
                "open_quotes_value": round(open_quotes_val, 2),
                "last_order_date":   last_order_date,
                "last_payment_date": last_payment_date,
                "customer_health":   health,
            },
            "chart": {
                "type":   "bar",
                "title":  f"Customer Activity — {customer} (last {days} days)",
                "labels": ["Revenue", "Outstanding", "Overdue"],
                "datasets": [{"name": base_curr,
                               "values": [round(total_revenue, 2),
                                          round(total_outstanding, 2),
                                          round(overdue_amount, 2)]}],
            },
            "data": {
                "open_orders":     [dict(o, base_grand_total=flt(o.base_grand_total))
                                    for o in open_orders],
                "unpaid_invoices": [dict(i, base_grand_total=flt(i.base_grand_total),
                                        outstanding_amount=flt(i.outstanding_amount))
                                    for i in unpaid_inv],
                "open_quotations": [dict(q, base_grand_total=flt(q.base_grand_total))
                                    for q in open_quotes],
                "top_items":       [dict(r) for r in top_items],
            },
            "message": (
                f"Customer {customer} — Revenue {base_curr} {total_revenue:,.0f} in {days} days. "
                f"Outstanding {base_curr} {total_outstanding:,.0f}. "
                f"Health: {health}."
            ),
        }
    except Exception as exc:
        frappe.log_error(title="get_customer_360 failed", message=str(exc))
        return {"status": "error", "data": [],
                "message": "Could not load customer 360 profile. Please try again."}


def get_po_receipt_gap(days_overdue: int = 0) -> dict:
    """Purchase Orders pending receipt, with stockout risk flags per item."""
    try:
        from frappe.utils import nowdate, date_diff

        base_curr  = get_base_currency()
        today      = nowdate()

        open_pos = frappe.get_all(
            "Purchase Order",
            filters=[["docstatus", "=", 1],
                     ["status", "in", ["To Receive and Bill", "To Receive"]]],
            fields=["name", "supplier", "schedule_date", "base_grand_total",
                    "currency", "status"],
            order_by="schedule_date asc",
            limit=500,
        )

        data = []
        not_recv_count = 0;  not_recv_val = 0.0
        partial_count  = 0
        overdue_days_list  = []
        stockout_risk_count = 0

        for po in open_pos:
            receipts = frappe.get_all(
                "Purchase Receipt Item",
                filters=[["purchase_order", "=", po.name], ["docstatus", "=", 1]],
                fields=["qty"],
                limit=1,
            )
            if not receipts:
                receipt_status = "Not Received"
                not_recv_count += 1
                not_recv_val   += flt(po.base_grand_total)
            else:
                receipt_status = "Partially Received"
                partial_count += 1

            d_overdue = 0
            if po.schedule_date:
                d_overdue = date_diff(today, str(po.schedule_date))
                if d_overdue > 0:
                    overdue_days_list.append(d_overdue)

            if int(days_overdue) > 0 and d_overdue < int(days_overdue):
                continue

            # Stockout risk: any PO item with negative projected_qty in Bin
            po_items = frappe.get_all(
                "Purchase Order Item",
                filters=[["parent", "=", po.name]],
                fields=["item_code"],
            )
            stockout_risk = False
            for pi in po_items:
                if frappe.get_all("Bin",
                                  filters=[["item_code", "=", pi.item_code],
                                           ["projected_qty", "<", 0]],
                                  limit=1):
                    stockout_risk = True
                    break
            if stockout_risk:
                stockout_risk_count += 1

            data.append({
                "name":           po.name,
                "supplier":       po.supplier,
                "schedule_date":  str(po.schedule_date) if po.schedule_date else None,
                "days_overdue":   max(d_overdue, 0),
                "base_grand_total": flt(po.base_grand_total),
                "currency":       po.currency,
                "receipt_status": receipt_status,
                "stockout_risk":  stockout_risk,
            })

        data.sort(key=lambda x: x["days_overdue"], reverse=True)
        avg_overdue    = round(sum(overdue_days_list) / len(overdue_days_list), 1) if overdue_days_list else 0.0

        return {
            "status":   "ok",
            "intent":   "get_po_receipt_gap",
            "multi_currency": False,
            "metrics": {
                "base_currency":            base_curr,
                "total_open_pos":           len(open_pos),
                "not_received_count":       not_recv_count,
                "not_received_value":       round(not_recv_val, 2),
                "partially_received_count": partial_count,
                "avg_days_overdue":         avg_overdue,
                "stockout_risk_count":      stockout_risk_count,
                "total_exposure_value":     round(not_recv_val, 2),
            },
            "chart": {
                "type":   "bar",
                "title":  "Purchase Order Receipt Status",
                "labels": ["Not Received", "Partially Received"],
                "datasets": [{"name": "POs",
                               "values": [not_recv_count, partial_count]}],
            },
            "data": data,
            "message": (
                f"{len(open_pos)} purchase orders worth {base_curr} {not_recv_val:,.0f} pending receipt. "
                f"{len(overdue_days_list)} are overdue. "
                f"{stockout_risk_count} items at stockout risk."
            ),
        }
    except Exception as exc:
        frappe.log_error(title="get_po_receipt_gap failed", message=str(exc))
        return {"status": "error", "data": [],
                "message": "Could not load PO receipt gap report. Please try again."}


def get_monthly_pl_bridge(months: int = 6) -> dict:
    """Monthly P&L bridge: revenue vs purchase cost, gross margin, MoM comparison."""
    try:
        from frappe.utils import nowdate, getdate, get_first_day, get_last_day, add_months

        base_curr = get_base_currency()
        today     = getdate(nowdate())

        rows = []
        for i in range(int(months) - 1, -1, -1):
            month_first = get_first_day(add_months(today, -i))
            month_last  = get_last_day(month_first)
            label       = month_first.strftime("%b %Y")

            rev = frappe.db.sql("""
                SELECT COALESCE(SUM(base_grand_total), 0) AS total
                FROM   `tabSales Invoice`
                WHERE  docstatus = 1
                  AND  posting_date BETWEEN %s AND %s
            """, (str(month_first), str(month_last)), as_dict=True)
            revenue = flt(rev[0].total) if rev else 0.0

            cost_q = frappe.db.sql("""
                SELECT COALESCE(SUM(base_grand_total), 0) AS total
                FROM   `tabPurchase Invoice`
                WHERE  docstatus = 1
                  AND  posting_date BETWEEN %s AND %s
            """, (str(month_first), str(month_last)), as_dict=True)
            cost = flt(cost_q[0].total) if cost_q else 0.0

            gross_profit = revenue - cost
            margin_pct   = round(gross_profit / revenue * 100, 1) if revenue else 0.0

            prev_cost_ratio = (rows[-1]["cost"] / rows[-1]["revenue"]
                               if rows and rows[-1]["revenue"] else 0.0)
            curr_cost_ratio = cost / revenue if revenue else 0.0
            margin_squeeze  = bool(rows and curr_cost_ratio > prev_cost_ratio)

            rows.append({
                "month_label":   label,
                "revenue":       round(revenue, 2),
                "cost":          round(cost, 2),
                "gross_profit":  round(gross_profit, 2),
                "margin_pct":    margin_pct,
                "margin_squeeze": margin_squeeze,
            })

        curr = rows[-1] if rows else {}
        prev = rows[-2] if len(rows) >= 2 else {}

        def _mom(c, p, key):
            pv = p.get(key, 0)
            cv = c.get(key, 0)
            return round((cv - pv) / pv * 100, 1) if pv else 0.0

        ytd_revenue = sum(r["revenue"]      for r in rows)
        ytd_cost    = sum(r["cost"]         for r in rows)
        ytd_gp      = sum(r["gross_profit"] for r in rows)

        rev_mom  = _mom(curr, prev, "revenue")
        cost_mom = _mom(curr, prev, "cost")
        marg_mom = round(curr.get("margin_pct", 0) - prev.get("margin_pct", 0), 1)
        direction = "up" if marg_mom >= 0 else "down"

        return {
            "status":   "ok",
            "intent":   "get_monthly_pl_bridge",
            "multi_currency": False,
            "metrics": {
                "base_currency":               base_curr,
                "months":                      int(months),
                "current_month_revenue":       curr.get("revenue", 0),
                "current_month_cost":          curr.get("cost", 0),
                "current_month_gross_profit":  curr.get("gross_profit", 0),
                "current_month_margin_pct":    curr.get("margin_pct", 0),
                "prev_month_revenue":          prev.get("revenue", 0),
                "prev_month_margin_pct":       prev.get("margin_pct", 0),
                "revenue_mom_pct":             rev_mom,
                "cost_mom_pct":                cost_mom,
                "margin_mom_pct":              marg_mom,
                "margin_squeeze":              curr.get("margin_squeeze", False),
                "ytd_revenue":                 round(ytd_revenue, 2),
                "ytd_cost":                    round(ytd_cost, 2),
                "ytd_gross_profit":            round(ytd_gp, 2),
            },
            "chart": {
                "type":   "composed",
                "title":  f"Revenue vs Cost — Last {months} Months ({base_curr})",
                "labels": [r["month_label"] for r in rows],
                "datasets": [
                    {"name": "Revenue",  "type": "bar",  "values": [r["revenue"]    for r in rows]},
                    {"name": "Cost",     "type": "bar",  "values": [r["cost"]       for r in rows]},
                    {"name": "Margin %", "type": "line", "values": [r["margin_pct"] for r in rows]},
                ],
            },
            "data": rows,
            "message": (
                f"Gross margin this month is {curr.get('margin_pct', 0)}%. "
                f"Revenue {base_curr} {curr.get('revenue', 0):,.0f}, "
                f"cost {base_curr} {curr.get('cost', 0):,.0f}. "
                f"Margin is {direction} {abs(marg_mom):.1f}% vs last month."
            ),
        }
    except Exception as exc:
        frappe.log_error(title="get_monthly_pl_bridge failed", message=str(exc))
        return {"status": "error", "data": [],
                "message": "Could not load P&L bridge report. Please try again."}
