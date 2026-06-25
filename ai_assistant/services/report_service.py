"""
ReportService — unified service layer for business intelligence reports.

Thin class-based wrapper around bi_tools.py that provides a stable,
composable API for Phase 3 (caching, async prefetch, multi-source joins).
"""
from __future__ import annotations


class ReportService:
    """Service layer for business intelligence and analytics reports."""

    def get_monthly_sales_trend(self, months: int = 6) -> dict:
        from ai_assistant.api.bi_tools import get_monthly_sales_trend
        return get_monthly_sales_trend(months)

    def get_top_customers(self, period_days: int = 30, limit: int = 10) -> dict:
        from ai_assistant.api.bi_tools import get_top_customers
        return get_top_customers(period_days, limit)

    def get_top_selling_items(self, period_days: int = 30, limit: int = 10) -> dict:
        from ai_assistant.api.bi_tools import get_top_selling_items
        return get_top_selling_items(period_days, limit)

    def get_pending_quotations(self) -> dict:
        from ai_assistant.api.bi_tools import get_pending_quotations
        return get_pending_quotations()

    def get_overdue_invoices(self) -> dict:
        from ai_assistant.api.bi_tools import get_overdue_invoices
        return get_overdue_invoices()

    def get_stock_alerts(self) -> dict:
        from ai_assistant.api.bi_tools import get_stock_alerts
        return get_stock_alerts()

    def get_open_job_cards(self) -> dict:
        from ai_assistant.api.bi_tools import get_open_job_cards
        return get_open_job_cards()

    def analyze_business(self) -> dict:
        from ai_assistant.api.bi_tools import analyze_business
        return analyze_business()

    def get_management_summary(self) -> dict:
        from ai_assistant.api.bi_tools import get_management_summary
        return get_management_summary()

    def get_inactive_customers(self) -> dict:
        from ai_assistant.api.bi_tools import get_inactive_customers
        return get_inactive_customers()

    def get_unconverted_quotations(self) -> dict:
        from ai_assistant.api.bi_tools import get_unconverted_quotations
        return get_unconverted_quotations()

    def get_customers_with_overdue_balance(self) -> dict:
        from ai_assistant.api.bi_tools import get_customers_with_overdue_balance
        return get_customers_with_overdue_balance()

    def get_sales_order_dashboard(self) -> dict:
        from ai_assistant.api.bi_tools import get_sales_order_dashboard
        return get_sales_order_dashboard()

    def get_sales_pipeline_status(self) -> dict:
        from ai_assistant.api.bi_tools import get_sales_pipeline_status
        return get_sales_pipeline_status()

    def get_monthly_pl_bridge(self) -> dict:
        from ai_assistant.api.bi_tools import get_monthly_pl_bridge
        return get_monthly_pl_bridge()


report_service = ReportService()
