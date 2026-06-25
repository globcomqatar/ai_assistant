"""
AI Feature Flag Manager

Controls availability of Phase 3 features. All flags default to False (off)
in production. Enable flags via site_config.json under the "ai_flags" key.

site_config.json example:
    {
        "ai_flags": {
            "prediction_engine": true,
            "morning_brief": true
        }
    }

Flags can also be overridden at runtime for testing via feature_flags.override().
"""
from __future__ import annotations

import enum


class FeatureFlag(str, enum.Enum):
    """All known AI platform feature flags."""
    PREDICTION_ENGINE   = "prediction_engine"
    RISK_ENGINE         = "risk_engine"
    OPPORTUNITY_ENGINE  = "opportunity_engine"
    MORNING_BRIEF       = "morning_brief"
    CONTINUOUS_LEARNING = "continuous_learning"
    AUTONOMOUS_ACTIONS  = "autonomous_actions"
    EXPERIMENTAL        = "experimental_features"


# Default state for all flags (False = disabled in production)
_DEFAULTS: dict[str, bool] = {flag.value: False for flag in FeatureFlag}


class FeatureFlagManager:
    """
    Reads feature flags from frappe.conf.ai_flags and applies runtime overrides.

    Priority (highest to lowest):
        1. Runtime override set via override()
        2. frappe.conf.ai_flags from site_config.json
        3. _DEFAULTS (all False)
    """

    def __init__(self) -> None:
        self._overrides: dict[str, bool] = {}

    def is_enabled(self, flag: FeatureFlag | str) -> bool:
        """Return True if the feature flag is enabled."""
        key = flag.value if isinstance(flag, FeatureFlag) else str(flag)
        if key in self._overrides:
            return self._overrides[key]
        return self._read_from_config(key)

    def get_all(self) -> dict[str, bool]:
        """Return current state of all known flags."""
        return {flag.value: self.is_enabled(flag) for flag in FeatureFlag}

    def override(self, flag: FeatureFlag | str, value: bool) -> None:
        """Set a runtime override — intended for tests and admin utilities."""
        key = flag.value if isinstance(flag, FeatureFlag) else str(flag)
        self._overrides[key] = value

    def clear_overrides(self) -> None:
        """Remove all runtime overrides, restoring config-driven values."""
        self._overrides.clear()

    def _read_from_config(self, key: str) -> bool:
        """Read from frappe.conf.ai_flags — returns False if Frappe is unavailable."""
        try:
            import frappe
            ai_flags = getattr(frappe.conf, "ai_flags", None) or {}
            return bool(ai_flags.get(key, _DEFAULTS.get(key, False)))
        except Exception:
            return _DEFAULTS.get(key, False)


# Module-level singleton
feature_flags = FeatureFlagManager()
