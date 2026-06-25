"""
AI Kernel — the single entry point for all AI platform infrastructure.

The Kernel provides:
  - AIContext:            standardized context for every AI Engine request
  - PromptManager:        versioned prompt templates, isolated from business logic
  - KernelProviderManager: provider capability detection and selection
  - EngineRegistry:       centralized registry of active and future engines
  - FeatureFlagManager:   Phase 3 feature gate management

Import from here instead of individual modules:

    from ai_assistant.kernel import (
        AIContext, context_manager,
        prompt_manager,
        engine_registry,
        feature_flags, FeatureFlag,
    )
"""
from ai_assistant.kernel.context_manager import (
    AIContext,
    AIContextManager,
    context_manager,
)
from ai_assistant.kernel.prompt_manager import (
    PromptManager,
    PromptTemplate,
    prompt_manager,
)
from ai_assistant.kernel.provider_manager import (
    KernelProviderManager,
    ProviderCapability,
    ProviderConfig,
    PROVIDER_CONFIGS,
    kernel_provider_manager,
)
from ai_assistant.kernel.engine_registry import (
    EngineRegistry,
    EngineRegistration,
    engine_registry,
)
from ai_assistant.kernel.feature_flags import (
    FeatureFlagManager,
    FeatureFlag,
    feature_flags,
)

__all__ = [
    # Context
    "AIContext",
    "AIContextManager",
    "context_manager",
    # Prompts
    "PromptManager",
    "PromptTemplate",
    "prompt_manager",
    # Providers
    "KernelProviderManager",
    "ProviderCapability",
    "ProviderConfig",
    "PROVIDER_CONFIGS",
    "kernel_provider_manager",
    # Engine registry
    "EngineRegistry",
    "EngineRegistration",
    "engine_registry",
    # Feature flags
    "FeatureFlagManager",
    "FeatureFlag",
    "feature_flags",
]
