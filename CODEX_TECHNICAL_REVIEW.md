# Codex Technical Review: AI Assistant Frappe App

Scope: `frappe-bench/apps/ai_assistant`

This review covers only the AI Assistant Frappe application. ERPNext and Frappe framework code were not reviewed.

## Critical Issues

### 1. Tool execution bypasses native ERPNext permissions

Many AI tools create or modify ERPNext documents with `ignore_permissions = True`. The shared helper `_save_and_commit()` applies this bypass to every document it inserts, and several conversion/payment/update tools apply it directly.

Affected examples:

- `ai_assistant/api/tools.py::_save_and_commit`
- `convert_quotation_to_sales_order`
- `convert_so_to_invoice`
- `convert_so_to_delivery_note`
- `create_sales_return`
- `generate_payment_from_invoice`
- `update_task_status`

Impact:

AI Tool Permission becomes the only authorization layer. A user allowed to call a broad tool may bypass standard ERPNext DocType permissions, user permissions, account permissions, company restrictions, territory restrictions, and other business controls.

Recommendation:

Remove broad `ignore_permissions`. Use normal `doc.insert()` and `doc.save()`, `doc.check_permission()`, `frappe.has_permission()`, and permission-aware reads/writes. Any privileged action should be isolated behind explicit System Manager-only checks and audited with a clear reason.

### 2. AI Usage Log is readable by all users

`AI Usage Log` stores prompts, responses, requested tools, permission results, user roles, costs, agent information, and errors, but grants read access to role `All`.

Impact:

Users may be able to view other users' prompts and AI responses, including sensitive business data, customer data, financial data, HR data, or prompt-injected secrets.

Recommendation:

Remove role `All` read access from `AI Usage Log`. Allow System Manager to read all logs. If users need usage visibility, expose a controlled endpoint that returns only the current user's summary or sanitized own logs.

### 3. Dashboard KPI endpoints expose global business metrics

The whitelisted functions in `ai_assistant/api/dashboard.py` return global sales, overdue invoice counts, low stock, open job counts, pending quotations, and new customer counts without explicit role or tool permission checks.

Impact:

Any authenticated user who can call these endpoints may access business-wide operational metrics.

Recommendation:

Gate each KPI endpoint with explicit roles or the same AI Tool Permission model used by AI tools. At minimum, require appropriate business roles such as Accounts Manager, Sales Manager, Stock Manager, or System Manager.

### 4. Daily briefing bypasses AI tool RBAC

`get_daily_briefing()` is whitelisted, allows role `All`, and directly calls `get_management_summary()` instead of passing through the AI tool permission layer.

Impact:

Users can obtain a management-level summary containing sales, collections, overdue invoices, quotations, inventory, workshop status, and action priorities without being authorized for the corresponding AI tool.

Recommendation:

Route this endpoint through the same server-side permission validation used by `execute_actions()`, or restrict it to management roles.

## High Priority Issues

### 1. Broad reads bypass user-level data access

Many tools use `frappe.get_all()` or raw SQL for user-facing data. These calls can bypass normal user-level document permissions or fail to apply company/user permission filters.

Affected areas include:

- Customer history
- Sales invoices
- Purchase invoices
- Payments
- Salary slips
- Payroll summary
- Attendance
- Payables analysis
- Sales analysis
- Management summary
- Business analysis

Recommendation:

Use `frappe.get_list()` for user-facing reads where possible. For aggregate reports that require SQL, gate the tool with explicit business roles and apply company/user scope filters.

### 2. Financial tools bypass sensitive accounting permissions

`get_account_balance()` passes `ignore_account_permission=True`. Several finance and BI tools aggregate global accounting data with broad SQL.

Impact:

Users may access account balances, AR, AP, payroll, and sales performance data outside their normal ERPNext permissions.

Recommendation:

Respect account permissions. Require finance roles for financial tools. Apply company/account filters and avoid `ignore_account_permission=True` except for tightly controlled admin-only workflows.

### 3. High-risk write tools execute without confirmation

The AI can execute write tools immediately after selecting an intent, subject only to AI Tool Permission.

High-risk examples:

- `create_sales_invoice`
- `record_payment`
- `create_journal_entry`
- `generate_payment_from_invoice`
- `create_purchase_invoice`
- `create_stock_entry`
- `create_employee`
- `create_leave_application`
- `create_expense_claim`

Impact:

Prompt injection, model error, or ambiguous user input can create financial, HR, stock, or operational records.

Recommendation:

Classify tools by risk tier. Require explicit confirmation before executing high-risk writes. Return `confirmation_required` with sanitized parameters, and execute only after a confirmed request.

### 4. Prompt injection boundary is weak

Client-supplied `history` is accepted and sent to the provider. Model output is parsed into JSON and treated as executable tool intent if the user has tool permission.

Impact:

User content can influence tool selection and parameters. If a user is allowed to call a powerful tool, prompt injection can cause unwanted action execution.

Recommendation:

Treat all model output as untrusted. Validate action shape and parameters against strict schemas. Reject unknown parameters. Store or validate history server-side. Require confirmation for write tools.

### 5. Agent metadata endpoint allows user parameter impersonation

`get_available_agents(user=None)` is whitelisted and accepts a user argument. A caller should not be able to request agent availability for another user.

Recommendation:

Ignore client-supplied `user` in whitelisted calls. Always use `frappe.session.user`, or split internal and whitelisted APIs.

