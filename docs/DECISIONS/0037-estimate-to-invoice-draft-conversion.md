# 0037 — Estimate-to-Invoice Draft Conversion

## Context

The app already has estimates, estimate line items, supplements, printable
estimate output, and a controlled estimate approval lifecycle (Slices 29–33),
plus an existing billing/invoice workflow (Slices 6–20). Until now there was no
controlled way to turn an approved estimate into an invoice; staff had to
re-enter the same line items by hand. This slice adds a single controlled action
that creates an invoice *draft* from an *approved* estimate, copying estimate
line items into invoice line items.

## Decision

### Only approved estimates can be converted

Conversion is allowed only when the estimate's status is `approved`. Draft,
submitted, declined, and expired estimates cannot be converted. This keeps the
estimate lifecycle (Slice 36) authoritative: an estimate becomes billable work
only once it has been formally approved.

### Conversion creates a draft invoice only

The created invoice is always `draft`. Conversion does not issue the invoice,
does not set `issued_at`, and does not record any payment. Issuing, voiding, and
payment remain separate billing actions with their own guards and permissions.
This preserves the existing invoice lifecycle untouched — conversion is only a
*creation* path, not a lifecycle change.

### Line items are copied, not live-linked

Estimate line items are copied field-for-field into new `InvoiceLineItem` rows
(`item_type`, `description`, `quantity`, `unit_price`). The copies are
independent: later edits to the estimate do not change the invoice, and invoice
edits do not change the estimate. This matches the domains' different lifecycles
(an estimate is a proposal; an invoice is a billing record with overpayment and
void guards). `EstimateLineItem.sort_order` has no `InvoiceLineItem` counterpart,
so estimate line items are copied in their natural display order and the invoice
preserves insertion order.

Because each `InvoiceLineItem.save()` recalculates the invoice subtotal, the
created invoice's total equals the approved estimate's total (which is itself
derived from its line items). No total is copied manually.

### Source-estimate traceability via a new nullable FK

A nullable `Invoice.source_estimate` foreign key (`PROTECT`,
`related_name="converted_invoices"`) records which estimate produced an invoice.
Normal (manually created) invoices leave it null. This:

- prevents duplicate conversion from the same estimate,
- gives audit traceability from both sides (estimate → invoice and invoice →
  estimate),
- avoids mutating the `Estimate` model.

A partial unique constraint (`unique_invoice_source_estimate`, condition
`source_estimate IS NOT NULL`) enforces "at most one invoice per source
estimate" at the database level, so normal invoices can still share the null
value.

### Duplicate conversion is blocked (two independent guards)

Two layers prevent a second invoice from a converted estimate:

1. `Invoice.repair_order` is one-to-one, so a repair order can hold only one
   invoice at all. The conversion service checks this and blocks with a clear
   message rather than letting the one-to-one constraint raise.
2. The `source_estimate` partial unique constraint blocks converting the *same*
   estimate twice even if the one-to-one slot were somehow free.

The conversion service re-validates inside a `transaction.atomic()` block after
taking a `select_for_update()` lock on the estimate row, so concurrent
conversion attempts serialize and the second is blocked. Conversion is all-or-
nothing: a blocked attempt creates no invoice and no line items.

### Conversion lives in a billing service

`billing/services.py` owns `convert_estimate_to_invoice(estimate, *,
created_by=None)` and the `estimate_can_convert_to_invoice(estimate)` predicate,
plus `EstimateInvoiceConversionError` / `EstimateInvoiceConversionBlocked`.
Conversion constructs billing objects (invoice number, draft status, line-item
copy), so the "how to build an invoice from an estimate" knowledge stays in
billing. The shop-facing trigger is `POST
/estimates/<pk>/convert-to-invoice/` (`estimates:convert_to_invoice`), which
requires the existing `billing.manage` permission — no new role or permission
was introduced.

### Conversion is one-way for now

This slice deliberately keeps conversion one-directional: estimate → invoice
draft. There is no "unconvert", no syncing of later estimate edits into the
invoice, and no merging of multiple estimates/supplements into one invoice. Each
of those would warrant its own slice once single-estimate conversion has been
used in practice.

## Migration

One migration: `billing/0003_invoice_source_estimate_and_more` adds the nullable
`source_estimate` FK and the partial unique constraint
`unique_invoice_source_estimate`. No estimate, repair-order, customer, or vehicle
schema changed. The field is nullable so all existing invoices remain valid.

## Consequences

- Approved, itemized estimates can be turned into draft invoices in one action,
  with line items copied and the invoice total matching the estimate total.
- Invoices are traceable to their source estimate from both the estimate detail
  page and the invoice detail page.
- Duplicate conversion is blocked at the service and database level.
- Invoice issuing, voiding, and payment behavior are unchanged.
- The authorization matrix is unchanged; conversion reuses `billing.manage`.
- Test count rose from 721 to 798.

## Remaining limitations

- No conversion of supplements into invoice supplements / additional invoices
  (the one-to-one repair-order/invoice relationship means a repair order still
  has a single invoice).
- No re-sync of estimate edits into an already-created invoice.
- No "unconvert" / detach action.
- No multi-estimate invoice merging and no partial conversion.
- No PDF, email, or signature workflow.
- No estimate locking by repair-order final status (deferred; existing behavior
  preserved).
