"""Backward-compatibility shim — implementation moved to ai_assistant.registries.action_registry."""
from ai_assistant.registries.action_registry import (  # noqa: F401
    ACTION_REGISTRY,
    get_action_registry,
    get_action,
)
