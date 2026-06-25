"""Report Engine — delegates to services/report_service.py."""
from __future__ import annotations

from typing import TYPE_CHECKING

from ai_assistant.engines.base import BaseEngine

if TYPE_CHECKING:
    from ai_assistant.kernel.context_manager import AIContext


class ReportEngine(BaseEngine):
    """
    Wraps ReportService in the standard BaseEngine interface.
    Handles business intelligence reports and executive dashboard queries.
    """

    engine_id = "report_engine"
    name = "Report Engine"
    version = "1.0"

    def execute(self, context: "AIContext", payload: dict) -> dict:
        from ai_assistant.services.report_service import report_service

        report_id = payload.get("report_id", "")
        filters = payload.get("filters", {})

        if not report_id:
            return {"status": "error", "message": "report_id is required"}

        method = getattr(report_service, report_id, None)
        if method is None:
            return {"status": "error", "message": f"Unknown report: {report_id}"}

        try:
            data = method(filters) if filters else method()
            return {"status": "success", "data": data}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
