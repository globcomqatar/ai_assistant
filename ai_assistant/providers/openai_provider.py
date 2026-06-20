# Backward-compatibility shim — use providers/__init__.py going forward.
from ai_assistant.providers import get_provider  # noqa: F401
