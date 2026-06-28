# 0020: Invoice Lifecycle Actions

Status: Accepted

Decision:

Add explicit shop-facing POST-only actions for issuing and voiding invoices,
making status transitions intentional and auditable without expanding into a
full accounting workflow.

**Issue and void are POST-only actions at dedicated URLs**

Both `billing:invoice_issue` and `billing:invoice_void` accept only POST
requests. GET requests are redirected safely to the invoice detail page without
mutation. This prevents accidental state changes from browser pre-fetching,
history navigation, or link-sharing, and follows the existing pattern established
by the repair-order status update view.

**Issue action sets `issued_at` only when blank**

When a draft invoice is issued, `issued_at` is set to today's date
(`timezone.localdate()`) if it was blank. If `issued_at` was already set
manually (e.g. via the edit form), the existing value is preserved. This
prevents overwriting intentional back-dated issue dates.

**Void invoices remain visible**

Voiding an invoice sets `status = void` but does not delete the invoice,
its line items, or its payments. The invoice remains accessible at its detail
URL and appears on the repair-order detail page with a Void status badge.
This preserves the financial history of the repair order for reference.

**Payments are blocked for void invoices**

`Payment.clean()` already raises a `ValidationError` when a payment is
attempted against a void invoice. The `payment_create` view now also performs
an early redirect with a clear message when the invoice is void, preventing
even the payment form from rendering. This guards against both UI-level and
direct-POST payment attempts.

**Record Payment is hidden for void invoices in the UI**

The `_invoice_summary.html` partial and `invoice_detail.html` already
conditionally rendered Record Payment based on `invoice.balance_due and
invoice.status != "void"`. The void guard ensures Record Payment is also
hidden when the invoice is void but has an outstanding balance (e.g. if it
was voided before being fully paid).

**Issue and Void buttons are POST forms with CSRF tokens**

Lifecycle action buttons in both the invoice detail page and the
repair-order invoice summary partial are plain HTML `<form method="post">`
elements. No custom JavaScript is introduced. CSRF protection is enforced
by Django's built-in middleware.

**`sync_payment_status()` does not revive void invoices**

The existing `Invoice.sync_payment_status()` method already guards against
touching void invoices (`if self.status == self.Status.VOID: return`). No
change was needed to prevent payment saves or deletes from accidentally
reverting a voided invoice to a paid/partially-paid state.

**Out of scope for this slice**

- Invoice status history model (audit trail of lifecycle transitions)
- Void reason field or void reason required validation
- Refunds or credit memos
- Reopening void invoices
- Locking line-item edits after issuing
- Preventing invoice field edits after issuing
- PDF generation, email invoices, payment links, accounting export
- Tax automation
- Customer portal
- API endpoints
- HTMX expansion beyond existing status update
- Custom JavaScript
- Tailwind or any frontend build tooling
