from billing.models import Invoice

from .models import RepairOrder

_FINAL_STATUSES = frozenset({
    RepairOrder.Status.DELIVERED,
    RepairOrder.Status.CLOSED,
    RepairOrder.Status.CANCELED,
})


def closure_blocked_by_invoice(repair_order, new_status):
    """Return the blocking invoice if transitioning to new_status is blocked, else None.

    Blocked when: new_status is a final status AND the repair order has a non-void
    invoice with balance_due > 0.  No invoice, or a void invoice, never blocks.
    """
    if new_status not in _FINAL_STATUSES:
        return None
    try:
        invoice = repair_order.invoice
    except RepairOrder.invoice.RelatedObjectDoesNotExist:
        return None
    if invoice.status == Invoice.Status.VOID:
        return None
    if invoice.balance_due > 0:
        return invoice
    return None
