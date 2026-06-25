"""
Provider Manager — centralized AI provider lifecycle management.

Wraps the existing provider factory (providers/__init__.py) and defines
the future interface for provider health monitoring, cost-based routing,
and automatic failover (Phase 3).
"""
from __future__ import annotations

from ai_assistant.providers.base import AIProvider


class ProviderManager:
    """
    Manages AI provider selection and instantiation.

    Phase 2: thin wrapper around providers/__init__.get_provider().
    Phase 3 extensions:
    - Provider health checks and automatic failover
    - Cost-based provider selection
    - A/B routing between providers
    """

    @staticmethod
    def get_active_provider() -> AIProvider:
        """Return the provider instance configured in AI Settings."""
        from ai_assistant.providers import get_provider
        return get_provider()

    @staticmethod
    def get_active_model() -> str:
        """Return the model name currently selected in AI Settings."""
        from ai_assistant.ai_assistant.doctype.ai_settings.ai_settings import AISettings
        doc = AISettings.get_cached()
        return doc.get_active_model() if doc else ""

    @staticmethod
    def test_connectivity(timeout: int = 10) -> dict:
        """
        Test connectivity to the active provider.

        Returns a status dict with 'ok', 'provider', and optionally 'error'.
        """
        try:
            provider = ProviderManager.get_active_provider()
            response = provider.chat(
                messages=[{"role": "user", "content": "ping"}],
                system_prompt='Reply with exactly: {"intent":"reply","message":"pong"}',
                tools_schema=[],
            )
            return {
                "ok": True,
                "provider": type(provider).__name__,
                "preview": (response.raw_text or "")[:80],
            }
        except Exception as exc:
            return {"ok": False, "provider": None, "error": str(exc)}
