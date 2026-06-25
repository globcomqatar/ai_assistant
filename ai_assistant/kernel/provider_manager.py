"""
AI Kernel Provider Manager

High-level provider management with capability detection, provider selection,
and fallback support. This module knows about ALL supported providers (Phase 2
active + Phase 3 future) without containing any provider-specific SDK code.

Provider-specific implementation lives in ai_assistant/providers/.
Actual provider instantiation is delegated to ai_assistant/core/provider_manager.py.

Phase 2 providers (active): openai, openrouter, anthropic, google, groq
Phase 3 providers (placeholder): azure_openai, ollama, local
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field


class ProviderCapability(str, enum.Enum):
    """Capabilities a provider may expose to AI engines."""
    CHAT              = "chat"
    FUNCTION_CALLING  = "function_calling"
    JSON_MODE         = "json_mode"
    STREAMING         = "streaming"
    VISION            = "vision"
    EMBEDDINGS        = "embeddings"
    FINE_TUNING       = "fine_tuning"      # Phase 3
    BATCH_INFERENCE   = "batch_inference"  # Phase 3


@dataclass
class ProviderConfig:
    """Metadata for a single AI provider."""
    provider_id: str
    display_name: str
    capabilities: list[ProviderCapability]
    is_available: bool = True       # True = implemented in Phase 2
    is_placeholder: bool = False    # True = Phase 3 provider
    requires_base_url: bool = False
    fallback_priority: int = 99     # lower = preferred when selecting a fallback


# ── All known providers ────────────────────────────────────────────────────────

PROVIDER_CONFIGS: dict[str, ProviderConfig] = {
    "openai": ProviderConfig(
        provider_id="openai",
        display_name="OpenAI",
        capabilities=[
            ProviderCapability.CHAT,
            ProviderCapability.FUNCTION_CALLING,
            ProviderCapability.JSON_MODE,
            ProviderCapability.STREAMING,
            ProviderCapability.VISION,
        ],
        fallback_priority=1,
    ),
    "openrouter": ProviderConfig(
        provider_id="openrouter",
        display_name="OpenRouter",
        capabilities=[
            ProviderCapability.CHAT,
            ProviderCapability.FUNCTION_CALLING,
            ProviderCapability.JSON_MODE,
        ],
        fallback_priority=2,
    ),
    "anthropic": ProviderConfig(
        provider_id="anthropic",
        display_name="Claude (Anthropic)",
        capabilities=[
            ProviderCapability.CHAT,
            ProviderCapability.FUNCTION_CALLING,
            ProviderCapability.STREAMING,
            ProviderCapability.VISION,
        ],
        fallback_priority=3,
    ),
    "google": ProviderConfig(
        provider_id="google",
        display_name="Google Gemini",
        capabilities=[
            ProviderCapability.CHAT,
            ProviderCapability.JSON_MODE,
            ProviderCapability.VISION,
        ],
        fallback_priority=4,
    ),
    "groq": ProviderConfig(
        provider_id="groq",
        display_name="Groq",
        capabilities=[
            ProviderCapability.CHAT,
            ProviderCapability.JSON_MODE,
            ProviderCapability.STREAMING,
        ],
        fallback_priority=5,
    ),
    # ── Phase 3 placeholders ─────────────────────────────────────────────────
    "azure_openai": ProviderConfig(
        provider_id="azure_openai",
        display_name="Azure OpenAI",
        capabilities=[
            ProviderCapability.CHAT,
            ProviderCapability.FUNCTION_CALLING,
            ProviderCapability.JSON_MODE,
            ProviderCapability.STREAMING,
        ],
        is_available=False,
        is_placeholder=True,
        requires_base_url=True,
        fallback_priority=10,
    ),
    "ollama": ProviderConfig(
        provider_id="ollama",
        display_name="Ollama (Local)",
        capabilities=[
            ProviderCapability.CHAT,
            ProviderCapability.STREAMING,
        ],
        is_available=False,
        is_placeholder=True,
        requires_base_url=True,
        fallback_priority=20,
    ),
    "local": ProviderConfig(
        provider_id="local",
        display_name="Local Model",
        capabilities=[
            ProviderCapability.CHAT,
        ],
        is_available=False,
        is_placeholder=True,
        requires_base_url=True,
        fallback_priority=30,
    ),
}


class KernelProviderManager:
    """
    High-level provider management for the AI Kernel.

    Does NOT instantiate providers — delegates to core.provider_manager for that.
    Responsible for:
      - Capability advertisement
      - Provider selection based on required capabilities
      - Fallback provider identification
    """

    def get_active_provider(self):
        """Return the currently active AI provider instance (reads AI Settings)."""
        from ai_assistant.core.provider_manager import ProviderManager
        return ProviderManager.get_active_provider()

    def get_capabilities(self, provider_id: str) -> list[ProviderCapability]:
        """Return the capability list for a provider."""
        config = PROVIDER_CONFIGS.get(provider_id)
        return list(config.capabilities) if config else []

    def select_provider(self, required: list[ProviderCapability]) -> str | None:
        """
        Return the provider_id of the best available provider that supports
        all required capabilities, ranked by fallback_priority.
        Returns None if no match is found.
        """
        candidates = sorted(
            [c for c in PROVIDER_CONFIGS.values() if c.is_available and not c.is_placeholder],
            key=lambda c: c.fallback_priority,
        )
        for config in candidates:
            if all(cap in config.capabilities for cap in required):
                return config.provider_id
        return None

    def get_fallback_provider_id(self, exclude: str | None = None) -> str | None:
        """
        Return the provider_id of the best available fallback provider,
        optionally excluding a specific provider (e.g. the one that just failed).
        """
        candidates = sorted(
            [c for c in PROVIDER_CONFIGS.values() if c.is_available and not c.is_placeholder],
            key=lambda c: c.fallback_priority,
        )
        for config in candidates:
            if config.provider_id != exclude:
                return config.provider_id
        return None

    def is_available(self, provider_id: str) -> bool:
        config = PROVIDER_CONFIGS.get(provider_id)
        return config is not None and config.is_available and not config.is_placeholder

    def list_available(self) -> list[ProviderConfig]:
        """Return Phase 2 providers (available, not placeholders)."""
        return [c for c in PROVIDER_CONFIGS.values() if c.is_available and not c.is_placeholder]

    def list_placeholders(self) -> list[ProviderConfig]:
        """Return Phase 3 placeholder providers."""
        return [c for c in PROVIDER_CONFIGS.values() if c.is_placeholder]

    def list_all(self) -> list[ProviderConfig]:
        return list(PROVIDER_CONFIGS.values())


# Module-level singleton
kernel_provider_manager = KernelProviderManager()
