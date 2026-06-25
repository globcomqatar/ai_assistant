"""Backward-compatibility shim — implementation moved to ai_assistant.registries.workflow_registry."""
from ai_assistant.registries.workflow_registry import (  # noqa: F401
    WORKFLOW_REGISTRY,
    get_workflow_registry,
    get_workflow,
)
