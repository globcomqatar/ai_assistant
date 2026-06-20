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
    → router.py:route()           # builds system prompt, calls AI provider
      → providers/__init__.py:get_provider()   # reads AI Settings, returns provider
        → OpenAICompatibleProvider / AnthropicProvider
    → executor.py:execute_actions()   # maps intents → tool functions, checks budget
      → api/tools.py:TOOL_REGISTRY[intent](**params)   # actual ERPNext ORM calls
    → AI Usage Log (written via frappe.new_doc)
```

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

`executor.py:_check_budget()` reads `AI Settings.max_monthly_budget` and sums `AI Usage Log.cost` for the current month per user. At 80% a realtime warning is published; at 100% the request is blocked. All usage is logged to `AI Usage Log` regardless of outcome.

## Key Files

| File | Purpose |
|---|---|
| `api/tools.py` | All 35 tool functions + TOOL_REGISTRY + TOOLS_SCHEMA |
| `api/router.py` | Builds system prompt, calls provider, extracts JSON |
| `api/executor.py` | Budget check, tool dispatch, usage logging |
| `api/chat.py` | Whitelisted Frappe endpoints (`send_message`, `test_connection`, `get_usage_summary`) |
| `providers/__init__.py` | Provider factory |
| `providers/openai_compatible.py` | OpenAI/OpenRouter/Groq/Google implementation |
| `providers/anthropic_provider.py` | Claude implementation |
| `ai_assistant/doctype/ai_settings/ai_settings.py` | Single DocType with `get_active_api_key()` fix |
| `public/js/ai_desk_launcher.js` | Floating FAB injected site-wide |
| `ai_assistant/page/ai_chat/ai_chat.js` | Chat UI class |

## Dependencies

- `openai>=1.30.0` — used for OpenAI, OpenRouter, Groq, Google Gemini (all via `base_url` override)
- `anthropic>=0.30.0` — used only when provider is "Claude (Anthropic)"

The `anthropic` package is lazy-imported inside `AnthropicProvider.__init__` to avoid import errors when Claude is not the active provider.
