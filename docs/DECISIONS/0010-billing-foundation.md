# 0010: Billing Foundation

Status: Accepted

Decision:

Introduce `billing.Invoice` and `billing.Payment` as the billing foundation for
repair orders.

**Invoice is one-to-one with RepairOrder**

A repair order can have at most one invoice. This reflects the current shop
workflow: one job, one bill. Splitting invoices or supplemental billing is
deferred until the workflow proves it needs it.

The `OneToOneField` with `PROTECT` ensures an invoice cannot be orphaned by
repair order deletion and prevents a repair order from having multiple invoices.

**Invoice totals are manual fields for now**

`subtotal` and `tax_amount` are manually entered `DecimalField` values. There are
no invoice line items (parts, labor, materials) yet. This keeps the billing
foundation minimal and unblocks payment tracking without requiring the full
line-item model.

Line items, estimates, parts pricing, and labor rates are deferred to a later
slice.

**Payments sync invoice status automatically**

`Payment.save()` and `Payment.delete()` call `invoice.sync_payment_status()`
after the payment operation completes. `sync_payment_status()` transitions the
invoice through:

```
draft / issued → partially_paid → paid
paid / partially_paid → draft  (if all payments removed)
void → (never touched)
```

Status is not modified when `amount_paid == 0` and the invoice is already
`draft` or `issued`, avoiding aggressive resets for invoices that haven't
been touched by payments.

**Django admin is the current billing interface**

`InvoiceAdmin` and `PaymentAdmin` expose billing records through Django admin.
No custom billing UI exists in this slice.

**Deferred scope**

- Estimate / quote models
- Invoice line items (parts, labor, materials)
- Tax jurisdiction logic
- Configurable invoice numbering
- PDF invoice generation
- Email invoice sending
- Payment processor integration (Stripe, Square, etc.)
- Accounting export (QuickBooks, etc.)
- Custom billing UI
