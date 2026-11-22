from django.core import signing
from django.urls import reverse

from .business_rules import is_final_repair_order_status


def _signer(invoice):
    return signing.Signer(
        salt=f"repair_orders.status_continuation.{invoice.repair_order_id}.{invoice.pk}"
    )


def sign_status_continuation(invoice, status, *, payment_recorded=False):
    return _signer(invoice).sign_object([status, payment_recorded])


def read_status_continuation(invoice, token):
    if invoice is None or not token:
        return None, False
    try:
        status, payment_recorded = _signer(invoice).unsign_object(token)
    except signing.BadSignature:
        return None, False
    if not is_final_repair_order_status(status):
        return None, False
    return status, payment_recorded


def status_controls_url(repair_order_pk, token):
    return reverse(
        "repair_orders:detail",
        kwargs={"pk": repair_order_pk},
        query={"status_continuation": token},
        fragment="status-update-card",
    )
