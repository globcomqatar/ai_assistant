# AI Assistant Security Fix Test Plan

Scope: `frappe-bench/apps/ai_assistant`

## Permission Tests

1. Normal user cannot read AI Usage Log
   - Login as a non-System Manager user.
   - Attempt to open the AI Usage Log list and an existing AI Usage Log document.
   - Expected: access is denied.

2. Normal user can only access sanitized usage summary
   - Call `ai_assistant.api.chat.get_usage_summary` as a non-System Manager user.
   - Expected: response contains request/token summary and budget percentage only; no prompts, responses, tool parameters, errors, or raw cost details.

3. Normal user cannot call management dashboard APIs
   - Call each method in `ai_assistant.api.dashboard` as a user without management roles.
   - Expected: `frappe.PermissionError`.

4. Sales user cannot access accounting/management summary without required roles and tool permission
   - Login as a user with Sales role but without Accounts Manager/System Manager/management role.
   - Call `ai_assistant.api.chat.get_daily_briefing`.
   - Expected: permission denied.

5. Management user without AI Tool Permission cannot bypass tool RBAC
   - Login as a management role user who lacks permission for `get_management_summary`.
   - Call `get_daily_briefing`.
   - Expected: permission denied by AI Tool Permission validation.

## Agent and Tool Metadata Tests

6. `get_available_agents` ignores supplied user argument
   - Login as a normal user.
   - Call `ai_assistant.api.agent_manager.get_available_agents(user="Administrator")`.
   - Expected: response is for the logged-in user only and does not expose System Manager-only agents.

7. Normal user cannot read full AI Agent or AI Tool DocTypes
   - Attempt to open AI Agent and AI Tool list/form as non-System Manager.
   - Expected: access denied.

8. Tool helper endpoints return only permitted tools
   - Call `ai_assistant.api.tools.get_tool_names` as a normal user.
   - Expected: only tools allowed by AI Tool Permission are returned.

## High-Risk Write Tests

9. High-risk write returns confirmation requirement
   - Trigger AI intent `create_sales_invoice` without confirmation.
   - Expected: no Sales Invoice is created and response contains `confirmation_required: true`.

10. Confirmed high-risk write respects ERPNext permissions
   - Trigger a confirmed high-risk write as a user without ERPNext create/write permission for the target DocType.
   - Expected: permission denied and no document is created.

11. Confirmed high-risk write succeeds only with proper ERPNext permission
   - Trigger a confirmed high-risk write as a user with the correct ERPNext permission and AI Tool Permission.
   - Expected: document is created normally without `ignore_permissions` bypass.

## Error Handling Tests

12. Tool server errors return safe messages
   - Force a tool error in a non-production test site.
   - Expected: user response is generic; detailed error is present only in server logs.

13. Daily briefing errors return safe messages
   - Temporarily break a BI dependency in a test site.
   - Expected: endpoint returns a generic unavailable message and logs the server-side error.
