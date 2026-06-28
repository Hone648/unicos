# 0016: Shop-Facing Billing Workflow

Status: Accepted

Decision:

Add shop-facing invoice and payment views so staff can create invoices,
edit invoice details, and record payments from the repair-order workspace
without needing Django admin.

**Shop-facing invoice and payment workflow has been added**

Staff can now create an invoice for a repair order, edit its basic fields,
and record payments against it. The repair-order detail page shows the
invoice summary, a live balance, and a payments table.

**Invoices are created from repair orders**

The invoice create view is accessed via a URL that includes the repair order pk
(`/billing/repair-orders/<pk>/invoice/new/`). The view sets `invoice.repair_order`
from the URL, not from a form field. This enforces the one-invoice-per-repair-order
constraint at the view level in addition to the model's OneToOneField constraint.
A duplicate-create request is redirected to the repair-order detail with an info
message rather than raising a 500 error.

**Payments are recorded against invoices**

The payment create view is accessed via a URL that includes the invoice pk
(`/billing/invoices/<pk>/payments/new/`). The view sets `payment.invoice` from
the URL. Invoice is not exposed in the payment form.

**Existing billing model validation remains authoritative**

`Invoice.clean()` validates subtotal/tax >= 0 and due_date >= issued_at.
`Payment.clean()` validates amount > 0, rejects void invoices, and rejects
overpayments. These constraints are not duplicated in the forms. For the payment
view, after `form.save(commit=False)` the view sets `payment.invoice`, then
calls `payment.full_clean()` before saving so that invoice-dependent constraints
(void check, overpayment check) are enforced and surfaced as form errors.

**Invoice/payment status synchronization remains model-owned**

`Invoice.sync_payment_status()` is called automatically from `Payment.save()`
and `Payment.delete()`. The billing views do not call `sync_payment_status()`
directly; they rely on `Payment.save()` to trigger it.

**Invoice status is not exposed in the edit form**

`InvoiceForm` excludes `status`. Status transitions are driven by payments and
the existing `sync_payment_status()` logic. Allowing direct status edits from
the shop form would bypass this logic.

**Audit fields are set in views**

`invoice.created_by` and `invoice.updated_by` are set in the create/edit views.
`payment.received_by` is set in the payment create view. These fields are
excluded from their respective forms.

**Invoice section on repair-order detail is now interactive**

The read-only invoice block was replaced with an `_invoice_summary.html` partial
that shows:
- A "Create Invoice" button when no invoice exists.
- Invoice details, "Edit Invoice", and "Record Payment" (when balance > 0 and
  invoice is not void) when an invoice exists.
- A payments table when payments exist.

**Out of scope for this slice**

- Invoice line items (parts, labor)
- Parts/labor catalog
- Tax automation
- PDF generation
- Print templates
- Email invoices
- Refunds
- Void workflow expansion
- Deleting invoices or payments
- Repair-order status workflow changes
- API endpoints
- HTMX expansion beyond existing status update
- Tailwind or any frontend build tooling
- Custom JavaScript
