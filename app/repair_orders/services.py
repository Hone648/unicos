from django.db import transaction
from django.utils import timezone

from .business_rules import closure_blocked_by_invoice


class RepairOrderLifecycleError(Exception):
    pass


class RepairOrderStatusTransitionBlocked(RepairOrderLifecycleError):
    def __init__(self, message, *, invoice):
        super().__init__(message)
        self.invoice = invoice


@transaction.atomic
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
    Closure decisions and writes use the current row under a lock, so a
    stale duplicate cannot replace a saved closure timestamp. Other validation
    and no-op behavior delegates to the model. Returns the caller's instance.
    """
    from .models import RepairOrder  # local import avoids circular dependency

    current_order = repair_order
    if new_status == RepairOrder.Status.CLOSED:
        current_order = RepairOrder.objects.select_for_update().get(pk=repair_order.pk)
        if current_order.status == RepairOrder.Status.CLOSED:
            repair_order.status = current_order.status
            repair_order.closed_at = current_order.closed_at
            return repair_order

    blocking_invoice = closure_blocked_by_invoice(current_order, new_status)
    if blocking_invoice:
        label = dict(RepairOrder.Status.choices).get(new_status, new_status)
        raise RepairOrderStatusTransitionBlocked(
            f"Repair order cannot be marked {label.lower()} because "
            f"invoice {blocking_invoice.invoice_number} has a balance due.",
            invoice=blocking_invoice,
        )

    if new_status == RepairOrder.Status.CLOSED:
        # Save the locked row so a stale caller cannot restore older field values.
        current_order.closed_at = timezone.now()
    current_order._apply_status_change(new_status, changed_by=changed_by, note=note)
    if current_order is not repair_order:
        repair_order.status = current_order.status
        repair_order.closed_at = current_order.closed_at
    return repair_order
