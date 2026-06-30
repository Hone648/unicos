# 0046. Django admin service alignment

## Status

Accepted

## Context

Django admin is retained as an emergency/development console
(`DECISIONS/0042-django-admin-policy.md`). Several domain workflows now have
explicit service boundaries: repair-order lifecycle transitions
(`repair_orders.services`), estimate status transitions
(`estimates.services`), and billing mutations — invoice issue/void, payment
recording, and invoice line-item create/edit (`billing.services`).

Admin can accidentally bypass these service boundaries when `ModelAdmin`
fields and `save_model()` save directly instead of routing through the
service layer. Bypasses are especially risky for estimate approval (which
requires captured approval source/contact before `approved_at` is stamped),
invoice lifecycle (`issued`/`void` carry payment and closure consequences),
payment recording (must respect void-invoice and final-repair-order-status
blocks), invoice line-item mutation (same blocks, plus invoice subtotal
recalculation), and attachments (evidence/media metadata that should not be
casually altered or deleted).

Before this slice:

- `EstimateAdmin.save_model()` saved status directly with no routing through
  `transition_estimate_status()` and no approval-capture enforcement.
- `InvoiceAdmin` exposed `status` as a directly editable field with no
  routing through `issue_invoice()`/`void_invoice()`.
- `PaymentAdmin.save_model()` saved directly, bypassing
  `ensure_payment_recordable()`.
- `InvoiceLineItemAdmin.save_model()` saved directly, bypassing
  `ensure_invoice_line_items_mutable()`.
- `InvoiceLineItemInline` and `PaymentInline` on `InvoiceAdmin` allowed
  inline add/change, which also bypasses the service layer (an inline
  formset save calls `obj.save()` directly, with no hook into
  `save_model()`).
- `AttachmentAdmin` allowed `repair_order` and `uploaded_by` to be
  reassigned after upload, and did not restrict delete.

`RepairOrderAdmin` already routed status changes through
`transition_repair_order_status()` and bulk actions through
`RepairOrder.set_status()`; `RepairOrderStatusHistoryAdmin` was already fully
read-only. That existing pattern was used as the template for this slice.

## Decision

Keep Django admin available as an emergency/development console, but align
high-risk admin mutations with domain services:

- `EstimateAdmin.save_model()` now detects a status change in
  `form.changed_data`, restores the original status, saves other field
  changes, then calls `transition_estimate_status()` with approval data
  collected from the form. `EstimateStatusTransitionBlocked` is surfaced via
  `message_user()`. `approved_at` is readonly. `estimated_total` becomes
  readonly once the estimate has line items (mirroring the shop-facing form
  behavior and the billing invoice subtotal pattern), editable otherwise.
  `EstimateLineItemInline` and the standalone `EstimateLineItemAdmin` block
  add/change/delete for estimates that are not in `draft` status via
  `estimate_is_editable()`.
- `InvoiceAdmin.status` is always readonly; lifecycle changes go through two
  new bulk actions, `issue_selected_invoices` and `void_selected_invoices`,
  backed by `issue_invoice()`/`void_invoice()`. `subtotal` becomes readonly
  once the invoice has line items, editable otherwise (same pattern as
  estimate `estimated_total`).
- `InvoiceLineItemInline` and `PaymentInline` on `InvoiceAdmin` are read-only
  (no add/change/delete) — they exist for visibility only.
  `show_change_link` still points to the standalone admin pages where
  service-backed mutation applies.
- `InvoiceLineItemAdmin.save_model()` routes create through
  `create_invoice_line_item()` and edit through `edit_invoice_line_item()`,
  surfacing `InvoiceLineItemMutationBlocked` via `message_user()`. Delete
  remains disabled (no delete service exists).
- `PaymentAdmin.save_model()` routes creation through `record_payment()`.
  Existing payments cannot be changed (`has_change_permission()` returns
  `False` for an existing object) or deleted (`has_delete_permission()`
  always returns `False`).
- `AttachmentAdmin` makes `repair_order`, `file`, `original_filename`,
  `content_type`, `size_bytes`, `uploaded_by`, and `created_at` readonly, and
  disables delete (`has_delete_permission()` returns `False`). Only
  `category` and `description` remain editable after upload.
- `RepairOrderAdmin` is left unchanged; it already aligns with this pattern.

## Consequences

Positive:

- The emergency admin console remains available for inspection and a
  reduced set of safe mutations.
- Estimate, invoice, payment, and invoice line-item domain invariants
  (allowed-transition rules, approval capture, void/final-status blocks) are
  far less likely to be bypassed through admin.
- Attachment evidence/media metadata cannot be casually altered or deleted
  through admin.
- The new admin behaviors are unit-testable in isolation
  (`tests_admin.py` in `estimates`, `billing`, and `attachments`), following
  the existing `repair_orders` convention.

Trade-offs:

- Admin is less convenient for direct emergency edits: invoice status,
  payment edits, line-item-driven totals, and most attachment metadata can
  no longer be changed by editing a field and clicking Save.
- `InvoiceAdmin.subtotal` and `EstimateAdmin.estimated_total` use a
  conditional readonly rule (readonly only once line items exist) rather
  than a blanket readonly, to preserve the existing manual-total workflow
  for estimates/invoices with no line items. This mirrors already-accepted
  behavior elsewhere in the app rather than introducing a new pattern.
- `EstimateAdmin` still allows direct editing of `approval_source`,
  `approval_contact_name`, `approval_reference`, and `approval_note` outside
  of a status transition (i.e., without changing `status`). This is a minor,
  deliberate gap: editing approval metadata text on an already-approved
  estimate does not retroactively re-stamp `approved_at` or change the
  estimate's status, so the core approval-capture invariant
  (`approved_at` set only by the service) still holds.
- Full admin object-level permission integration (matching the shop-facing
  policy layer) remains future work; admin authorization is still Django's
  own staff/superuser model.

See `DECISIONS/0042-django-admin-policy.md` for the original admin-as-console
decision and `ARCHITECTURE.md` for the current service-layer boundaries.
