"""
Base class for all AI Engines.

Every engine in the platform — Phase 2 (active) and Phase 3 (placeholder) —
inherits from BaseEngine. This ensures a consistent interface across all engines
and allows the EngineRegistry to treat them uniformly.

Phase 3 placeholder engines override is_placeholder = True and raise
NotImplementedError in execute() until they are implemented.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from ai_assistant.kernel.context_manager import AIContext


class BaseEngine(ABC):
    """Abstract base class for all AI engines."""

    engine_id: ClassVar[str] = ""
    name: ClassVar[str] = ""
    version: ClassVar[str] = "1.0"
    is_placeholder: ClassVar[bool] = False

    @abstractmethod
    def execute(self, context: "AIContext", payload: dict) -> dict:
        """
        Process a request within the given AI context.

        Args:
            context: The standardized AIContext for this request.
            payload: Engine-specific input parameters.

        Returns:
            dict with at minimum {"status": "success"|"error", "data": ...}
        """
        ...

    def is_available(self) -> bool:
        """Return True if this engine is fully implemented and ready to use."""
        return not self.is_placeholder

    def describe(self) -> dict:
        """Return a metadata summary suitable for admin UIs and health checks."""
        return {
            "engine_id": self.engine_id,
            "name": self.name,
            "version": self.version,
            "is_placeholder": self.is_placeholder,
            "available": self.is_available(),
        }
