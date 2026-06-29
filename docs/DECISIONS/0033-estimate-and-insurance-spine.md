# 0033 — Estimate and Insurance Spine

## Context

The app manages customers, vehicles, repair orders, and billing, but has no
representation of estimates or insurance/claim context. Body shops routinely
write estimates (often insurer-driven) before or alongside the repair workflow,
and that context — insurer, claim number, deductible, estimated total — has had
nowhere to live.

This slice adds the first estimate/insurance data spine so a repair order can
carry estimate records, without changing invoice or billing behavior and
without pulling forward the larger estimate workflow (line items, supplements,
approvals, PDF output, invoice generation).

## Decision

### Separate `estimates` app

Estimates are their own domain object with their own status lifecycle,
insurance fields, document-number sequence, views, and admin. A dedicated app
keeps the model and its workflow isolated from `repair_orders` and `billing`,
mirroring how `billing` is structured. This leaves room for estimate line items
and supplements to be added later inside the same app without disturbing
repair-order or billing code.

### Estimate links to RepairOrder via `PROTECT`

```python
repair_order = models.ForeignKey(
    "repair_orders.RepairOrder",
    on_delete=models.PROTECT,
    related_name="estimates",
)
```

The estimate is a repair-order workflow object, so it hangs off the repair
order. `PROTECT` matches the project convention (customer, vehicle, invoice all
use `PROTECT`): a repair order that has estimates should not be silently
deletable, because estimates are audit-relevant records.

### Multiple estimates per repair order

The relationship is a `ForeignKey`, not a `OneToOneField`. A repair order may
accumulate multiple estimates over time (initial estimate, revisions, and —
later — supplements). Allowing many now keeps the future path open without a
schema reversal. The invoice relationship remains one-to-one and unchanged.

### Only basic insurance/claim fields now

This slice captures `insurance_company`, `claim_number`, `deductible`,
`estimated_total`, a small `status` lifecycle (draft/submitted/approved/
declined/expired), and `notes`. Insurance fields are optional because
customer-pay estimates have no insurer or claim. Richer insurance modeling
(adjuster, DRP flags, supplements, coverage lines) is deferred.

### Estimate line items, supplements, PDF, and invoice generation are deferred

Deliberately out of scope to keep the slice narrow:

- No `EstimateLineItem` — estimated_total is a single manual amount for now.
- No supplements or revisions workflow.
- No insurer/customer approval workflow or digital signatures.
- No PDF estimate output.
- No automatic invoice generation from an estimate.

These each warrant their own slice once the spine is in place and reviewed.

### Generated estimate numbers reuse the document-number sequence

`core.document_numbers.generate_estimate_number()` was added alongside the
existing repair-order and invoice generators, using the same
`DocumentNumberSequence` table and `select_for_update()` locking approach. A new
`DocumentType.ESTIMATE` choice was added, producing `EST-YYYY-NNNNNN`. Adding
the choice altered the `document_type` field's choices, which generated a small
`core` migration (`0002_alter_documentnumbersequence_document_type`).

### Estimate permissions reuse repair-order permissions

Estimates are repair-order workflow objects, so they reuse the existing
authorization matrix rather than introducing new permissions or roles:

- Estimate detail requires `PERM_REPAIR_ORDERS_VIEW`.
- Estimate create/edit require `PERM_REPAIR_ORDERS_MANAGE`.

This keeps the authorization matrix unchanged. Templates hide the create/edit
links when the user lacks `repair_orders.manage`, but the view decorators remain
authoritative.

### Repair-order detail integration

The repair-order detail page gained an estimate summary section
(`estimates/partials/_estimate_summary.html`) listing each estimate with its
number (linked to detail), status, insurer, claim number, deductible, and
estimated total, plus a permission-gated "Create Estimate" action. The invoice
summary is untouched. The detail context uses a deterministic query:
`ro.estimates.order_by("-updated_at", "-id")`.

### No global estimate queue

No top-level Estimates nav item or estimate list page was added; the estimate
workflow is entered from the repair-order detail page. A global estimate queue
(with pagination) can be added in a later slice if needed.

## Migration

This slice adds two migrations:

- `estimates/0001_initial` — creates the `Estimate` model.
- `core/0002_alter_documentnumbersequence_document_type` — adds the `estimate`
  document-type choice.

No billing, repair-order, customer, or vehicle schema changed.

## Consequences

- Repair orders can carry one or more estimate records with insurance/claim
  context.
- Estimate numbers are system-generated (`EST-YYYY-NNNNNN`).
- Billing and invoice behavior are completely unchanged.
- Authorization matrix is unchanged; estimates reuse repair-order permissions.
- Test count rose from 584 to 654.

## Remaining limitations

- No estimate line items.
- No supplements.
- No insurer/customer approval workflow.
- No PDF estimate output.
- No invoice-generation automation from estimates.
- No object-level authorization yet.
- No production hardening yet.
