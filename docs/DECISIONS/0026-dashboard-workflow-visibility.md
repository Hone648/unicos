# 0026: Dashboard Workflow Visibility

Status: Accepted

Decision:

Add a read-only dashboard overview for common shop workflow signals: active
repair orders, ready-for-pickup repair orders, unpaid invoices, repair orders
blocked from closure by invoice balance, and recently updated repair orders.

Rationale:

- Staff need a quick first screen that points to work requiring attention.
- The dashboard should reuse existing repair-order status and invoice balance
  rules instead of adding new workflow state.
- Closure-blocked visibility should match the existing rule that final-status
  movement is blocked by a non-void invoice with a balance due.
- Links should send staff back into existing detail/list views for action.

Scope:

- Read-only dashboard display only.
- No models, migrations, new statuses, auth changes, JavaScript, HTMX behavior,
  pagination, search changes, or billing workflow changes.
- Future dashboard filters, role-specific views, alerts, or reporting can be
  added in later slices if operational review justifies them.
