# 0014: Shop-Facing Repair Order Create/Edit

Status: Accepted

Decision:

Add shop-facing create and edit views for repair orders, allowing staff to
create and correct basic repair-order information from the repair-order
workspace without needing Django admin.

**Shop-facing create/edit is added for basic repair-order data**

The create and edit views expose only the fields staff need to initiate or
correct a repair order: RO number, customer, vehicle, assigned staff member,
promised date, reported problem, and internal notes.

**Customer and vehicle records must already exist**

This slice does not add customer or vehicle creation flows. Staff must select
from existing customers and vehicles. Customer and vehicle creation remain an
admin-only operation until a dedicated slice adds shop-facing customer/vehicle
management.

**Vehicle/customer relationship is validated in the form**

`RepairOrderForm.clean()` verifies that the selected vehicle's `customer_id`
matches the selected customer's `pk`:

```python
if vehicle.customer_id != customer.pk:
    raise forms.ValidationError(
        "The selected vehicle does not belong to the selected customer."
    )
```

The model's `clean()` method also enforces this invariant, but ModelForm does
not call `model.clean()` automatically, so the check is duplicated in the form.
The model constraint remains as a defense-in-depth guarantee for any direct ORM
saves that bypass form validation.

**Status is intentionally excluded from create/edit**

The `status` field is not included in `RepairOrderForm.Meta.fields`. Status
changes must always go through `RepairOrder.set_status()`, which creates an
audit trail entry and enforces valid transitions. Allowing status changes via
a general edit form would bypass this audit trail.

**Status changes remain controlled by `RepairOrder.set_status()`**

The existing HTMX status update form and its underlying view continue to be
the only path for changing status from the shop workspace. Basic field edits
do not create new `RepairOrderStatusHistory` entries.

**Audit fields are set in the view, not the form**

`created_by` and `updated_by` are excluded from the form. The create view sets
both fields to `request.user` before saving. The edit view sets `updated_by`
to `request.user` and leaves `created_by` unchanged.

**Normal Django POST/redirect is used; HTMX is not expanded in this slice**

The create and edit views follow the same function-based view pattern as
existing views. No HTMX behavior is added. This keeps the create/edit flow
simple and consistent with the rest of the workspace. HTMX can be added to
these views in a future slice if the UX warrants it.

**Billing, payments, customer creation, and vehicle creation are deferred**

Out of scope for this slice:
- Invoice creation/editing from the shop workspace
- Payment recording
- Customer creation
- Vehicle creation
- Parts and labor line items
- Photos and uploads
- Insurance workflow
- Advanced permissions (e.g., only assigned staff can edit)
- Dynamic vehicle filtering by customer (no JavaScript in this slice)
