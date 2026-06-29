from .business_rules import closure_blocked_by_invoice


class RepairOrderLifecycleError(Exception):
    pass


class RepairOrderStatusTransitionBlocked(RepairOrderLifecycleError):
    pass


def transition_repair_order_status(
    repair_order,
    new_status,
    *,
    changed_by=None,
    note="",
):
    """Enforce lifecycle rules and apply a repair-order status transition.

    Raises RepairOrderStatusTransitionBlocked when new_status is a final
    status and a non-void invoice with balance_due > 0 blocks the transition.
    Validation (invalid status) and no-op (status unchanged) are handled by
    the model layer and propagate through transparently.
    """
    from .models import RepairOrder  # local import avoids circular dependency

    blocking_invoice = closure_blocked_by_invoice(repair_order, new_status)
    if blocking_invoice:
        label = dict(RepairOrder.Status.choices).get(new_status, new_status)
        raise RepairOrderStatusTransitionBlocked(
            f"Repair order cannot be marked {label.lower()} because "
            f"invoice {blocking_invoice.invoice_number} has a balance due."
        )

    repair_order._apply_status_change(new_status, changed_by=changed_by, note=note)
    return repair_order
