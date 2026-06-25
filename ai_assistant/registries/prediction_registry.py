"""
Prediction Registry — Phase 3 placeholder.

Registry for ML prediction model metadata. Phase 3 will register trained
models (sales forecast, churn probability, inventory demand) here and
route requests through the AIOrchestrator to the correct predictor.

Structure of a predictor entry (future):
    {
        "prediction_id": "sales_forecast_30d",
        "name": "30-Day Sales Forecast",
        "model_type": "time_series",
        "input_features": ["historical_revenue", "seasonality"],
        "output": "predicted_revenue_qar",
        "confidence_metric": "mape",
    }
"""
from __future__ import annotations

PREDICTION_REGISTRY: list[dict] = []


def get_prediction_registry() -> list[dict]:
    """Return all registered predictors."""
    return list(PREDICTION_REGISTRY)


def get_predictor(prediction_id: str) -> dict | None:
    """Return a single predictor entry by ID, or None if not found."""
    for p in PREDICTION_REGISTRY:
        if p.get("prediction_id") == prediction_id:
            return dict(p)
    return None
