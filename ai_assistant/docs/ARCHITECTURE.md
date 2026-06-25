# AI Assistant — Platform Architecture

Version 15.24.15 · Sprint 2.5 Wave 3 (Version 1.0 Complete)

---

## Overview

AI Assistant is a multi-agent ERPNext intelligence layer built on Frappe v15. It connects ERPNext business data to AI providers (OpenAI, Anthropic, OpenRouter, Groq, Google) and exposes results through Chat, dashboards, Action Center, Approval Center, and Workflow Automation.

The platform is organized in three layers:

| Layer | Package | Role |
|---|---|---|
| **AI Kernel** | `kernel/` | Context, prompts, providers, engine registry, feature flags |
| **AI Engines** | `engines/` | Standardized engine wrappers (Phase 2) + Phase 3 interfaces |
| **Business Services** | `api/` + `services/` | Frappe endpoints, service classes, tool dispatch |

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
              └── kernel/engine_registry → recommendation_engine (Phase 3)
```

---

## Package Structure

```
ai_assistant/
│
├── kernel/              AI Kernel — single entry point for platform infrastructure (Wave 3)
│   ├── __init__.py      Exports all kernel symbols
│   ├── context_manager.py  AIContext dataclass + AIContextManager
│   ├── prompt_manager.py   PromptManager — versioned templates per engine
│   ├── provider_manager.py KernelProviderManager — capability detection + fallback
│   ├── engine_registry.py  EngineRegistry — all engines (Phase 2 + Phase 3)
│   └── feature_flags.py    FeatureFlagManager — Phase 3 gate control
│
├── engines/             AI Engine implementations + Phase 3 interfaces (Wave 3)
│   ├── __init__.py
│   ├── base.py              BaseEngine ABC
│   ├── report_engine.py     → delegates to services/report_service.py
│   ├── recommendation_engine.py → delegates to core/recommendation_engine.py
│   ├── action_engine.py     → delegates to services/action_service.py
│   ├── approval_engine.py   → delegates to services/approval_service.py
│   ├── workflow_engine.py   → delegates to services/workflow_service.py
│   ├── prediction_engine.py Phase 3 placeholder
│   ├── risk_engine.py       Phase 3 placeholder
│   ├── opportunity_engine.py Phase 3 placeholder
│   ├── learning_engine.py   Phase 3 placeholder
│   ├── morning_brief_engine.py Phase 3 placeholder
│   └── insight_engine.py    Phase 3 placeholder
│
├── api/                 Whitelisted Frappe endpoints (thin wrappers)
│   ├── chat.py          Main entry: send_message, get_agents, get_usage_summary
│   ├── router.py        Build system prompt, call provider, extract JSON
│   ├── executor.py      Budget check, tool dispatch, usage logging
│   ├── tools.py         35+ tool functions + TOOL_REGISTRY + TOOLS_SCHEMA
│   ├── bi_tools.py      Business intelligence report functions
│   ├── dashboard.py     KPI number card endpoints
│   ├── supervisor.py    Auto-routing classifier
│   ├── agent_manager.py Agent cache + governance patches
│   ├── action_center.py Action/Workflow whitelisted endpoints
│   ├── approval_service.py Approval logic
│   ├── workflow_engine.py  Workflow execution
│   └── health.py        Health check + metrics endpoints (Wave 2)
│
├── core/                Platform engine layer (Wave 1–2)
│   ├── ai_engine.py         AIEngine — provider-agnostic chat wrapper
│   ├── orchestrator.py      AIOrchestrator — Phase 3 routing extension point
│   ├── provider_manager.py  ProviderManager — provider instantiation
│   ├── recommendation_engine.py RecommendationEngine — advisory logic
│   ├── exceptions.py        Exception hierarchy (Wave 2)
│   ├── response.py          Standardized API response helpers (Wave 2)
│   ├── performance.py       Timing utilities (Wave 2)
│   ├── metrics.py           In-process metrics collector (Wave 2)
│   └── debug.py             Debug mode utilities (Wave 2)
│
├── services/            Business-logic service layer (Wave 1–2)
│   ├── report_service.py    ReportService — BI report wrapper
│   ├── action_service.py    ActionService — Action Center wrapper
│   ├── approval_service.py  ApprovalService — Approval Center wrapper
│   ├── workflow_service.py  WorkflowService — Workflow wrapper
│   └── health_service.py    HealthService — platform health checks (Wave 2)
│
├── registries/          Registry definitions (Wave 1 + Wave 3 expansion)
│   ├── action_registry.py   10 safe AI actions
│   ├── action_handlers.py   Action handler implementations
│   ├── workflow_registry.py 10 workflow templates
│   ├── workflow_templates.py Keyword-matching + step population
│   ├── playbook_registry.py 7 named playbook placeholders (Wave 3)
│   ├── kpi_registry.py      10 named KPI placeholders (Wave 3)
│   └── prediction_registry.py Phase 3 placeholder
│
├── security/            Security and RBAC (Wave 1)
│   ├── security.py          Guards, roles, confirmation helpers
│   └── permission_manager.py Tool RBAC with Redis cache
│
├── providers/           AI provider abstraction
│   ├── base.py              AIProvider ABC + AIResponse dataclass
│   ├── openai_compatible.py OpenAI / OpenRouter / Groq / Google
│   └── anthropic_provider.py Claude (Anthropic)
│
├── utils/               Utility helpers
│   ├── __init__.py          is_ai_enabled, get_user_monthly_cost
│   ├── helpers.py           clamp, safe_float, truncate, format_currency (Wave 2)
│   └── logger.py            Centralized logger (Wave 2)
│
├── config/
│   ├── desktop.py           Frappe desktop module icon
│   └── settings.py          Centralized configuration constants (Wave 1)
│
└── docs/                Developer documentation (Wave 2–3)
```

---

## AI Kernel

The kernel is the single entry point for all AI platform infrastructure. Import from it instead of individual modules:

```python
from ai_assistant.kernel import (
    AIContext, context_manager,        # context management
    prompt_manager,                    # versioned prompts
    kernel_provider_manager,           # provider capability detection
    engine_registry,                   # all engines
    feature_flags, FeatureFlag,        # Phase 3 gates
)
```

### AIContext

Standardized context object passed to every AI Engine request:

| Field | Type | Purpose |
|---|---|---|
| `user` | str | Frappe user |
| `roles` | list[str] | User roles |
| `company` | str | Active company |
| `language` | str | UI language |
| `timezone` | str | User timezone |
| `module` | str | Current Frappe module |
| `doctype` | str | Current DocType |
| `document` | str | Current document name |
| `filters` | dict | Active filters |
| `conversation` | list | Chat message history |
| `provider` | str | Active AI provider |
| `model` | str | Active AI model |
| `permissions` | dict | User permissions snapshot |
| `feature_flags` | dict | Feature flag overrides |
| `memory_hooks` | list | Phase 3 persistent memory hooks |

### Engine Registry

All 11 engines are pre-registered at import time:

| Engine | Phase | Status |
|---|---|---|
| Report Engine | 2 | Available |
| Recommendation Engine | 2 | Available |
| Action Engine | 2 | Available |
| Approval Engine | 2 | Available |
| Workflow Engine | 2 | Available |
| Prediction Engine | 3 | Placeholder |
| Risk Engine | 3 | Placeholder |
| Opportunity Engine | 3 | Placeholder |
| Learning Engine | 3 | Placeholder |
| Morning Brief | 3 | Placeholder |
| Insight Engine | 3 | Placeholder |

### Feature Flags

All flags default to `False`. Enable in `site_config.json`:

```json
{
  "ai_flags": {
    "prediction_engine": true,
    "morning_brief": true
  }
}
```

| Flag | Enables |
|---|---|
| `prediction_engine` | Time-series forecasting + anomaly detection |
| `risk_engine` | Risk identification and scoring |
| `opportunity_engine` | Lead scoring and opportunity prioritisation |
| `morning_brief` | Daily executive priority briefing |
| `continuous_learning` | Feedback-driven model adaptation |
| `autonomous_actions` | Agent-initiated actions without user confirmation |
| `experimental_features` | Unreleased experimental features |

---

## Provider System

### Phase 2 (Active)

| Provider | Capabilities |
|---|---|
| OpenAI | Chat, Function Calling, JSON Mode, Streaming, Vision |
| OpenRouter | Chat, Function Calling, JSON Mode |
| Claude (Anthropic) | Chat, Function Calling, Streaming, Vision |
| Google Gemini | Chat, JSON Mode, Vision |
| Groq | Chat, JSON Mode, Streaming |

### Phase 3 Placeholders

| Provider | Notes |
|---|---|
| Azure OpenAI | Enterprise deployment with private endpoints |
| Ollama | Self-hosted open-source models |
| Local Model | Air-gapped on-premise inference |

Provider selection via `kernel_provider_manager.select_provider([required_capabilities])`.

---

## Multi-Agent Governance

Four server-side patches enforce agent restrictions in `api/agent_manager.py`:

| Patch | Rule |
|---|---|
| 1 | Non-System Manager always gets the "general" agent |
| 2 | Server-side agent switch rejected for non-System Manager |
| 3 | AI Agent configuration endpoints gated to System Manager |
| 4 | Session cannot carry an agent override for non-System Manager |

---

## Security Architecture

- **Tool RBAC**: every tool call goes through `security/permission_manager.py`. System Manager gets all tools; others get a role-intersected subset.
- **Secure default**: no `AI Tool Permission` record = tool DENIED.
- **High-risk confirmation**: 9 write tools require `action.confirmed=true` from the frontend.
- **Audit log**: `AI Usage Log` written with `ignore_permissions=True` — intentional, audit logs must always be written.
- **No SQL injection**: all queries use parameterized `%s` placeholders or ORM.

---

## Phase 3 Roadmap

### Architecture (ready — Wave 3)

- [x] AI Kernel package with Context, Prompt, Provider, Engine Registry, Feature Flags
- [x] `engines/` package with BaseEngine ABC and all placeholder engines
- [x] 7 named Playbook placeholders in `registries/playbook_registry.py`
- [x] 10 named KPI placeholders in `registries/kpi_registry.py`
- [x] Feature flags for all Phase 3 capabilities
- [x] Phase 3 provider configs (Azure OpenAI, Ollama, local)
- [x] Phase 3 prompt templates registered in PromptManager

### To Implement (Phase 3)

1. **Prediction Engine** — populate `engines/prediction_engine.py`; implement time-series models
2. **Risk Engine** — populate `engines/risk_engine.py`; implement risk scoring
3. **Opportunity Engine** — populate `engines/opportunity_engine.py`; implement lead scoring
4. **Morning Brief** — populate `engines/morning_brief_engine.py`; implement daily briefing
5. **Learning Engine** — implement feedback loop from AI Usage Log
6. **Insight Engine** — implement cross-module pattern recognition
7. **Playbook Runner** — implement step execution in `registries/playbook_registry.py`
8. **KPI Calculator** — implement threshold monitoring for all KPI_REGISTRY entries
9. **Prompt Database** — move prompts from code to database; override via site config
10. **Provider Extensions** — implement Azure OpenAI, Ollama, and local model support
