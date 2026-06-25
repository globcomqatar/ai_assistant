# AI Assistant — Platform Architecture

Version 15.24.14 · Sprint 2.5 Wave 2

---

## Overview

AI Assistant is a multi-agent ERPNext intelligence layer built on Frappe v15. It connects ERPNext business data to AI providers (OpenAI, Anthropic, OpenRouter, Groq, Google) and exposes the results through a chat UI, dashboards, Action Center, Approval Center, and Workflow Automation.

---

## Request Flow

```
Browser
  │
  └── frappe.call("ai_assistant.api.chat.send_message")
        │
        ├── [Rate Limit] 2-second per-user cooldown (Redis)
        ├── [Governance] Agent resolution (Patch 1–4): non-SM → "general"
        ├── [Auto-routing] supervisor.py (System Manager + Auto mode only)
        │
        ├── router.py:route()
        │   ├── security/permission_manager.py → RBAC-filter TOOLS_SCHEMA
        │   ├── agent_manager.py → merge agent system prompt + KPIs
        │   ├── providers/__init__.py → dispatch to active provider
        │   └── _extract_json() → parse AI response
        │
        ├── executor.py:execute_actions()
        │   ├── Budget check (AI Settings.max_monthly_budget)
        │   ├── RBAC check per tool (security/permission_manager.py)
        │   ├── High-risk confirmation gate (security/security.py)
        │   ├── TOOL_REGISTRY[intent](**parameters)
        │   └── AI Usage Log insert (ignore_permissions=True — audit requirement)
        │
        └── chat.py:_interpret_analytics()   (for BI tools only)
              └── core/recommendation_engine.py (Phase 3 extension point)
```

---

## Package Structure

```
ai_assistant/
├── api/             Whitelisted Frappe endpoints (thin wrappers)
│   ├── chat.py      Main entry: send_message, get_agents, get_usage_summary
│   ├── router.py    Build system prompt, call provider, extract JSON
│   ├── executor.py  Budget check, tool dispatch, usage logging
│   ├── tools.py     35+ tool functions + TOOL_REGISTRY + TOOLS_SCHEMA
│   ├── bi_tools.py  Business intelligence report functions
│   ├── dashboard.py KPI number card endpoints
│   ├── supervisor.py Auto-routing classifier
│   ├── agent_manager.py Agent cache + governance patches
│   ├── action_center.py Action/Workflow whitelisted endpoints
│   ├── approval_service.py Approval logic
│   ├── workflow_engine.py Workflow execution
│   └── health.py    Health check + metrics endpoints (Wave 2)
│
├── core/            Platform engine layer (Wave 1–2)
│   ├── ai_engine.py         AIEngine — provider-agnostic chat wrapper
│   ├── orchestrator.py      AIOrchestrator — future routing entry point
│   ├── provider_manager.py  ProviderManager — provider lifecycle
│   ├── recommendation_engine.py RecommendationEngine — advisory logic
│   ├── exceptions.py        Exception hierarchy (Wave 2)
│   ├── response.py          Standardized API response helpers (Wave 2)
│   ├── performance.py       Timing utilities (Wave 2)
│   ├── metrics.py           In-process metrics collector (Wave 2)
│   └── debug.py             Debug mode utilities (Wave 2)
│
├── services/        Business-logic service layer (Wave 1–2)
│   ├── report_service.py    ReportService — BI report wrapper
│   ├── action_service.py    ActionService — Action Center wrapper
│   ├── approval_service.py  ApprovalService — Approval Center wrapper
│   ├── workflow_service.py  WorkflowService — Workflow wrapper
│   └── health_service.py    HealthService — platform health checks (Wave 2)
│
├── registries/      Registry definitions (Wave 1)
│   ├── action_registry.py   10 safe AI actions
│   ├── action_handlers.py   Action handler implementations
│   ├── workflow_registry.py 10 workflow templates
│   ├── workflow_templates.py Keyword-matching + step population
│   ├── playbook_registry.py Phase 3 placeholder
│   ├── kpi_registry.py      Phase 3 placeholder
│   └── prediction_registry.py Phase 3 placeholder
│
├── security/        Security and RBAC (Wave 1)
│   ├── security.py          Guards, roles, confirmation helpers
│   └── permission_manager.py Tool RBAC with Redis cache
│
├── providers/       AI provider abstraction
│   ├── base.py              AIProvider ABC + AIResponse dataclass
│   ├── openai_compatible.py OpenAI / OpenRouter / Groq / Google
│   └── anthropic_provider.py Claude (Anthropic)
│
├── utils/           Utility helpers
│   ├── __init__.py          is_ai_enabled, get_user_monthly_cost
│   ├── helpers.py           clamp, safe_float, truncate, format_currency (Wave 2)
│   └── logger.py            Centralized logger (Wave 2)
│
├── config/
│   ├── desktop.py           Frappe desktop module icon
│   └── settings.py          Centralized configuration constants (Wave 1)
│
└── docs/            Developer documentation (Wave 2)
```

---

## Provider System

All AI providers implement `AIProvider` (ABC) and return `AIResponse` dataclasses.

| Provider | SDK | Notes |
|---|---|---|
| OpenAI | `openai` | JSON mode with retry fallback |
| OpenRouter | `openai` + base_url | Access to 100+ models |
| Groq | `openai` + base_url | Ultra-low latency inference |
| Google Gemini | `openai` + base_url | Gemini 2.0 Flash |
| Anthropic Claude | `anthropic` | JSON via assistant pre-fill (`{`) |

Provider selection → `providers/__init__.py:get_provider()` → reads `AI Settings`.

---

## Multi-Agent Governance

Four server-side patches enforce agent restrictions:

| Patch | Rule |
|---|---|
| 1 | Non-System Manager always gets the "general" agent |
| 2 | Server-side agent switch rejected for non-System Manager |
| 3 | AI Agent configuration endpoints gated to System Manager |
| 4 | Session cannot carry an agent override for non-System Manager |

System Manager has full access to all 6 agents (supervisor, sales, marketing, accounts, operations, BI).

---

## Security Architecture

- **Tool RBAC**: every tool call goes through `security/permission_manager.py` before execution. System Manager gets all tools; others get a role-intersected subset from `AI Tool Permission`.
- **Secure default**: if no `AI Tool Permission` record exists for a tool, it is **DENIED**.
- **High-risk confirmation**: 9 tools (`create_sales_invoice`, `record_payment`, etc.) require `action.confirmed=true` from the frontend before the server executes them.
- **Audit log**: every request is written to `AI Usage Log` with `ignore_permissions=True` — this is intentional; audit logs must be written regardless of the calling user's DocType permissions.
- **No raw SQL injection risk**: all queries use parameterized `frappe.db.sql()` with `%s` placeholders or ORM methods.

---

## Phase 3 Extension Points

| File | Extension |
|---|---|
| `core/orchestrator.py` | Subclass `_DefaultOrchestrator` for predictive routing |
| `core/recommendation_engine.py` | ML confidence scoring and playbook matching |
| `registries/playbook_registry.py` | Pre-defined multi-step response chains |
| `registries/kpi_registry.py` | Business KPI definitions for anomaly detection |
| `registries/prediction_registry.py` | ML predictor metadata |
| `core/metrics.py` | Replace in-process counters with Redis / Prometheus |
| `services/health_service.py` | Add external probe endpoints for monitoring infra |
