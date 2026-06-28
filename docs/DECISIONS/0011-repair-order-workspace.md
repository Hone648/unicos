# 0011: Repair-Order Workspace (First Custom UI)

Status: Accepted

Decision:

Introduce a shop-facing repair-order workspace as the first custom UI layer,
separate from Django admin.

**Server-rendered Django views — no frontend framework**

The workspace uses plain Django views and templates. No HTMX, Tailwind, JavaScript
framework, or frontend build tooling is introduced in this slice. Semantic HTML
and the existing base template are sufficient for the first shop-facing screen.

**Django admin remains available for full back-office operations**

The workspace is not a replacement for admin. Admin continues to handle customer
creation, vehicle creation, billing operations, user management, and any operation
not yet exposed in the custom UI.

**The workspace focuses on open repair-order visibility and status changes**

The list view defaults to open (non-closed, non-canceled) repair orders.
Search covers repair order number, customer name, vehicle VIN, make, model,
and license plate. Status can be filtered via query string.

The detail view shows repair order data, status history newest-first, and a
read-only invoice/payment summary when an invoice exists.

**Status changes still use `RepairOrder.set_status()` to preserve history**

The status update POST view calls `set_status(new_status, changed_by=request.user,
note=...)` rather than using `queryset.update()`. This preserves the
`RepairOrderStatusHistory` invariant established in Slice 4.

Same-status POSTs are detected before calling `set_status()` and produce an
info message with no history row created.

Invalid status values are rejected with an error message and no mutation.

**Billing is read-only in this UI**

The detail page shows invoice number, status, total, amount paid, and balance
due when an invoice exists. Invoice and payment creation/editing remain in
Django admin only.

**Deferred scope**

- HTMX for partial-page updates
- Tailwind or any CSS framework
- Role-based permissions (technician vs. front desk vs. manager)
- Invoice/payment mutation UI
- Estimate models, parts, labor, work items
- Insurance claims
- Photo/attachment upload
- PDF invoice generation
- Email sending
- Payment processor integration
- Customer-facing portal
