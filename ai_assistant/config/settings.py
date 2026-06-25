"""
Centralized configuration for the AI Assistant platform.

All tunable constants live here — no more hardcoded values scattered across
modules. Phase 3 will load overrides from AI Settings at runtime so that
administrators can tune thresholds without code changes.
"""
from __future__ import annotations

# ── Cache ──────────────────────────────────────────────────────────────────────
AGENT_CACHE_TTL_SECONDS: int = 300       # 5 min per-agent Redis cache
RBAC_CACHE_TTL_SECONDS: int = 300        # 5 min RBAC permission map cache
RATE_LIMIT_COOLDOWN_SECONDS: int = 2     # Per-user request cooldown

# ── Budget ─────────────────────────────────────────────────────────────────────
BUDGET_WARNING_THRESHOLD: float = 0.80   # Realtime warning at 80 % of monthly limit
BUDGET_BLOCK_THRESHOLD: float = 1.00     # Block new requests at 100 %

# ── Provider timeouts ──────────────────────────────────────────────────────────
DEFAULT_TIMEOUT_SECONDS: int = 60        # Standard chat request timeout
ROUTING_TIMEOUT_SECONDS: int = 15        # Supervisor fast-routing timeout
ROUTING_CONNECT_TIMEOUT_SECONDS: int = 5

# ── Approval framework ─────────────────────────────────────────────────────────
SAFE_APPROVAL_ACTIVE: bool = True
MANAGER_APPROVAL_ACTIVE: bool = False
FINANCE_APPROVAL_ACTIVE: bool = False
MULTI_LEVEL_APPROVAL_ACTIVE: bool = False

# ── Analytics & recommendations ───────────────────────────────────────────────
CONFIDENCE_THRESHOLD: float = 0.65       # Minimum confidence to surface a recommendation
BUSINESS_IMPACT_THRESHOLD: float = 1_000.0  # Minimum QAR impact to flag a risk
ANALYTICS_INTERPRETATION_ENABLED: bool = True

# ── Data retention ─────────────────────────────────────────────────────────────
USAGE_LOG_RETENTION_DAYS: int = 90       # Enforced by Frappe log-clearing job

# ── Supervisor routing ─────────────────────────────────────────────────────────
SUPERVISOR_MIN_AGENTS_FOR_ROUTING: int = 2

# ── Security: high-risk write tools ───────────────────────────────────────────
HIGH_RISK_WRITE_TOOLS: frozenset[str] = frozenset({
    "create_sales_invoice",
    "record_payment",
    "create_journal_entry",
    "generate_payment_from_invoice",
    "create_purchase_invoice",
    "create_stock_entry",
    "create_employee",
    "create_leave_application",
    "create_expense_claim",
})

# ── Performance monitoring ─────────────────────────────────────────────────────
SLOW_QUERY_THRESHOLD_MS: int = 500           # Log a warning for any timed block exceeding this

# ── Security: management roles ─────────────────────────────────────────────────
MANAGEMENT_ROLES: frozenset[str] = frozenset({
    "System Manager",
    "Accounts Manager",
    "Sales Manager",
    "Stock Manager",
    "CEO",
    "Management",
    "Management User",
})
