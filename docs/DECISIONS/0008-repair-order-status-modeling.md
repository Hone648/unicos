# 0008: Repair Order and Status Modeling

Status: Accepted

Decision:

Introduce `repair_orders.RepairOrder` and `repair_orders.RepairOrderStatusHistory`
as the central shop workflow models.

**Repair orders as the workflow hub**

A repair order links a `Customer`, a `Vehicle`, and optionally an assigned staff
user. It is the primary record shop staff work from: intake through delivery.
Repair orders carry FK references to `Customer` and `Vehicle` with `PROTECT`,
preserving business history even if a customer or vehicle is archived.

**Status as controlled TextChoices**

Status is implemented as `RepairOrder.Status` (a Django `TextChoices` enum):

```
intake → estimating → awaiting_approval → approved → parts_ordered
→ in_repair → quality_check → ready_for_pickup → delivered → closed / canceled
```

Reasons for TextChoices over a configurable status table:
- Simpler and more stable for the first workflow iteration.
- Status values are tightly coupled to business logic (permissions, closed
  detection, reporting). Making them configurable without also configuring
  those behaviors would give a false sense of flexibility.
- Configurable statuses can be revisited after the real shop workflow is proven.

No status transition state machine is implemented in this slice. Any valid
status can move to any other valid status.

**Status history as an append-only audit trail**

`RepairOrderStatusHistory` records every status change automatically:
- Created on repair order creation (previous_status=None).
- Created on each status change with previous and new status, optional changed_by
  user, and optional note.
- No history record is created when a repair order is saved without a status
  change.
- History is deleted when the repair order is deleted (CASCADE).

History is generated inside `RepairOrder.save()` using a DB fetch of the old
status before saving. The `set_status()` convenience method manages the
transient `_status_changed_by` and `_status_change_note` attributes for callers
who want to attach user and note context to a status change.

Signals were intentionally avoided in this slice for simplicity.

**Staffing and audit fields**

- `assigned_to` — the staff member currently responsible for the RO.
- `created_by` / `updated_by` — tracked via `admin.save_model()` for admin-driven
  changes. Not automatically populated for direct ORM saves (acceptable for now).

**Deferred scope**

The following are not in this slice:
- Invoice models
- Payment models
- Estimate models
- Parts / labor line models
- Photo / attachment models
- Insurance workflow
- Supplements
- Status transition state machine
- Configurable status table
- Automatic RO number generation
