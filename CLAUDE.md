# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands must be run from `/workspace/development/frappe-bench/` unless otherwise noted.

```bash
# After any Python change
bench --site mysite.localhost migrate

# After any JS/CSS change
bench build --app ai_assistant

# Both together (common after adding a DocType field or changing hooks)
bench --site mysite.localhost migrate && bench build --app ai_assistant

# Restart the dev server
bench restart

# Test a whitelisted API method directly
bench --site mysite.localhost execute "frappe.call" --kwargs '{"cmd": "ai_assistant.api.chat.test_connection"}'

# Run SQL queries (useful for inspecting AI Usage Log, checking __Auth table)
bench --site mysite.localhost execute "frappe.db.sql" --args '["SELECT ... FROM `tabXXX`"]'

# Verify app version
python -c "import ai_assistant; print(ai_assistant.__version__)"
```

**Always bump `ai_assistant/__init__.py` version after any change** — increment `__version__` (e.g. `0.1.4` → `0.1.5`).

## Architecture

### Request Flow

```
Browser → frappe.call("ai_assistant.api.chat.send_message")
  → chat.py:send_message()
    → agent_manager.py             # resolve/validate active AI Agent persona (RBAC-gated)
    → supervisor.py                # optional: Auto mode classifies message → best agent (System Manager only)
    → router.py:route()            # builds system prompt (RBAC tools ∩ agent tools + agent prompt), calls AI provider
      → providers/__init__.py:get_provider()   # reads AI Settings, returns provider
        → OpenAICompatibleProvider / AnthropicProvider
    → executor.py:execute_actions()   # budget check → permission_manager RBAC check per intent → dispatch → log
      → api/tools.py + api/bi_tools.py:TOOL_REGISTRY[intent](**params)   # actual ERPNext ORM calls
    → chat.py:_interpret_analytics()  # for BI tools with `metrics`, a 2nd LLM call adds findings/risks/recommendations
    → AI Usage Log (written via frappe.new_doc)
```

### Multi-Agent Framework (`api/agent_manager.py`, `api/supervisor.py`)

There isn't just one assistant persona — the `AI Agent` DocType defines multiple specialist personas (fixtures: `general`, `sales_manager`, `accounts_manager`, `workshop_advisor`, `ceo_assistant`, `supervisor`, `sales`, `marketing`, `accounts`, `operations`, `bi`), each with its own system prompt, icon/color, optional model/temperature override, a scoped tool subset (`AI Agent Tool` child table), KPIs it tracks (`AI Agent KPI`), and allowed ERPNext roles (`AI Agent Role`).

**Governance is strict and entirely server-side** — never trust `current_agent` from the client:
- `resolve_active_agent()` — non-System Manager users are always forced to the default/`general` agent, regardless of what the client requested.
- `validate_agent_switch()` — throws `frappe.PermissionError` if a non-System Manager tries to activate any agent other than `general`.
- `get_session_agent()` — strips any session-level override for non-System Manager users.
- `check_system_manager_access()` — gates AI Agent configuration endpoints entirely.

These four checks run in sequence on every `send_message` call (see `chat.py:send_message`), so agent switching is only ever possible for System Manager.

**Auto-routing** (`supervisor.py:route_to_agent`) — when `AI Settings.agent_routing_mode == "Auto"` (System Manager only), an extra lightweight LLM call classifies the user's message against the available agent catalog and picks the best specialist. Uses a tight 5–15s timeout and falls back silently (via `frappe.log_error`, never raises) to the default agent on any failure or invalid response.

`agent_manager.py:build_agent_system_prompt()` prepends the agent's system prompt + KPI list on top of the base ERP-assistant prompt; `filter_tools_for_agent()` intersects the agent's tool list with whatever RBAC already allowed.

### RBAC / Permission System (`api/permission_manager.py`)

A second, independent layer from agent scoping — governs which ERPNext roles may call which tools, regardless of agent:

