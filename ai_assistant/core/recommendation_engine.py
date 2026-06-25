"""
Recommendation Engine — AI-powered analysis and advisory generation.

Extracts and formalizes the advisory generation logic from chat.py into
a dedicated engine class. Phase 3 will extend this with ML-based
confidence scoring, playbook matching, and proactive predictive signals.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RecommendationResult:
    """Structured output from the recommendation engine."""

    executive_summary: str = ""
    findings: list[dict] = field(default_factory=list)
    root_causes: list[str] = field(default_factory=list)
    risks: list[dict] = field(default_factory=list)
    opportunities: list[dict] = field(default_factory=list)
    recommendations: list[dict] = field(default_factory=list)
    required_actions: list[dict] = field(default_factory=list)
    expected_business_impact: str = ""
    confidence_score: float = 0.0
    metadata: dict = field(default_factory=dict)


class RecommendationEngine:
    """
    Generates structured recommendations from business metrics.

    Phase 2: delegates to the deterministic advisory rules in chat.py and
             the LLM interpretation pipeline (_interpret_analytics).
    Phase 3: ML confidence scoring, playbook matching, predictive signals,
             and historical pattern recognition.
    """

    def analyze(self, metrics: dict, context: dict | None = None) -> RecommendationResult:
        """
        Analyze business metrics and return structured recommendations.

        Delegates to the existing deterministic advisory pipeline for Phase 2.
        """
        from ai_assistant.api.chat import _deterministic_advisory
        tool_result = {"metrics": metrics, **(context or {})}
        base = _deterministic_advisory(tool_result)
        return RecommendationResult(
            risks=base.get("risks", []),
            required_actions=base.get("required_actions", []),
        )

    def score_confidence(self, result: RecommendationResult) -> float:
        """
        Compute a 0-1 confidence score for a recommendation set.

        Phase 2: simple heuristic based on finding count.
        Phase 3: model-based calibration against historical accuracy.
        """
        if not result.findings and not result.risks:
            return 0.0
        raw = len(result.findings) * 0.10 + len(result.risks) * 0.15
        return round(min(1.0, raw), 4)

    def merge(self, deterministic: dict, ai_generated: dict) -> RecommendationResult:
        """
        Merge deterministic rule-based output with AI-generated advisory.

        Delegates to chat._merge_advisory for Phase 2.
        """
        from ai_assistant.api.chat import _merge_advisory
        merged = _merge_advisory(deterministic, ai_generated)
        return RecommendationResult(
            executive_summary=merged.get("executive_summary", ""),
            findings=merged.get("findings", []),
            root_causes=merged.get("root_causes", []),
            risks=merged.get("risks", []),
            opportunities=merged.get("opportunities", []),
            recommendations=merged.get("recommendations", []),
            required_actions=merged.get("required_actions", []),
            expected_business_impact=merged.get("expected_business_impact", ""),
        )
