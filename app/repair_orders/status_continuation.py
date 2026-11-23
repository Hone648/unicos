from django.core import signing
from django.urls import reverse

from .business_rules import is_final_repair_order_status
from .transition_policy import transition_error


def _signer(invoice):
    return signing.Signer(
        salt=f"repair_orders.status_continuation.{invoice.repair_order_id}.{invoice.pk}"
    )


def sign_status_continuation(
    invoice, status, *, payment_recorded=False, source_status=None, action="routine"
):
    return _signer(invoice).sign_object(
        {
            "status": status,
            "paid": payment_recorded,
            "source": source_status or invoice.repair_order.status,
            "action": action,
        }
    )


def continuation_details(invoice, token):
    if invoice is None or not token:
        return None
    try:
        data = _signer(invoice).unsign_object(token)
    except (signing.BadSignature, ValueError, TypeError):
        return None
    if not isinstance(data, dict) or not is_final_repair_order_status(data.get("status")):
        return None
    if not isinstance(data.get("paid"), bool) or data.get("action") not in {"routine", "cancel"}:
        return None
    return data


def read_status_continuation(invoice, token):
    data = continuation_details(invoice, token)
    return (data["status"], data["paid"]) if data else (None, False)


def validated_continuation(invoice, token, user):
    data = continuation_details(invoice, token)
    if not data:
        return None
    ro = invoice.repair_order
    if data.get("source") != ro.status:
        return None
    if transition_error(
        ro, data["status"], action=data["action"], actor=user, require_reason=False
    ):
        return None
    return data


def status_controls_url(repair_order_pk, token):
    return reverse(
        "repair_orders:detail",
        kwargs={"pk": repair_order_pk},
        query={"status_continuation": token},
        fragment="status-update-card",
    )
