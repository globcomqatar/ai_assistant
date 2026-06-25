"""
AI Engines — Phase 2 implementations and Phase 3 interface placeholders.

Phase 2 (active):
    ReportEngine, RecommendationEngine, ActionEngine, ApprovalEngine, WorkflowEngine

Phase 3 (placeholder — not yet implemented):
    PredictionEngine, RiskEngine, OpportunityEngine, LearningEngine,
    MorningBriefEngine, InsightEngine

All engines inherit from BaseEngine and are registered in kernel.engine_registry.
"""
from ai_assistant.engines.base import BaseEngine

# Phase 2 engines
from ai_assistant.engines.report_engine import ReportEngine
from ai_assistant.engines.recommendation_engine import RecommendationEngine
from ai_assistant.engines.action_engine import ActionEngine
from ai_assistant.engines.approval_engine import ApprovalEngine
from ai_assistant.engines.workflow_engine import WorkflowEngine

# Phase 3 placeholder engines
from ai_assistant.engines.prediction_engine import PredictionEngine
from ai_assistant.engines.risk_engine import RiskEngine
from ai_assistant.engines.opportunity_engine import OpportunityEngine
from ai_assistant.engines.learning_engine import LearningEngine
from ai_assistant.engines.morning_brief_engine import MorningBriefEngine
from ai_assistant.engines.insight_engine import InsightEngine

__all__ = [
    "BaseEngine",
    # Phase 2
    "ReportEngine",
    "RecommendationEngine",
    "ActionEngine",
    "ApprovalEngine",
    "WorkflowEngine",
    # Phase 3
    "PredictionEngine",
    "RiskEngine",
    "OpportunityEngine",
    "LearningEngine",
    "MorningBriefEngine",
    "InsightEngine",
]
