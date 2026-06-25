"""Backward-compatibility shim — implementation moved to ai_assistant.security.security."""
from ai_assistant.security.security import (  # noqa: F401
    MANAGEMENT_ROLES,
    HIGH_RISK_WRITE_TOOLS,
    user_roles,
    is_system_manager,
    has_any_role,
    require_any_role,
    require_management_access,
    require_doctype_permission,
    insert_with_permission,
    save_with_permission,
    is_confirmed_action,
    sanitize_parameters,
    confirmation_required_response,
)
