# 0024: Final Repair Order Billing Guards

Status: Accepted

Decision:

Final repair orders are billing-read-only in shop-facing views. Delivered,
Closed, and Canceled repair orders keep their billing records visible, but
invoice creation/editing, line-item creation/editing, payment creation, invoice
issue, and invoice void actions are blocked.

Rationale:

- Final repair orders should preserve their billing state after delivery,
  closure, or cancellation.
- Billing records remain visible for operational review.
- Repair-order invoice summaries and printable invoice pages remain available.
- Payment history remains visible.
- Direct URL access is guarded in views, not only by hiding UI links/buttons.
- Payments are blocked for final repair orders in this slice.

Scope:

- Status movement is not fully frozen.
- Delivered -> Closed remains allowed when existing invoice-balance closure rules
  allow it.
- Existing void-invoice guards remain in force.
- No model migration was added.
- No custom JavaScript was introduced.
