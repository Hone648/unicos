# 0027: Billing Invoice Queue

Status: Accepted

Decision:

Add a shop-facing, read-only invoice queue at `/billing/invoices/` so staff can
find invoices directly without first navigating through a repair order or
dashboard card.

Rationale:

- Billing review is a common workflow that deserves a direct workspace.
- The queue shows invoice, repair order, customer, vehicle, status, total,
  paid, balance due, issued date, and due date.
- Status filters use the existing `Invoice.Status` choices and ignore invalid
  status values safely.
- Search covers invoice number, repair-order number, customer identity fields,
  and common vehicle identity fields.
- Existing `Invoice.total_amount`, `Invoice.amount_paid`, and
  `Invoice.balance_due` remain the source of billing totals.

Scope:

- Read-only list/search/filter page only.
- No model changes or migrations.
- No payment behavior changes.
- No invoice status behavior changes.
- No repair-order workflow-rule changes.
- No export, PDF generation, email sending, JavaScript, HTMX behavior, or
  frontend build tooling.
