"""Routine workflow and explicitly authorized lifecycle exceptions."""

from accounts.policies import (
    can_change_repair_order_status,
    can_view_repair_order,
    is_owner_admin_or_manager,
)

from .models import RepairOrder

S = RepairOrder.Status
ROUTINE_TRANSITIONS = {
    S.INTAKE: (S.ESTIMATING, S.IN_REPAIR),
    S.ESTIMATING: (S.AWAITING_APPROVAL, S.APPROVED),
    S.AWAITING_APPROVAL: (S.APPROVED, S.ESTIMATING),
    S.APPROVED: (S.PARTS_ORDERED, S.IN_REPAIR),
    S.PARTS_ORDERED: (S.IN_REPAIR,),
    S.IN_REPAIR: (S.QUALITY_CHECK,),
    S.QUALITY_CHECK: (S.READY_FOR_PICKUP, S.IN_REPAIR),
    S.READY_FOR_PICKUP: (S.DELIVERED, S.IN_REPAIR),
    S.DELIVERED: (S.CLOSED,),
    S.CLOSED: (),
    S.CANCELED: (),
}
CANCELABLE_STATUSES = frozenset(ROUTINE_TRANSITIONS) - {S.DELIVERED, S.CLOSED, S.CANCELED}
REOPEN_TARGETS = {S.CLOSED: S.IN_REPAIR, S.CANCELED: S.INTAKE}


def routine_choices(status):
    return [(value, S(value).label) for value in ROUTINE_TRANSITIONS.get(status, ())]


def can_use_exceptions(user, repair_order):
    return is_owner_admin_or_manager(user) and can_view_repair_order(user, repair_order)


def transition_error(
    repair_order, new_status, *, action="routine", actor=None, reason="", require_reason=True
):
    current = repair_order.status
    if action == "routine":
        if actor is not None and not can_change_repair_order_status(actor, repair_order):
            return "You do not have permission to change this repair order's status."
        if new_status not in ROUTINE_TRANSITIONS.get(current, ()):
            return (
                f"{S(current).label} cannot change directly to "
                f"{dict(S.choices).get(new_status, new_status)}. Select a current available action."
            )
        return None
    if action not in {"cancel", "reopen"}:
        return "Unknown repair-order action. Select a current available action."
    if not actor or not can_use_exceptions(actor, repair_order):
        return "Only a Manager or Owner/Admin may cancel or reopen a repair order."
    if require_reason and not reason.strip():
        return "A nonblank reason is required to cancel or reopen a repair order."
    if len(reason.strip()) > 500:
        return "The reason must be 500 characters or fewer."
    if action == "cancel" and (current not in CANCELABLE_STATUSES or new_status != S.CANCELED):
        return "Cancellation is available only before delivery. Select a current available action."
    if action == "reopen" and REOPEN_TARGETS.get(current) != new_status:
        return (
            "Only Closed or Canceled repair orders can be reopened. "
            "Select a current available action."
        )
    return None
