# AI Action Center Manual Test Plan

## Scope

Manual validation for Phase 2 Management Intelligence Action Center buttons on AI Chat Required Action cards.

## Tests

1. Create Task from Required Action
   - Run a Management Intelligence report with at least one Required Action.
   - Click **Create Task**.
   - Expected: a Task is created using the action title, priority mapping, suggested next step, and AI context.

2. Create Follow-up from Required Action
   - Click **Follow-up** on a Required Action.
   - Expected: a Task is created with subject `Follow-up: {action}` and description from `suggested_next_step`.

3. Open related Quotation
   - Use a Required Action with `related_doctype = Quotation` and a valid `related_document`.
   - Click **Open Document**.
   - Expected: user is routed to the Quotation only if they have read permission.

4. Open related Sales Invoice
   - Use a Required Action with `related_doctype = Sales Invoice` and a valid `related_document`.
   - Click **Open Document**.
   - Expected: user is routed to the Sales Invoice only if they have read permission.

5. Draft Email modal
   - Click **Draft Email**.
   - Expected: a modal opens with `to`, `subject`, and `body`; no email is sent.
   - Click **Copy Draft** and confirm the draft text is copied or displayed.

6. Normal user without Task create permission
   - Log in as a user without Task create permission.
   - Click **Create Task**.
   - Expected: permission denied; no Task is created.

7. User cannot open document without read permission
   - Use a related document the user cannot read.
   - Click **Open Document**.
   - Expected: permission denied or not available; user is not routed to the document.

8. No high-risk financial document creation
   - Click every Action Center button from reports involving invoices, payments, stock, or accounting.
   - Expected: only Task/follow-up Task, route validation, assign placeholder, or draft email are produced.
   - Confirm no invoice, payment, journal entry, stock entry, purchase invoice, salary slip, or expense claim is created.
