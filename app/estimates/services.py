from django.utils import timezone

from .models import Estimate


class EstimateStatusTransitionError(Exception):
    pass


class EstimateStatusTransitionBlocked(EstimateStatusTransitionError):
    pass


ALLOWED_ESTIMATE_STATUS_TRANSITIONS = {
    Estimate.Status.DRAFT: {Estimate.Status.SUBMITTED},
    Estimate.Status.SUBMITTED: {
        Estimate.Status.APPROVED,
        Estimate.Status.DECLINED,
        Estimate.Status.EXPIRED,
    },
    Estimate.Status.APPROVED: set(),
    Estimate.Status.DECLINED: set(),
    Estimate.Status.EXPIRED: set(),
}


def get_available_estimate_status_transitions(estimate):
    return ALLOWED_ESTIMATE_STATUS_TRANSITIONS.get(estimate.status, set())


def estimate_is_editable(estimate):
    return estimate.status == estimate.Status.DRAFT


def transition_estimate_status(
    estimate,
    new_status,
    *,
    updated_by=None,
    approval_data=None,
):
    if new_status not in {value for value, _label in Estimate.Status.choices}:
        raise EstimateStatusTransitionBlocked(
            f"'{new_status}' is not a valid estimate status."
        )

    if new_status == estimate.status:
        raise EstimateStatusTransitionBlocked(
            f"Estimate {estimate.estimate_number} is already "
            f"{estimate.get_status_display().lower()}."
        )

    allowed_statuses = get_available_estimate_status_transitions(estimate)
    if new_status not in allowed_statuses:
        raise EstimateStatusTransitionBlocked(
            f"Estimate {estimate.estimate_number} cannot move from "
            f"{estimate.get_status_display().lower()} to "
            f"{dict(Estimate.Status.choices)[new_status].lower()}."
        )

    estimate.status = new_status
    update_fields = ["status", "updated_at"]

    if new_status == Estimate.Status.APPROVED:
        approval_data = approval_data or {}
        approval_source = approval_data.get("approval_source", "")
        approval_contact_name = (approval_data.get("approval_contact_name") or "").strip()
        valid_sources = {value for value, _label in Estimate.ApprovalSource.choices}
        if (
            not approval_source
            or approval_source not in valid_sources
            or not approval_contact_name
        ):
            raise EstimateStatusTransitionBlocked(
                "Approval source and approval contact name are required before "
                "an estimate can be approved."
            )

        estimate.approval_source = approval_source
        estimate.approval_contact_name = approval_contact_name
        estimate.approval_reference = (
            approval_data.get("approval_reference") or ""
        ).strip()
        estimate.approval_note = (approval_data.get("approval_note") or "").strip()
        estimate.approved_at = timezone.now()
        update_fields.extend([
            "approval_source",
            "approval_contact_name",
            "approval_reference",
            "approval_note",
            "approved_at",
        ])

    if updated_by is not None:
        estimate.updated_by = updated_by
        update_fields.append("updated_by")
    estimate.save(update_fields=update_fields)
    return estimate