- `AI Tool Permission` DocType maps a tool name → allowed roles (`AI Tool Permission Role` child table).
- **Secure by default**: a tool with no `AI Tool Permission` record is denied to everyone except System Manager.
- System Manager always gets every enabled tool.
- `get_permitted_tools_schema(user)` pre-filters `TOOLS_SCHEMA` before it ever reaches the AI system prompt — the model never sees, and so never proposes, tools the user isn't allowed to call.
- `executor.py` calls `validate_tool_permission(user, intent)` again immediately before dispatch — belt-and-suspenders in case a client bypasses the filtered prompt. Denials are logged to `AI Usage Log` with `status="Denied"`.
- Permission map is cached site-wide for 5 minutes (`_load_permission_map`); call `permission_manager.invalidate_cache()` after editing `AI Tool Permission` records outside the UI (the DocType's own hooks already do this on save/delete).

### Provider System (`providers/`)

- `base.py` — `AIProvider` ABC + `AIResponse` dataclass
- `openai_compatible.py` — handles OpenAI, OpenRouter, Groq, Google Gemini all via the `openai` SDK with `base_url` override
- `anthropic_provider.py` — Claude-specific: uses `anthropic` SDK, enforces JSON via assistant pre-fill (`{` prepended to response)
- `__init__.py:get_provider()` — reads `AI Settings` Single DocType, calls `get_active_api_key()` and `get_active_model()`, dispatches to the right class

### Tool System (`api/tools.py`)

Adding a new tool requires three steps in `tools.py`:
1. Define the Python function (must return `dict` with at minimum `{"status", "message"}`)
2. Register it in `TOOL_REGISTRY: dict[str, callable]`
3. Document it in `TOOLS_SCHEMA: list[dict]` — this is injected verbatim into the AI system prompt

The AI receives `TOOLS_SCHEMA` as its list of callable intents. It returns JSON like `{"intent": "tool_name", "parameters": {...}}`. `executor.py` dispatches to `TOOL_REGISTRY[intent]`.

### AI Settings DocType (Single)

`ai_assistant/doctype/ai_settings/` is a **Single DocType**. Critical Frappe v15 constraint:

> **Password fields in Single DocTypes are NOT loaded into the document object.** They live in `__Auth`, not `tabSingles`. `frappe.get_single()` leaves Password fields empty at runtime.

**Never call `doc.get_password(fieldname)` or `doc.api_key` on a Single DocType** — it silently returns empty. The correct approach (already implemented in `ai_settings.py`):

```python
from frappe.utils.password import get_decrypted_password
key = get_decrypted_password("AI Settings", "AI Settings", field_name, raise_exception=False) or ""
```

### JSON Extraction (`router.py:_extract_json`)

Open-source models (LLaMA, Mistral via OpenRouter/Groq) often wrap JSON in markdown fences. `_extract_json()` strips ` ```json ``` ` fences, then bracket-depth scans to extract the first valid `{…}` or `[…]` block. All providers try `response_format={"type": "json_object"}` first, with automatic retry without it if the provider rejects it.

### Frappe-Specific Patterns

- `frappe.log_error(title="Short Title", message=str(exc))` — title is first arg, max 140 chars. Use keyword args.
- `doc.flags.ignore_permissions = True` before `doc.insert()` in all tool functions.
- `frappe.db.commit()` after every `insert()` in tool functions.
- `@frappe.whitelist()` is required on every function callable from the browser.
- `frappe.throw()` raises `frappe.ValidationError` — caught in `executor.py` and returned as `"status": "validation_error"`.

### Front-End (`ai_assistant/page/ai_chat/`)

This is a **Frappe Desk Page** (not a `www` page). Accessible via `frappe.set_route("ai-chat")`. The floating 🤖 button is injected on every desk page via `hooks.py → app_include_js`.

`ai_chat.js:AIChatPage._build_result_card()` has per-intent icon and table rendering. When adding a new tool that returns list data, add a matching `_render_*_table()` method and update the `icon` map and `detail` dispatch block.

### Cost & Budget

`executor.py:_check_budget()` reads `AI Settings.max_monthly_budget` and sums `AI Usage Log.cost` for the current month per user. At 80% a realtime warning is published; at 100% the request is blocked. All usage is logged to `AI Usage Log` regardless of outcome (including denials and blocks, with `permission_result`, `agent_code`, `agent_name`, `user_roles` recorded per row).

### Business Intelligence Tools (`api/bi_tools.py`)

Separate from `api/tools.py`'s CRUD-style tools — read-only analytical/reporting tools (sales trend, top customers/items, overdue AR, stock alerts, follow-up opportunities, vehicle diagnostics) plus composite cross-module tools (`get_so_invoice_gap`, `get_sales_pipeline_status`, `get_customer_360`, `get_po_receipt_gap`, `get_monthly_pl_bridge`, `get_sales_order_dashboard`). Tools that return a `metrics` key are listed in `chat.py:ANALYTICAL_TOOLS` and get a second AI call to interpret the numbers into findings/risks/recommendations/required_actions — remember to add any new metrics-returning tool's intent to that frozenset.

### Voice Input (`api/voice.py`)

Optional voice-to-text entry point, configured via `AI Settings.enable_voice_input` / `voice_provider` / `voice_api_key` (same `__Auth`-backed password pattern as the main provider keys, via `get_voice_api_key()`).

## Key Files

| File | Purpose |
|---|---|
| `api/tools.py` | ~80 CRUD/action tool functions + TOOL_REGISTRY + TOOLS_SCHEMA (96 tools total with bi_tools.py) |
| `api/bi_tools.py` | Read-only BI/analytics tools + composite cross-module reports |
| `api/router.py` | Builds system prompt (RBAC + agent filtered), calls provider, extracts JSON |
| `api/executor.py` | Budget check, per-tool RBAC re-check, tool dispatch, usage logging |
| `api/chat.py` | Whitelisted endpoints (`send_message`, `test_connection`, `get_usage_summary`, `get_agents`, `get_daily_briefing`, `get_settings_status`); analytics interpreter |
| `api/agent_manager.py` | AI Agent persona loading/caching, governance checks (agent switch lockdown), prompt/tool/KPI merging |
| `api/supervisor.py` | Auto-routing classifier — picks best specialist agent for a message (System Manager + Auto mode only) |
| `api/permission_manager.py` | RBAC: tool → allowed-roles map, permission checks, prompt schema filtering |
| `api/voice.py` | Voice input endpoint |
| `providers/__init__.py` | Provider factory |
| `providers/openai_compatible.py` | OpenAI/OpenRouter/Groq/Google implementation |
| `providers/anthropic_provider.py` | Claude implementation |
| `ai_assistant/doctype/ai_settings/ai_settings.py` | Single DocType with `get_active_api_key()` / `get_voice_api_key()` fix |
| `ai_assistant/doctype/ai_agent/` | Agent persona DocType (+ `ai_agent_tool`, `ai_agent_role`, `ai_agent_kpi` child tables) |
| `ai_assistant/doctype/ai_tool_permission/` | RBAC DocType (+ `ai_tool_permission_role` child table) |
| `ai_assistant/fixtures/ai_agent.json` | Shipped agent personas (general, sales_manager, accounts_manager, workshop_advisor, ceo_assistant, supervisor, sales, marketing, accounts, operations, bi) |
| `public/js/ai_desk_launcher.js` | Floating FAB injected site-wide |
| `ai_assistant/page/ai_chat/ai_chat.js` | Chat UI class |

## Dependencies

- `openai>=1.30.0` — used for OpenAI, OpenRouter, Groq, Google Gemini (all via `base_url` override)
- `anthropic>=0.30.0` — used only when provider is "Claude (Anthropic)"

The `anthropic` package is lazy-imported inside `AnthropicProvider.__init__` to avoid import errors when Claude is not the active provider.
