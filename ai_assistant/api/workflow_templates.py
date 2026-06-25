"""Backward-compatibility shim — implementation moved to ai_assistant.registries.workflow_templates."""
from ai_assistant.registries.workflow_templates import (  # noqa: F401
    KEYWORD_WORKFLOWS,
    infer_workflow_id,
    workflow_payload,
    populate_steps,
)
