# 0021: Void Invoice Edit Guards

Status: Accepted

Decision:

Void invoices become billing-read-only: staff can still view and print them,
but cannot modify their billing contents through invoice edit, line-item
create/edit, or payment create.

**Void invoices remain visible but are billing-read-only**

Voiding an invoice (Slice 16) sets `status = void` but retains the invoice,
its line items, and its payments for audit and history. This slice adds the
complementary guard: a void invoice cannot be mutated through any billing
edit action. Staff who need to fix a voided invoice must create a new one.

**UI actions are hidden for void invoices**

The following actions are hidden in `invoice_detail.html` and
`_invoice_summary.html` when `invoice.status == "void"`:

- Edit Invoice
- Add Line Item
- Edit Line Item (in the line-items table on the RO summary)

Issue Invoice and Void Invoice were already hidden for void invoices from
Slice 16 (Issue requires draft status; Void hides when already void).
Record Payment was already hidden for void invoices from Slice 16
(`invoice.balance_due and invoice.status != "void"` condition).

Hiding buttons is a UX improvement. It does not replace server-side guards.

**Direct URL access is also guarded at the view level**

Even with buttons hidden, a user could construct or bookmark a direct URL.
The following views now redirect immediately with an error message when the
invoice is void:

- `billing:invoice_edit` → redirects to `billing:invoice_detail`
- `billing:line_item_create` → redirects to `billing:invoice_detail`
- `billing:line_item_edit` → redirects to `billing:invoice_detail`
- `billing:payment_create` → already guarded in Slice 16; redirects to
  `repair_orders:detail` with an error message (behavior preserved)

The redirect target for invoice/line-item edits is `billing:invoice_detail`
rather than `repair_orders:detail`, because the invoice detail page is the
natural context for these errors — it shows the invoice state and makes the
void status immediately visible to the user.

**Issued invoices are not locked in this slice**

This slice intentionally locks only void invoices. Draft, issued,
partially-paid, and paid invoices remain fully editable. Locking issued
invoices (to prevent retroactive changes after delivery to a customer) is
a reasonable future constraint but is deferred because:

- The shop currently issues invoices informally and may need to adjust them.
- No customer portal exists, so there is no external consumer of issued
  invoices whose view could be invalidated by an edit.
- Adding the lock later is a one-line guard change — the pattern is
  established here and can be extended without migration.

**No model migration was added**

All guards are view-level and template-level. The `Invoice.Status.VOID` enum
value already exists. No new fields, constraints, or migrations are required.

**No custom JavaScript was introduced**

All UI changes are server-rendered conditional template blocks. No client-side
scripting is used.

**Out of scope for this slice**

- Locking issued, partially-paid, or paid invoices
- Invoice status history model (audit trail of who voided or edited)
- Void reason field
- Refunds or credit memos
- Reopening void invoices
- PDF generation, email invoices, payment links, accounting export
- Tax automation
- Customer portal
- API endpoints
- HTMX expansion beyond existing status update
- Custom JavaScript
- Tailwind or any frontend build tooling
