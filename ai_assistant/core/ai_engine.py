"""
AI Engine — core abstraction layer for provider-agnostic AI interactions.

Defines the AIEngine class that wraps the provider system and provides a
uniform interface for the orchestration layer. Phase 3 (Predictive
Intelligence) will extend this with adaptive model selection, streaming,
and engine-level cost tracking.
"""
from __future__ import annotations

from ai_assistant.providers.base import AIProvider, AIResponse


class AIEngine:
    """
    Central AI execution engine.

    Responsibilities:
    - Accept standardized chat requests from the orchestration layer
    - Delegate to the active provider via ProviderManager
    - Return standardized AIResponse objects
    - Track engine-level metrics (Phase 3)

    Usage:
        engine = AIEngine.from_settings()
        response = engine.chat(messages, system_prompt, tools_schema)
    """

    def __init__(self, provider: AIProvider | None = None) -> None:
        self._provider = provider

    @classmethod
    def from_settings(cls) -> "AIEngine":
        """Create an AIEngine using the current AI Settings configuration."""
        from ai_assistant.core.provider_manager import ProviderManager
        return cls(provider=ProviderManager.get_active_provider())

    def _get_provider(self) -> AIProvider:
        if self._provider is not None:
            return self._provider
        from ai_assistant.core.provider_manager import ProviderManager
        return ProviderManager.get_active_provider()

    def chat(
        self,
        messages: list[dict],
        system_prompt: str = "",
        tools_schema: list[dict] | None = None,
    ) -> AIResponse:
        """
        Send a chat request to the active AI provider.

        Args:
            messages: Conversation history in provider-agnostic format.
            system_prompt: System-level instructions injected before the conversation.
            tools_schema: Available tools the AI may invoke (filtered by RBAC upstream).

        Returns:
            AIResponse with raw_text, token counts, and estimated cost.
        """
        return self._get_provider().chat(messages, system_prompt, tools_schema or [])

    def estimate_cost(self, tokens_prompt: int, tokens_completion: int) -> float:
        """Estimate USD cost for the given token pair using the active pricing table."""
        return self._get_provider().estimate_cost(tokens_prompt, tokens_completion)
