# Management Intelligence Test Plan

Scope: `frappe-bench/apps/ai_assistant`

## Backend Schema Tests

1. Sales analysis report
   - Ask: "Show sales analysis and advise what management should do."
   - Expected: `result.analysis` includes `executive_summary`, `findings`, `root_causes`, `risks`, `opportunities`, `recommendations`, `required_actions`, and `expected_business_impact`.
   - Verify `risks[*].severity` is one of `low`, `medium`, `high`, `critical`.
   - Verify `risks[*].risk_score` is between `0` and `100`.
   - Verify `opportunities[*].opportunity_score` is between `0` and `100`.

2. Management summary
   - Ask: "Give me today's management summary."
   - Expected: advisory sections explain what happened, why it matters, required action, and business impact.
   - Expected: no invented numeric values; figures should match report metrics or say `insufficient data`.

3. Business analysis
   - Ask: "Analyze my business and give me recommendations."
   - Expected: deterministic signals are present when metrics trigger them, such as collection risk for overdue invoices or inventory risk for low stock.

4. Legacy analysis fallback
   - Simulate an old analysis payload containing only `findings`, `risks`, `recommendations`, and `required_actions` as string arrays.
   - Expected: frontend renders the old format safely as advisory cards/lists.

5. Malformed AI JSON fallback
   - Force the interpreter provider to return malformed JSON on a test site.
   - Expected: chat does not break; server logs the parsing issue and either omits analysis or returns deterministic advisory signals.

## Permission Tests

6. Unauthorized user cannot access management intelligence
   - Login as a non-management user without the relevant AI Tool Permission.
   - Call management summary/dashboard flows.
   - Expected: permission denied.

7. System Manager can access full intelligence output
   - Login as System Manager.
   - Run sales analysis, management summary, and business analysis.
   - Expected: full advisory analysis renders in the chat UI.

## Frontend UI Tests

8. New advisory cards render
   - Verify the chat result shows:
     - Executive Summary
     - Findings
     - Root Causes
     - Risks with severity badge and score
     - Opportunities with score
     - Recommendations
     - Required Actions with priority badge and owner role
     - Expected Business Impact

9. Mobile layout
   - Open the AI Chat page on a mobile-width viewport.
   - Expected: advisory cards stack in one column, badges do not overflow, and long text wraps.
