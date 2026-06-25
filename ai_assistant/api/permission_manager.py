"""Backward-compatibility shim — implementation moved to ai_assistant.security.permission_manager."""
from ai_assistant.security.permission_manager import (  # noqa: F401
    invalidate_cache,
    get_user_roles,
    get_allowed_tools,
    validate_tool_permission,
    get_permitted_tools_schema,
)
