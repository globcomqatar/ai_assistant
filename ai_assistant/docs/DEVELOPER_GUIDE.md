# AI Assistant — Developer Guide

Version 15.24.14 · Sprint 2.5 Wave 2

---

## Quick Start

```bash
# After any Python change
bench --site mysite.localhost migrate

# After JS/CSS changes
bench build --app ai_assistant

# Run pure Python tests (no bench required)
cd /workspace/development/frappe-bench/apps/ai_assistant
python -m pytest tests/unit/ tests/regression/ -v

# Run original score normalization test
python -m pytest tests/test_score_normalization.py -v
```

---

## Adding a New Tool

1. **Write the function** in `api/tools.py`:
   ```python
   def get_my_report(period: str = "monthly") -> dict:
       require_management_access()
       # ... query ERPNext ...
       return {"status": "success", "data": [...]}
   ```
   
2. **Register in TOOL_REGISTRY** (same file):
   ```python
   TOOL_REGISTRY["get_my_report"] = get_my_report
   ```

3. **Document in TOOLS_SCHEMA** (same file):
   ```python
   {
       "name": "get_my_report",
       "description": "Get my custom report...",
       "parameters": {
           "type": "object",
           "properties": {
               "period": {"type": "string", "description": "monthly or quarterly"}
           }
       }
   }
   ```

4. **Create an AI Tool record** and **AI Tool Permission** in the database (or add to `setup.py`).

5. **Add a render method** in `ai_assistant/page/ai_chat/ai_chat.js` for custom table display.

---

## Logging

Use the centralized logger instead of calling `frappe.logger()` directly:

```python
from ai_assistant.utils.logger import log_request, log_security, log_exception

# Category-specific helpers
log_request("Chat message received", user=user, agent=agent_code)
log_security("Tool denied", tool=tool_name, user=user)
log_exception("Provider call failed", exc=exc, user=user)

# Generic with level
from ai_assistant.utils.logger import log_engine
log_engine("Model selected", model=model_name, level="debug")
```

**Never use `frappe.log_error()` for routine events** — it writes to Error Log (visible to System Manager UI). Use it only for genuine exceptions you want a developer to investigate.

---

## Exception Handling

Use the exception hierarchy from `core/exceptions.py`:

```python
from ai_assistant.core.exceptions import ProviderError, ConfigurationError

# Raise platform exceptions — they carry user-safe messages
raise ProviderError(
    "OpenAI returned 429",             # developer log
    user_message="AI service is busy.",  # shown to user
    recovery="Try again in a moment.",
)
```

In API handlers, convert exceptions to responses:

```python
from ai_assistant.core.response import from_exception, RequestTimer

@frappe.whitelist()
def my_endpoint():
    timer = RequestTimer()
    try:
        result = do_work()
        return ok("Done.", result, execution_time=timer.elapsed())
    except AIAssistantError as exc:
        log_exception("my_endpoint failed", exc=exc)
        return from_exception(exc, execution_time=timer.elapsed())
```

---

## Performance Monitoring

```python
from ai_assistant.core.performance import timed, PerformanceTracker

# Context manager for a single block
with timed("bi_report_query", user=user):
    data = frappe.db.sql("SELECT ...")

# Per-request tracker for multiple stages
tracker = PerformanceTracker()
tracker.start("routing")
agent = resolve_agent(user, message)
tracker.stop("routing")

tracker.start("provider")
response = provider.chat(messages, prompt)
tracker.stop("provider")

print(tracker.summary())
# {"total_s": 1.23, "steps": [{"name": "routing", "elapsed_ms": 45.2, ...}, ...]}
```

---

## Debug Mode

```python
from ai_assistant.core.debug import is_debug_mode, debug_log, debug_dump

debug_log("System prompt built", data=system_prompt, user=user)
debug_dump("Tool result", tool_result)   # pretty-prints JSON
```

Enable by setting `ai_debug_mode=1` in `site_config.json` or enabling `developer_mode`.

---

## Metrics

```python
from ai_assistant.core.metrics import metrics

# Record events
metrics.record_request(success=True, tokens=1240, cost=0.0024, elapsed=1.2)
metrics.record_action("create_task", success=True)
metrics.record_error("ProviderError")

# Query
snapshot = metrics.snapshot()
# {"requests": {"total": 42, "success": 40, ...}, "errors": {...}, ...}
```

Metrics are per-worker-process and reset on restart. For site-wide persistent metrics, query `tabAI Usage Log` directly.

---

## Health Check

```python
from ai_assistant.services.health_service import health_service

status = health_service.check_all()
# {"status": "ok", "version": "15.24.14", "checks": {"database": {"status": "ok"}, ...}}

# API endpoint (System Manager only):
# frappe.call("ai_assistant.api.health.get_health_status")
```

---

## API Response Standard

```python
from ai_assistant.core.response import ok, error, from_exception

# Success
return ok("Report generated.", data=report_data, warnings=["No data for last week."])

# Error (never exposes internal details)
return error("Provider timeout.", user_message="AI is temporarily unavailable.")

# From exception hierarchy
return from_exception(exc)
```

All responses include: `success`, `ok`, `message`, `request_id`, and optionally `execution_time`, `warnings`, `errors`.

---

## Security Rules

1. **Never use `ignore_permissions=True`** in tool functions. Use `insert_with_permission(doc)` from `security/security.py` — it checks the DocType create permission before inserting.
   - *Exception*: `AI Usage Log` in `executor.py` uses `ignore_permissions=True` because audit logs must be written regardless of the acting user's DocType permissions. This is documented and intentional.

2. **Always validate tool inputs** — use `frappe.throw()` with `frappe.ValidationError` for invalid parameters.

3. **Never expose Python tracebacks** to the frontend — use `from_exception()` which extracts only the user-safe message.

4. **RBAC is enforced server-side** — the AI never receives tools the user cannot use (filtered in `router.py` via `permission_manager.get_permitted_tools_schema()`).

5. **SQL queries use parameterized form**:
   ```python
   # Correct
   frappe.db.sql("SELECT ... WHERE user = %s", (user,))
   
   # Wrong — SQL injection risk
   frappe.db.sql(f"SELECT ... WHERE user = '{user}'")
   ```

---

## Testing

```
tests/
├── conftest.py              Frappe mock infrastructure
├── test_score_normalization.py  Original normalization tests
├── unit/                    Pure Python (no Frappe context)
│   ├── test_config.py       config/settings.py constants
│   ├── test_utils_helpers.py utils/helpers.py functions
│   ├── test_registries.py   action_registry + workflow_registry
│   ├── test_exceptions.py   exception hierarchy
│   ├── test_response.py     API response helpers
│   └── test_performance.py  performance tracking utilities
├── service/                 Standalone + bench context tests
│   └── test_services.py     Service classes + metrics collector
├── regression/              Fast smoke tests
│   └── test_smoke.py        Import chain + object identity checks
├── api/                     API endpoint tests (bench context)
└── performance/             Load and timing tests
```

Pure Python tests run with `python -m pytest tests/unit/ tests/regression/ -v`.
Integration tests require `bench --site mysite.localhost run-tests --app ai_assistant`.
