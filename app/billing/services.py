"""Billing service boundary."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.document_numbers import generate_invoice_number
from estimates.models import Estimate
from repair_orders.business_rules import is_final_repair_order_status

from .models import Invoice, InvoiceLineItem, Payment


class BillingServiceError(Exception):
    """Base error for billing service operations."""


class BillingOperationBlocked(BillingServiceError):
    """Billing mutation is not allowed in the current state."""


class InvoiceIssueBlocked(BillingOperationBlocked):
    """Invoice issue transition is blocked."""


class InvoiceVoidBlocked(BillingOperationBlocked):
    """Invoice void transition is blocked."""


class PaymentRecordingBlocked(BillingOperationBlocked):
    """Payment recording is blocked."""


class InvoiceLineItemMutationBlocked(BillingOperationBlocked):
    """Invoice line-item mutation is blocked."""


class EstimateInvoiceConversionError(Exception):
    """Base error for estimate-to-invoice conversion."""


class EstimateInvoiceConversionBlocked(EstimateInvoiceConversionError):
    """Conversion is not allowed for the given estimate in its current state."""


_PAYMENT_FIELDS = ["payment_date", "amount", "method", "reference", "notes"]
_LINE_ITEM_FIELDS = ["item_type", "description", "quantity", "unit_price"]


def _final_invoice_message(invoice):
    return (
        f"Invoice {invoice.invoice_number} belongs to a final repair order "
        "and cannot be changed."
    )


def _invoice_void_message(invoice):
    return f"Invoice {invoice.invoice_number} is void and cannot be edited."


def _lock_invoice(invoice):
    return (
        Invoice.objects.select_for_update()
        .select_related("repair_order")
        .get(pk=invoice.pk)
    )


def _ensure_repair_order_allows_billing(invoice, exception_cls):
    if is_final_repair_order_status(invoice.repair_order.status):
        raise exception_cls(_final_invoice_message(invoice))


def ensure_payment_recordable(invoice):
    """Raise if a payment cannot be recorded for this invoice."""
    _ensure_repair_order_allows_billing(invoice, PaymentRecordingBlocked)
    if invoice.status == Invoice.Status.VOID:
        raise PaymentRecordingBlocked(
            f"Invoice {invoice.invoice_number} is void and cannot accept payments."
        )


def ensure_invoice_line_items_mutable(invoice):
    """Raise if invoice line items cannot be changed."""
    _ensure_repair_order_allows_billing(invoice, InvoiceLineItemMutationBlocked)
    if invoice.status == Invoice.Status.VOID:
        raise InvoiceLineItemMutationBlocked(_invoice_void_message(invoice))


def _model_validation_message(error):
    if hasattr(error, "messages"):
        return " ".join(error.messages)
    return str(error)


def _clean_data(data, fields):
    return {field: data[field] for field in fields if field in data}


def _conversion_block_reason(estimate):
    """Return a human-readable reason conversion is blocked, or None if allowed."""
    if estimate.status != Estimate.Status.APPROVED:
        return "Only approved estimates can be converted to an invoice."

    if not estimate.has_approval_capture:
        return (
            "This estimate is approved but has no approval capture. Record "
            "customer or insurer approval before creating an invoice."
        )

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


def issue_invoice(invoice, *, actor):
    """Issue a draft invoice and return the updated invoice."""
    _ensure_repair_order_allows_billing(invoice, InvoiceIssueBlocked)
    if invoice.status != Invoice.Status.DRAFT:
        raise InvoiceIssueBlocked(
            f"Invoice {invoice.invoice_number} is already "
            f"{invoice.get_status_display().lower()} - no change made."
        )

    invoice.status = Invoice.Status.ISSUED
    if not invoice.issued_at:
        invoice.issued_at = timezone.localdate()
    invoice.updated_by = actor
    invoice.save(update_fields=["status", "issued_at", "updated_by", "updated_at"])
    return invoice


def void_invoice(invoice, *, actor):
    """Void an invoice and return the updated invoice."""
    _ensure_repair_order_allows_billing(invoice, InvoiceVoidBlocked)
    if invoice.status == Invoice.Status.VOID:
        raise InvoiceVoidBlocked(f"Invoice {invoice.invoice_number} is already void.")

    invoice.status = Invoice.Status.VOID
    invoice.updated_by = actor
    invoice.save(update_fields=["status", "updated_by", "updated_at"])
    return invoice


@transaction.atomic
def record_payment(invoice, data, *, actor):
    """Record a payment while locking the invoice balance row."""
    locked_invoice = _lock_invoice(invoice)
    ensure_payment_recordable(locked_invoice)

    payment = Payment(
        invoice=locked_invoice,
        received_by=actor,
        **_clean_data(data, _PAYMENT_FIELDS),
    )
    try:
        payment.full_clean()
        payment.save()
    except ValidationError as error:
        raise PaymentRecordingBlocked(_model_validation_message(error)) from error

    return payment


def create_invoice_line_item(invoice, data, *, actor):
    """Create an invoice line item and return it."""
    del actor
    ensure_invoice_line_items_mutable(invoice)
    line_item = InvoiceLineItem(
        invoice=invoice,
        **_clean_data(data, _LINE_ITEM_FIELDS),
    )
    try:
        line_item.save()
    except ValidationError as error:
        raise InvoiceLineItemMutationBlocked(_model_validation_message(error)) from error
    return line_item


def edit_invoice_line_item(line_item, data, *, actor):
    """Edit an invoice line item and return it."""
    del actor
    invoice = line_item.invoice
    ensure_invoice_line_items_mutable(invoice)
    for field, value in _clean_data(data, _LINE_ITEM_FIELDS).items():
        setattr(line_item, field, value)
    try:
        line_item.save()
    except ValidationError as error:
        raise InvoiceLineItemMutationBlocked(_model_validation_message(error)) from error
    return line_item
