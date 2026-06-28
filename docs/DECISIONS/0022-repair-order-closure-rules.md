# 0022: Repair-Order Closure Rules

Status: Accepted

Decision:

Block final/closed repair-order status transitions when the repair order has
a non-void invoice with an outstanding balance due. Staff must collect payment
(or void the invoice) before closing or delivering a job.

**Final statuses are DELIVERED, CLOSED, and CANCELED**

`RepairOrder.Status` has eleven values. Three represent the end of the job
lifecycle and are treated as final:

- `DELIVERED` — the vehicle has been returned to the customer. This is the
  primary trigger: money should be settled before the car leaves the shop.
- `CLOSED` — administrative close of the repair order after delivery.
- `CANCELED` — the job was abandoned. If an invoice exists and has a balance,
  staff should void the invoice before canceling; that removes the balance and
  unblocks the transition.

All other statuses (INTAKE, ESTIMATING, AWAITING_APPROVAL, APPROVED,
PARTS_ORDERED, IN_REPAIR, QUALITY_CHECK, READY_FOR_PICKUP) are workflow
statuses and are never blocked by this rule.

**Void invoices do not block closure**

A voided invoice has status `void`. A void invoice means the billing record
has been cancelled; it has no collectible balance. Voiding the invoice before
closing is the correct shop workflow for abandoned jobs. The guard explicitly
bypasses void invoices.

**No invoice does not block closure**

If the repair order has no invoice at all, the guard cannot fire. Some jobs
may be handled as cash at the counter before an invoice is created, or an
invoice may never be created for warranty work.

**Paid invoices do not block closure**

`invoice.balance_due` is calculated from `total_amount - amount_paid`. A
fully paid invoice has `balance_due == 0` and therefore does not trigger the
guard. A partially paid invoice with `balance_due > 0` does trigger the guard,
which is correct: there is still money owed.

**Enforcement is in the shop-facing status-update view, not the model**

The rule is enforced in `repair_order_status_update` in `repair_orders/views.py`,
using a helper in `repair_orders/business_rules.py`. This is intentional:

- The model's `set_status()` and `save()` are called from multiple places
  (admin, management commands, tests). Adding a hard constraint at the model
  level would break admin workflows and testing utilities that legitimately
  set any status.
- The shop-facing view is the right boundary: staff use it to drive the
  workflow, and it already guards invalid status values.
- HTMX and non-HTMX paths both pass through the same view, so both paths
  get the guard consistently.

**No model migration was added**

The rule uses existing model fields: `invoice.status`, `invoice.balance_due`,
and `RepairOrder.Status` choices. No new fields or database changes are needed.

**Invoice issuing, payment collection, and repair-order closing remain separate
user actions**

The system does not automatically issue invoices, collect payments, or close
repair orders. These are distinct steps that staff perform intentionally. The
closure rule enforces the dependency — money first, then close — without
collapsing the steps or automating them.

**Out of scope for this slice**

- New repair-order statuses
- Automatic invoice issuing on delivery
- Automatic invoice voiding on cancellation
- Estimate-to-invoice conversion
- Insurance workflow
- Customer authorization/signature requirement
- Inventory/parts tracking
- PDF generation, email workflow, payment links
- Accounting export
- API endpoint
- Custom JavaScript or Tailwind
