"""
AI Orchestrator — unified request routing and response coordination.

The orchestrator is the single logical entry point for all AI interactions.
It receives a standardized OrchestratorRequest, routes to the correct
engine/service, and returns a standardized OrchestratorResponse.

Phase 2: _DefaultOrchestrator delegates to the existing router/executor pipeline.
Phase 3: Subclass AIOrchestrator to add predictive pre-fetching, multi-step
         reasoning chains, and confidence-gated fallback routing.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OrchestratorRequest:
    """Standardized input to the AI orchestrator."""

    messages: list[dict]
    user: str
    agent_code: str = "general"
    session_id: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class OrchestratorResponse:
    """Standardized output from the AI orchestrator."""

    actions: list[dict]
    raw_text: str = ""
    tokens_prompt: int = 0
    tokens_completion: int = 0
    cost_usd: float = 0.0
    agent_code: str = "general"
    routed_to: str | None = None
    metadata: dict = field(default_factory=dict)


class AIOrchestrator:
    """
    Abstract base orchestrator.

    All orchestrator variants must implement process(). Use
    AIOrchestrator.for_agent() to obtain the correct implementation.
    """

    def process(self, request: OrchestratorRequest) -> OrchestratorResponse:
        """Route a request through the AI pipeline and return a response."""
        raise NotImplementedError("Subclass must implement process()")

    @classmethod
    def for_agent(cls, agent_code: str = "general") -> "AIOrchestrator":
        """Factory: return the correct orchestrator for the given agent code."""
        return _DefaultOrchestrator()


class _DefaultOrchestrator(AIOrchestrator):
    """
    Phase 2 default orchestrator.

    Delegates to the existing router.route() and executor.execute_actions()
    pipeline without introducing new behavior.
    """

    def process(self, request: OrchestratorRequest) -> OrchestratorResponse:
        from ai_assistant.api.router import route
        actions = route(request.messages, request.user, request.agent_code)
        return OrchestratorResponse(
            actions=actions,
            agent_code=request.agent_code,
        )
