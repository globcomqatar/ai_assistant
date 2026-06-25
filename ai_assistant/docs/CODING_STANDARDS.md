# AI Assistant — Coding Standards

Version 15.24.14 · Sprint 2.5 Wave 2

---

## Python Style

- **Python 3.11+** — use `str | None`, `list[dict]`, `from __future__ import annotations`
- **Tabs for indentation** in Frappe DocType files and api/ files (Frappe convention)
- **4 spaces** in new packages (core/, services/, security/, registries/)
- **Type annotations** on all public function signatures
- **Docstrings**: one-line for simple helpers; multi-line for classes and complex functions
- **No inline comments** explaining *what* — only *why* (non-obvious invariants, workarounds)

---

## Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Module | `snake_case.py` | `permission_manager.py` |
| Class | `PascalCase` | `ProviderManager` |
| Function / method | `snake_case` | `get_allowed_tools()` |
| Constant | `UPPER_SNAKE_CASE` | `HIGH_RISK_WRITE_TOOLS` |
| Private helper | `_snake_case` | `_load_permission_map()` |
| Frappe logger name | `ai_assistant.{category}` | `ai_assistant.security` |

---

## Module Responsibilities

| Layer | Responsibility |
|---|---|
| `api/` | `@frappe.whitelist()` wrappers only — call services/core, return response |
| `core/` | Engine abstractions, exception hierarchy, response/metrics utilities |
| `services/` | Business-logic orchestration — delegates to api/ functions or registries |
| `registries/` | Pure data definitions — no DB calls, no Frappe imports where possible |
| `security/` | RBAC, permission guards, confirmation helpers |
| `utils/` | Stateless helper functions — no side effects |
| `providers/` | AI provider adapters — return `AIResponse` dataclasses |

---

## Error Handling Rules

1. Raise `AIAssistantError` subclasses inside platform code.
2. Catch `Exception` only at the outermost API boundary; convert to `from_exception()`.
3. Use `frappe.throw()` to surface user-visible validation errors in tool functions.
4. Log exceptions with `log_exception()`, not bare `print()` or `frappe.log_error()`.
5. Never expose Python tracebacks to the browser.

---

## Frappe-Specific Rules

- `@frappe.whitelist()` — only in `api/` layer; never in services or registries
- `frappe.db.commit()` — only in action handler functions (discrete user-initiated writes)
- `doc.flags.ignore_permissions = True` — only for `AI Usage Log` (documented exception)
- `frappe.get_all()` — prefer over `frappe.db.sql()` unless complex aggregation needed
- `frappe.db.sql()` — always use `%s` parameterized form
- `frappe.throw()` — always pass `frappe.ValidationError` or `frappe.PermissionError` as second arg
- Single DocType passwords — use `get_decrypted_password("AI Settings", "AI Settings", field)` (NEVER `doc.get_password()`)

---

## Version Bumping

Always increment `ai_assistant/__init__.py __version__` after any change:
- Format: `15.MINOR.PATCH` (e.g., `15.24.14`)
- Bump PATCH for bug fixes and quality improvements
- Bump MINOR for new features or significant refactoring

---

## Git Commit Convention

```
type(scope): short summary (v15.X.Y)

- Bullet details if needed

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

---

## Adding to Phase 3

When implementing Phase 3 (Predictive Intelligence):

1. **Do not modify** `api/chat.py`, `api/executor.py`, or `api/tools.py` unless absolutely necessary — they are the stable Phase 2 core.
2. **Extend** `core/orchestrator.py` — subclass `AIOrchestrator` to add predictive routing.
3. **Populate** `registries/playbook_registry.py` and `registries/kpi_registry.py` with real entries.
4. **Register** ML models in `registries/prediction_registry.py`.
5. **Replace** `core/metrics.py` in-process counters with Redis writes for site-wide aggregation.