### 6. Voice transcription endpoint lacks payload and abuse controls

`transcribe_audio()` accepts arbitrary base64 audio and may send it to paid external providers. There is no size limit, duration limit, rate limit, language validation, or usage logging.

Impact:

Large payloads can exhaust memory or create unexpected external API cost.

Recommendation:

Add maximum payload size, validate language/provider, rate-limit calls, return generic errors, and log or budget voice usage.

### 7. AI Agent and AI Tool DocTypes expose sensitive metadata to role All

`AI Agent` grants read access to role `All`, potentially exposing system prompts and configuration. `AI Tool` also grants read access to role `All`, exposing the internal tool surface.

Recommendation:

Restrict full reads to System Manager. Expose filtered, sanitized agent/tool metadata through controlled APIs for regular users.

## Medium Priority Issues

### 1. SQL helper functions interpolate SQL fragments

`_sql_sum()` and `_sql_count()` interpolate table, field, and where strings directly. Current calls appear internal, but the helper is risky if reused with user-controlled fragments.

Recommendation:

Replace with explicit query functions or restrict inputs to fixed whitelists.

### 2. Input validation is too thin

Most tools validate only required fields. Dates, amounts, quantities, status values, account names, item codes, voucher types, company scope, and limits are not consistently validated.

Recommendation:

Add schema validation for every tool. Clamp limits, reject negative values where inappropriate, validate dates, and whitelist enum-like fields.

### 3. Transaction boundaries are fragmented

The app commits inside helper functions and log writes.

Impact:

Partial actions can be committed even if later actions in the same AI request fail.

Recommendation:

Avoid manual commits in normal request flow. Let Frappe manage transactions. Keep audit logging robust but separate from business transaction correctness.

### 4. Error handling can expose raw exception text

Some endpoints return `str(exc)` directly to users.

Recommendation:

Log detailed context server-side and return generic user-safe messages. Avoid exposing provider errors, SQL details, stack traces, or secrets.

### 5. Budget control does not cover all costs or abuse cases

Budget checks focus on logged LLM costs. Voice transcription, tool side effects, retries, and request frequency are not fully controlled.

Recommendation:

Add request rate limits, voice usage accounting, and optional per-role or per-site limits.

### 6. BI reports may be expensive on large sites

Several BI tools run broad raw SQL aggregations over ERP tables and may not use tight indexed filters consistently.

Recommendation:

Add date bounds, company filters, indexes where appropriate, caching for expensive summaries, and role-gated access.

## Low Priority Improvements

### 1. Settings status endpoint reveals provider metadata

`get_settings_status()` exposes provider/model/feature state to all authenticated users.

Recommendation:

Return only UI-required booleans for regular users. Keep provider/model details System Manager-only.

### 2. Tool catalog helper endpoints expose full tool names

`get_tool_names()` and `get_tool_description()` are whitelisted and expose the tool catalog.

Recommendation:

Return only tools permitted for the current user, or restrict these endpoints to System Manager if they are only needed in admin forms.

### 3. Scheduler task is misleading

`reset_monthly_usage()` only logs a message while retention is handled through `default_log_clearing_doctypes`.

Recommendation:

Rename the task, remove it, or implement actual summary/reset behavior.

### 4. Dependency ranges are broad

`openai>=1.30.0` and `anthropic>=0.30.0` are open-ended.

Recommendation:

Pin tested compatible upper bounds for Frappe Cloud stability.

## Recommended Refactoring Plan

### 1. Add a central ToolContext

Create a context object with:

- `user`
- `roles`
- `allowed_companies`
- `request_id`
- `dry_run`
- `requires_confirmation`
- `require_role()`
- `require_doctype_permission()`
- `can_read()`
- `can_write()`
- `validate_company_scope()`
- `safe_get_list()`

Use this context for all tool execution.

### 2. Add tool metadata and risk tiers

Every tool should declare:

- `read_only`
- `draft_create`
- `high_risk_write`
- `financial`
- `hr_payroll`
- `stock_movement`

Use metadata to enforce roles, confirmation, audit logging, and UI behavior.

### 3. Make permission enforcement layered

Keep AI Tool Permission, but do not treat it as a replacement for ERPNext permissions.

Recommended layers:

1. User is authenticated.
2. User is allowed to use AI Assistant.
3. User is allowed to call the AI tool.
4. User has DocType permission for the underlying ERP document.
5. User passes user permission, company, account, and role constraints.
6. High-risk writes require explicit confirmation.

### 4. Harden LLM action execution

Treat model output as untrusted:

- Validate intent is registered.
- Validate parameters against schema.
- Reject unknown parameters.
- Clamp list limits.
- Confirm high-risk writes.
- Never allow user/history content to override safety rules.

### 5. Fix direct API exposure

All whitelisted endpoints should use explicit role checks, current session user only, or the same RBAC/tool permission layer.

### 6. Improve tests

Add tests for:

- Tool permission denial.
- ERPNext permission enforcement.
- Direct endpoint role checks.
- Prompt-injection attempts.
- High-risk write confirmation.
- Voice payload limits.
- Own-log versus all-log access.

## Summary

The AI Assistant app has useful server-side RBAC for tool selection, but the tool bodies and direct endpoints still bypass or sidestep important ERPNext security boundaries. The most important fixes are to remove broad `ignore_permissions`, restrict sensitive DocType reads, gate direct whitelisted endpoints, add confirmation for high-risk writes, and validate all model-selected actions as untrusted input.
