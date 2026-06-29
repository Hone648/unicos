"""Billing service boundary.

Currently houses the estimate-to-invoice draft conversion. Conversion reads an
approved estimate and creates a *draft* invoice for the same repair order, copying
estimate line items into invoice line items. Issuing, payment, and lifecycle
transitions remain separate billing operations.
"""

from django.db import transaction

from core.document_numbers import generate_invoice_number
from estimates.models import Estimate

from .models import Invoice, InvoiceLineItem


class EstimateInvoiceConversionError(Exception):
    """Base error for estimate-to-invoice conversion."""


class EstimateInvoiceConversionBlocked(EstimateInvoiceConversionError):
    """Conversion is not allowed for the given estimate in its current state."""


def _conversion_block_reason(estimate):
    """Return a human-readable reason conversion is blocked, or None if allowed."""
    if estimate.status != Estimate.Status.APPROVED:
        return "Only approved estimates can be converted to an invoice."

    if not estimate.line_items.exists():
        return (
            "This estimate has no line items, so there is nothing to convert "
            "into an invoice."
        )

    existing = estimate.converted_invoices.first()
    if existing is not None:
        return (
            f"Estimate {estimate.estimate_number} has already been converted to "
            f"invoice {existing.invoice_number}."
        )

    # Invoice.repair_order is one-to-one: a repair order can carry only one
    # invoice. Block (rather than crash on the unique constraint) when one exists.
    if Invoice.objects.filter(repair_order=estimate.repair_order).exists():
        return (
            f"Repair order {estimate.repair_order.repair_order_number} already "
            "has an invoice and cannot accept a converted estimate."
        )

    return None


def estimate_can_convert_to_invoice(estimate):
    """Predicate for UI/view gating: True when conversion is currently allowed."""
    return _conversion_block_reason(estimate) is None


@transaction.atomic
def convert_estimate_to_invoice(estimate, *, created_by=None):
    """Create a draft invoice from an approved estimate.

    Copies the estimate's line items into invoice line items, links the new
    invoice back to the source estimate, and returns the created invoice. Raises
    ``EstimateInvoiceConversionBlocked`` (without creating anything) when the
    estimate is not eligible. Does not mutate the estimate or issue the invoice.
    """
    # Lock the estimate row so concurrent conversion attempts serialize; the
    # second one then sees the first invoice and is blocked below.
    locked_estimate = (
        Estimate.objects.select_for_update()
        .select_related("repair_order")
        .get(pk=estimate.pk)
    )

    reason = _conversion_block_reason(locked_estimate)
    if reason is not None:
        raise EstimateInvoiceConversionBlocked(reason)

    invoice = Invoice.objects.create(
        repair_order=locked_estimate.repair_order,
        invoice_number=generate_invoice_number(),
        status=Invoice.Status.DRAFT,
        source_estimate=locked_estimate,
        created_by=created_by,
        updated_by=created_by,
    )

    # Copy line items. Each InvoiceLineItem.save() recalculates the invoice
    # subtotal, so the invoice total ends up matching the estimate total.
    for item in locked_estimate.line_items.all():
        InvoiceLineItem.objects.create(
            invoice=invoice,
            item_type=item.item_type,
            description=item.description,
            quantity=item.quantity,
            unit_price=item.unit_price,
        )

    invoice.refresh_from_db()
    return invoice
