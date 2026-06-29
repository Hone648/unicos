# 0030 — Repair-Order Lifecycle Service

## Context

Repair-order status transitions were previously enforced only in the
shop-facing status-update view (`repair_orders/views.py`). The rule — "block
final-status transitions when a non-void invoice has balance due" — lived in
`business_rules.py` and was called directly from the view. Admin bulk status
actions used `RepairOrder.set_status()` directly and therefore bypassed the
rule entirely.

The goal of this slice is to make the lifecycle rule authoritative everywhere
without duplicating it across views, admin, and test utilities.

## Decision

### Centralized service module

A dedicated service module (`repair_orders/services.py`) owns the lifecycle
rule:

```python
def transition_repair_order_status(repair_order, new_status, *, changed_by=None, note="")
```

It raises `RepairOrderStatusTransitionBlocked` (a subclass of
`RepairOrderLifecycleError`) when a final-status transition is blocked by an
unpaid invoice. All other validation (invalid status string, no-op) is
delegated to the model layer.

### `RepairOrder.set_status()` routes through the service

`set_status()` is now a compatibility entry point that delegates to
`transition_repair_order_status()`. All existing callers (views, admin, tests)
continue to work through the same public interface.

### Low-level `_apply_status_change()` for privileged callers

A private `_apply_status_change()` method on `RepairOrder` performs the actual
status write and history creation without enforcing lifecycle rules. It exists
for test setup (setting a final status to prepare fixtures) and as the internal
implementation target for the service. It must not be called from normal
application flows.

### Shop-facing view

`repair_order_status_update` no longer calls `closure_blocked_by_invoice()`
directly. It calls `transition_repair_order_status()` and catches
`RepairOrderStatusTransitionBlocked`. The user-facing error message format is
unchanged.

### Admin bulk status actions

`_apply_status_action()` calls `ro.set_status()` (unchanged call site), which
now routes through the service. Blocked transitions produce an admin error
message and leave the repair order unchanged; other orders in the queryset
continue to be processed.

### Admin status form

`save_model()` detects when the admin form changes the status field and routes
that change through `transition_repair_order_status()`. Other field changes
(notes, assigned-to, dates) are saved first with the original status, then the
service applies the transition. If the service blocks the transition, an error
message is shown and the status remains unchanged.

### No admin override behavior added

Admin users are not given a bypass pathway in this slice. If the product later
requires owner/admin overrides (e.g. voiding an unpaid invoice and closing in
one step), that should be an explicit future slice with clear audit semantics,
not a silent bypass.

## Consequences

- The unpaid-invoice final-status block is now enforced consistently across
  shop-facing views and Django admin.
- `RepairOrder.set_status()` is preserved as the normal public API.
- `RepairOrder._apply_status_change()` is available for test setup but should
  not appear in application code paths.
- Two existing test setups that used `set_status()` to force final status with
  blocking invoices were updated to `_apply_status_change()`.
- Lifecycle coverage is currently focused on repair-order status transitions;
  billing workflow operations (invoice issue, void, payment) do not yet have a
  corresponding service layer.

## Remaining limitations

- No object-level authorization (assigned-technician constraints).
- Other domain workflows (invoice lifecycle, payment recording) do not yet have
  service boundaries.
- Lifecycle centralization for billing is future work.
- No production deployment hardening in this slice.
