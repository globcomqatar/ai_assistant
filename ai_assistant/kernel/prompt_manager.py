"""
AI Prompt Manager

Centralizes prompt definitions, versioning, and variable substitution.
Isolates prompt content from business logic so prompts can evolve
independently of the engines that use them.

Phase 3 will extend this with:
- Database-backed prompt storage (overrideable per site)
- A/B testing across prompt versions
- Prompt effectiveness tracking via AI Usage Log
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PromptTemplate:
    """A versioned prompt assigned to a specific AI engine."""
    name: str
    engine: str
    version: str
    content: str
    variables: list[str] = field(default_factory=list)
    description: str = ""
    is_placeholder: bool = False

    def has_variable(self, name: str) -> bool:
        return name in self.variables


class PromptManager:
    """
    Manages prompt templates — register, version, retrieve, and render.

    Usage:
        template = prompt_manager.get("sales_agent")
        text = prompt_manager.render(template, {"user": "Ahmed", "company": "ABC"})
    """

    def __init__(self) -> None:
        # {engine_id: {version: PromptTemplate}}
        self._prompts: dict[str, dict[str, PromptTemplate]] = {}
        self._register_defaults()

    # ── Public API ────────────────────────────────────────────────────────────

    def register(self, template: PromptTemplate) -> None:
        """Register a prompt template, replacing any existing entry for the same (engine, version)."""
        self._prompts.setdefault(template.engine, {})[template.version] = template

    def get(self, engine: str, version: str = "latest") -> PromptTemplate | None:
        """
        Return a prompt template for an engine.
        Pass version="latest" (default) to get the highest version string.
        """
        engine_prompts = self._prompts.get(engine, {})
        if not engine_prompts:
            return None
        if version == "latest":
            latest = sorted(engine_prompts.keys())[-1]
            return engine_prompts[latest]
        return engine_prompts.get(version)

    def render(self, template: PromptTemplate, variables: dict[str, str]) -> str:
        """
        Render a prompt by substituting {{variable}} placeholders.
        Missing variables are left as-is; unknown variables are ignored.
        """
        content = template.content
        for key, value in variables.items():
            content = content.replace("{{" + key + "}}", str(value))
        return content

    def list_engines(self) -> list[str]:
        """Return sorted list of all registered engine IDs."""
        return sorted(self._prompts.keys())

    def list_versions(self, engine: str) -> list[str]:
        """Return sorted list of registered versions for an engine."""
        return sorted(self._prompts.get(engine, {}).keys())

    # ── Default placeholders ──────────────────────────────────────────────────

    def _register_defaults(self) -> None:
        """
        Register built-in placeholder prompts for all known engines.
        Phase 3 will override these with production prompts loaded from
        the database or site configuration.
        """
        _PLACEHOLDER = (
            "Placeholder prompt for {{engine_id}}. "
            "Implement via prompt_manager.register() or database override in Phase 3."
        )

        # (engine_id, version, description, variables)
        _entries: list[tuple[str, str, str, list[str]]] = [
            (
                "executive_report",
                "v1",
                "Executive Report — daily performance summary for CEO users.",
                ["company", "period", "language", "kpis"],
            ),
            (
                "ceo_assistant",
                "v1",
                "CEO Assistant — strategic advisor and decision support for executive users.",
                ["user", "company", "context", "date"],
            ),
            (
                "sales_agent",
                "v1",
                "Sales Agent — pipeline management, quotation follow-up, opportunity conversion.",
                ["user", "company", "context", "pipeline_value"],
            ),
            (
                "accounts_agent",
                "v1",
                "Accounts Agent — collections, invoicing, payment follow-up, financial health.",
                ["user", "company", "context", "overdue_amount"],
            ),
            (
                "workshop_agent",
                "v1",
                "Workshop Agent — job card management, service reminders, maintenance scheduling.",
                ["user", "company", "context", "open_jobs"],
            ),
            (
                "prediction_engine",
                "v1",
                "Prediction Engine — time-series forecasting and demand anomaly detection. (Phase 3)",
                ["metric", "period", "historical_data", "context"],
            ),
            (
                "risk_engine",
                "v1",
                "Risk Engine — business risk identification, scoring, and early warning. (Phase 3)",
                ["context", "thresholds", "risk_categories"],
            ),
            (
                "opportunity_engine",
                "v1",
                "Opportunity Engine — opportunity scoring, prioritisation, and lead qualification. (Phase 3)",
                ["context", "pipeline", "scoring_weights"],
            ),
            (
                "morning_brief",
                "v1",
                "Morning Brief — daily executive priorities, alerts, and recommended actions. (Phase 3)",
                ["user", "company", "date", "alerts", "priorities"],
            ),
        ]

        for engine_id, version, description, variables in _entries:
            self.register(PromptTemplate(
                name=engine_id,
                engine=engine_id,
                version=version,
                content=_PLACEHOLDER,
                variables=variables,
                description=description,
                is_placeholder=True,
            ))


# Module-level singleton
prompt_manager = PromptManager()
