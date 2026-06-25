"""
Exception hierarchy for the AI Assistant platform.

All public exceptions inherit from AIAssistantError, which carries:
- A developer-facing ``message`` (logged internally, never shown to users)
- A user-facing ``user_message`` (safe for display in the UI)
- A ``recovery`` hint (actionable next step shown to the user)
- An ``error_code`` slug for client-side branching

Usage:
    raise ProviderError(
        "OpenAI returned 429",
        user_message="AI service is temporarily unavailable.",
        recovery="Please try again in a moment.",
    )
"""
from __future__ import annotations


class AIAssistantError(Exception):
    """Base exception for all AI Assistant platform errors."""

    http_status_code: int = 500
    error_code: str = "AI_ASSISTANT_ERROR"

    def __init__(
        self,
        message: str = "An unexpected error occurred.",
        *,
        user_message: str | None = None,
        recovery: str | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.user_message: str = user_message or "An error occurred. Please try again."
        self.recovery: str = recovery or "Contact your system administrator if the issue persists."
        if code:
            self.error_code = code

    def to_dict(self) -> dict:
        """Return a user-safe dict — never includes Python traceback."""
        return {
            "error_code": self.error_code,
            "message": self.user_message,
            "recovery": self.recovery,
        }


class ProviderError(AIAssistantError):
    """Raised when the AI provider returns an error or is unreachable."""
    http_status_code = 502
    error_code = "AI_PROVIDER_ERROR"

    def __init__(self, message: str = "AI provider request failed.", **kwargs):
        kwargs.setdefault("user_message", "The AI service is temporarily unavailable.")
        kwargs.setdefault("recovery", "Please try again in a moment.")
        super().__init__(message, **kwargs)


class BudgetExceededError(AIAssistantError):
    """Raised when the user's monthly AI budget is exhausted."""
    http_status_code = 429
    error_code = "BUDGET_EXCEEDED"

    def __init__(self, message: str = "Monthly AI budget exceeded.", **kwargs):
        kwargs.setdefault("user_message", "Your monthly AI usage budget has been reached.")
        kwargs.setdefault("recovery", "Contact your administrator to increase the budget limit.")
        super().__init__(message, **kwargs)


class PermissionDeniedError(AIAssistantError):
    """Raised when a user lacks permission for a tool or agent."""
    http_status_code = 403
    error_code = "PERMISSION_DENIED"

    def __init__(self, message: str = "Permission denied.", **kwargs):
        kwargs.setdefault("user_message", "You do not have permission to perform this action.")
        kwargs.setdefault("recovery", "Contact your administrator to request access.")
        super().__init__(message, **kwargs)


class ValidationError(AIAssistantError):
    """Raised when request parameters fail validation."""
    http_status_code = 400
    error_code = "VALIDATION_ERROR"

    def __init__(self, message: str = "Invalid input.", **kwargs):
        kwargs.setdefault("user_message", message)
        kwargs.setdefault("recovery", "Check the input and try again.")
        super().__init__(message, **kwargs)


class ConfigurationError(AIAssistantError):
    """Raised when AI Settings are missing or invalid."""
    http_status_code = 500
    error_code = "CONFIGURATION_ERROR"

    def __init__(self, message: str = "AI Assistant is not properly configured.", **kwargs):
        kwargs.setdefault("user_message", "AI Assistant is not configured. Contact your administrator.")
        kwargs.setdefault("recovery", "Open AI Settings and verify the provider and API key are set.")
        super().__init__(message, **kwargs)


class AgentNotFoundError(AIAssistantError):
    """Raised when a requested AI Agent does not exist or is disabled."""
    http_status_code = 404
    error_code = "AGENT_NOT_FOUND"

    def __init__(self, agent_code: str = "", **kwargs):
        msg = f"AI Agent '{agent_code}' not found or disabled." if agent_code else "AI Agent not found."
        kwargs.setdefault("user_message", "The requested AI agent is not available.")
        kwargs.setdefault("recovery", "Use the default agent or contact your administrator.")
        super().__init__(msg, **kwargs)


class RateLimitError(AIAssistantError):
    """Raised when a user sends requests too quickly."""
    http_status_code = 429
    error_code = "RATE_LIMIT"

    def __init__(self, message: str = "Request rate limit exceeded.", **kwargs):
        kwargs.setdefault("user_message", "Please wait a moment before sending another message.")
        kwargs.setdefault("recovery", "Wait a few seconds and try again.")
        super().__init__(message, **kwargs)


class ToolExecutionError(AIAssistantError):
    """Raised when a tool function fails during execution."""
    http_status_code = 500
    error_code = "TOOL_EXECUTION_ERROR"

    def __init__(self, tool: str = "", message: str = "Tool execution failed.", **kwargs):
        full_msg = f"Tool '{tool}' failed: {message}" if tool else message
        kwargs.setdefault("user_message", "The requested action could not be completed.")
        kwargs.setdefault("recovery", "Try again or contact your administrator if the issue continues.")
        super().__init__(full_msg, **kwargs)


class WorkflowError(AIAssistantError):
    """Raised when workflow execution encounters an unrecoverable error."""
    http_status_code = 500
    error_code = "WORKFLOW_ERROR"

    def __init__(self, message: str = "Workflow execution failed.", **kwargs):
        kwargs.setdefault("user_message", "The workflow could not be completed.")
        kwargs.setdefault("recovery", "Check the failed step and retry or skip it.")
        super().__init__(message, **kwargs)
