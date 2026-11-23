from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .business_rules import closure_blocked_by_invoice
from .transition_policy import transition_error


class RepairOrderLifecycleError(Exception):
    pass


class RepairOrderTransitionInvalid(RepairOrderLifecycleError):
    pass


class RepairOrderStatusTransitionBlocked(RepairOrderLifecycleError):
    def __init__(self, message, *, invoice):
        super().__init__(message)
        self.invoice = invoice


def _synchronize(caller, current):
    caller.status = current.status
    caller.closed_at = current.closed_at


@transaction.atomic
def transition_repair_order_status(
    repair_order,
    new_status,
    *,
    changed_by=None,
    note="",
    action="routine",
    reason="",
    expected_status=None,
):
    """Validate the locked saved state and persist only the current row.

    Duplicate routine requests are no-ops. Exceptions require an authorized
    actor and a reason; all writes and history share the row-lock transaction.
    The caller's status/date are synchronized and the same instance is returned.
    """
    from .models import RepairOrder

    if action == "routine" and new_status not in RepairOrder.Status.values:
        raise ValidationError(f"'{new_status}' is not a valid repair order status.")
    current = RepairOrder.objects.select_for_update().get(pk=repair_order.pk)
    _synchronize(repair_order, current)
    if action == "routine" and new_status == current.status:
        return repair_order
    if expected_status is not None and expected_status != current.status:
        raise RepairOrderTransitionInvalid(
            f"Status changed to {current.get_status_display()} since this page was loaded. "
            "Review the current available actions."
        )
    error = transition_error(current, new_status, action=action, actor=changed_by, reason=reason)
    if error:
        raise RepairOrderTransitionInvalid(error)
    blocking_invoice = closure_blocked_by_invoice(current, new_status)
    if blocking_invoice:
        label = dict(RepairOrder.Status.choices)[new_status]
        raise RepairOrderStatusTransitionBlocked(
            f"Repair order cannot be marked {label.lower()} because "
            f"invoice {blocking_invoice.invoice_number} has a balance due.",
            invoice=blocking_invoice,
        )
    if new_status == RepairOrder.Status.CLOSED:
        current.closed_at = timezone.now()
    current._apply_status_change(
        new_status, changed_by=changed_by, note=reason.strip() if action != "routine" else note
    )
    _synchronize(repair_order, current)
    return repair_order
