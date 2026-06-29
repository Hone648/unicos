# 0034 — Estimate Line Items and Supplements

## Context

Slice 29 added a basic `Estimate` spine: estimate records attached to a repair
order with a single manually entered `estimated_total` and insurance/claim
context. Body-shop estimates are itemized in practice, and insurer-driven work
routinely produces supplements (additional estimates issued against the same
job). This slice adds itemized estimate lines and a minimal supplement lineage
while leaving billing/invoice behavior untouched.

## Decision

### Estimate line items are separate from invoice line items

`EstimateLineItem` is its own model in the `estimates` app, distinct from
`billing.InvoiceLineItem`. They look similar (item type, description, quantity,
unit price, line total) but serve different domains and lifecycles:

- An estimate is a *proposal* — its totals are projections and may change as
  supplements are written.
- An invoice is a *billing record* — its line items drive money owed and are
  guarded against dropping below amounts already paid.

Coupling them would force invoice billing rules (overpayment guards, void
states, final-RO locks) onto estimates, which are pre-billing. Keeping them
separate preserves both lifecycles. Converting estimate lines into invoice lines
is explicitly deferred to a future slice.

### `estimated_total` is recalculated from line items when any exist

`EstimateLineItem.save()` and `.delete()` call `Estimate.recalculate_total()`,
which sums `line_total` across the estimate's line items and writes the result
to `estimated_total`. This mirrors the billing invoice
`recalculate_subtotal_from_line_items()` pattern, so the codebase has one
consistent "line items drive the total" mechanism.

### Manual `estimated_total` is preserved when no line items exist

An estimate with no line items keeps its manually entered `estimated_total`.
This supports quick ballpark estimates that have not been itemized yet. Once the
first line item is added, the total becomes calculated; `EstimateForm` disables
the `estimated_total` field (with help text) whenever line items exist, matching
the billing `InvoiceEditForm` subtotal-disabling pattern. Removing all line
items resets the calculated total to `0.00`.

### Supplements are Estimates with `kind="supplement"` and `parent_estimate`

Rather than introducing a separate `Supplement` model, a supplement is an
`Estimate` with `kind=Estimate.Kind.SUPPLEMENT` and a `parent_estimate`
self-foreign-key (`PROTECT`). Slice 29 already allowed multiple estimates per
repair order, and a supplement behaves exactly like an estimate — it has its own
line items, status, and total. Reusing the model:

- avoids a parallel estimate-like model and duplicated line-item plumbing,
- keeps supplements visible in the same estimate views and summaries,
- leaves room for revision/version semantics later without a schema reversal.

Lineage is validated in `Estimate.clean()`:

- an initial estimate must not have a `parent_estimate`,
- a supplement must have a `parent_estimate`,
- an estimate cannot be its own parent,
- a supplement must share the parent's repair order.

`parent_estimate` uses `PROTECT` so an estimate with supplements cannot be
deleted out from under its lineage.

### Permissions reuse repair-order permissions

Estimate line-item and supplement mutations reuse the existing authorization
matrix, exactly as Slice 29 did for estimates:

- line-item and supplement create/edit/delete require
  `PERM_REPAIR_ORDERS_MANAGE`,
- estimate detail requires `PERM_REPAIR_ORDERS_VIEW`.

No new roles or permissions were introduced; the authorization matrix is
unchanged.

### Line-item delete is a POST-only action

Estimate line items use `CASCADE` (they have no billing/payment significance, so
unlike invoice line items they can be removed). Removal is a POST-only action
(`estimates:line_item_delete`) rendered as an inline "Remove" button in the
detail table; a GET falls through to a redirect back to the estimate detail.

### Invoice generation, approval, PDF, and signatures remain deferred

This slice deliberately does not generate invoices from estimates, convert
estimate lines into invoice lines, produce PDF estimates, or add
customer/insurer approval or signature workflows. Those each warrant their own
slice once itemized estimates and supplements have been reviewed in use.

## Migration

One migration: `estimates/0002_estimate_kind_estimate_parent_estimate_and_more`
adds `kind` and `parent_estimate` to `Estimate` and creates the
`EstimateLineItem` model. No billing, repair-order, customer, or vehicle schema
changed.

## Consequences

- Estimates can be itemized; the total is derived from line items once any
  exist, and remains manual otherwise.
- Supplements are first-class estimates linked to a parent, with validated
  lineage.
- Billing and invoice behavior are completely unchanged.
- Authorization matrix is unchanged; estimates reuse repair-order permissions.
- Test count rose from 654 to 721.

## Remaining limitations

- No invoice generation from estimates.
- No conversion of estimate line items into invoice line items.
- No PDF estimate output.
- No approval/signature workflow.
- No insurer/customer portal.
- No full estimate versioning engine (supplements are a minimal lineage only).
- No estimate locking by repair-order final status (deferred; current estimate
  behavior from Slice 29 is preserved).
- No object-level authorization yet.
- No production hardening yet.
