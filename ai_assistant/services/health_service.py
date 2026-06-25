"""
Health Check Service — platform status and diagnostics.

Returns a structured status dict covering all critical platform components.
Designed for future integration with monitoring infrastructure (Prometheus,
PagerDuty, Frappe Cloud health probes) in Phase 3.

Usage:
    from ai_assistant.services.health_service import health_service
    status = health_service.check_all()

Whitelisted endpoint: ai_assistant.api.health.get_health_status
"""
from __future__ import annotations

import frappe
from frappe import _


class HealthService:
    """
    Platform health check service.

    Each check_*() method returns a small status dict:
        {"status": "ok" | "warning" | "error" | "unknown", ...extra}

    check_all() aggregates all checks and returns "ok" only when every
    individual check is "ok"; otherwise "degraded".
    """

    def check_all(self, include_provider: bool = False) -> dict:
        """
        Run all health checks and return an aggregated status dict.

        ``include_provider`` is False by default because testing AI
        connectivity makes a real outbound HTTP call — enable only for
        dedicated health probe requests.
        """
        checks: dict[str, dict] = {
            "database":   self.check_database(),
            "ai_settings": self.check_ai_settings(),
            "registries": self.check_registries(),
            "scheduler":  self.check_scheduler(),
            "queue":      self.check_queue(),
        }
        if include_provider:
            checks["ai_provider"] = self.check_ai_provider()

        all_ok = all(c.get("status") == "ok" for c in checks.values())
        return {
            "status":  "ok" if all_ok else "degraded",
            "version": self._get_version(),
            "checks":  checks,
        }

    def check_database(self) -> dict:
        """Verify a basic database query succeeds."""
        try:
            frappe.db.sql("SELECT 1")
            return {"status": "ok"}
        except Exception as exc:
            return {"status": "error", "error": str(exc)[:200]}

    def check_ai_settings(self) -> dict:
        """Verify AI Settings exist and AI Assistant is enabled."""
        try:
            settings = frappe.get_single("AI Settings")
            if not settings.enabled:
                return {"status": "warning", "message": "AI Assistant is disabled in settings."}
            provider = getattr(settings, "ai_provider", None) or "not configured"
            return {"status": "ok", "provider": provider}
        except Exception as exc:
            return {"status": "error", "error": str(exc)[:200]}

    def check_ai_provider(self) -> dict:
        """
        Test live connectivity to the active AI provider.

        Makes a real HTTP call — use sparingly (not on every page load).
        """
        try:
            from ai_assistant.core.provider_manager import ProviderManager
            result = ProviderManager.test_connectivity()
            if result.get("ok"):
                return {"status": "ok", "provider": result.get("provider")}
            return {"status": "error", "error": (result.get("error") or "unknown")[:200]}
        except Exception as exc:
            return {"status": "error", "error": str(exc)[:200]}

    def check_scheduler(self) -> dict:
        """Verify the Frappe scheduler is active."""
        try:
            from frappe.utils.scheduler import is_scheduler_disabled
            if is_scheduler_disabled():
                return {"status": "warning", "message": "Frappe scheduler is disabled."}
            return {"status": "ok"}
        except ImportError:
            # Frappe internal API may vary — treat unknown as non-critical
            return {"status": "unknown", "note": "Could not check scheduler state."}
        except Exception as exc:
            return {"status": "unknown", "note": str(exc)[:100]}

    def check_queue(self) -> dict:
        """Verify the background job queue module is importable."""
        try:
            import frappe.utils.background_jobs  # noqa: F401
            return {"status": "ok"}
        except Exception as exc:
            return {"status": "unknown", "note": str(exc)[:100]}

    def check_registries(self) -> dict:
        """Verify action and workflow registries load without errors."""
        try:
            from ai_assistant.registries.action_registry import ACTION_REGISTRY
            from ai_assistant.registries.workflow_registry import WORKFLOW_REGISTRY
            return {
                "status": "ok",
                "action_count": len(ACTION_REGISTRY),
                "workflow_count": len(WORKFLOW_REGISTRY),
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)[:200]}

    @staticmethod
    def _get_version() -> str:
        try:
            import ai_assistant
            return ai_assistant.__version__
        except Exception:
            return "unknown"


health_service = HealthService()
